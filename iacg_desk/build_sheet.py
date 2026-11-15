"""The confirmed build revision — the scope-finalize handoff (CE Phase 1).

Ported from iacgenius-v2 services/workflow/app/build_sheet.py, simplified to ONE freeze hash.
Assembles a review-only preview from the ledger + pinned versions; confirmation freezes a
content hash of the customer's CHOICES ({key: value}, not provenance labels). Generation runs
only on the frozen revision; a later change of hashed inputs invalidates it.

Writes the build-sheet.json handoff the generation stage reads.
"""
from __future__ import annotations

import hashlib
import json

from . import versions
from .store import Store, now

CONFIRM_LABEL = "Confirm and generate"
REVISE_LABEL = "Revise the proposal"


def _sha16(payload) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def hash_inputs(sheet: dict) -> dict:
    """The fields that identify the agreement — the choices, not the bookkeeping."""
    return {
        "provider": sheet.get("provider"),
        "iac_tool": sheet.get("iac_tool"),
        "build_tier": sheet.get("build_tier"),
        "decisions": sorted(
            ({"key": d["key"], "value": d["value"]} for d in sheet.get("decisions", []) if d.get("value") is not None),
            key=lambda d: d["key"]),
        "versions": sheet.get("versions"),
    }


def assemble(store: Store, mid: str) -> dict:
    mission = store.mission(mid)
    if mission is None:
        raise KeyError(f"unknown mission {mid}")
    decisions = []
    for r in store.ledger_rows(mid):
        cls = "MUST_ASK" if r["origin"] == "MUST_ASK" else ("STATED" if r["origin"] == "STATED" else "DEFAULTED")
        decisions.append({"key": r["key"], "value": r["value"], "decision_class": cls,
                          "source": r["source"], "reversibility": r["reversibility"], "rationale": r["rationale"]})
    decisions.sort(key=lambda d: d["key"])
    must_ask = [d["key"] for d in decisions if d["decision_class"] == "MUST_ASK"]
    sheet = {
        "status": "proposed",
        "mission_id": mid,
        "title": mission["title"],
        "provider": mission["provider"],
        "iac_tool": mission["iac_tool"],
        "build_tier": mission["build_tier"],
        "decisions": decisions,
        "versions": versions.read(store, mid),
        "must_ask": must_ask,
        "blockers": [f"{k} is unsettled (answer or skip it)" for k in must_ask],
        "can_confirm": not must_ask,
        "confirmed_at": None,
        "confirmed_by": None,
        "revision_id": None,
        "sheet_hash": None,
    }
    sheet["sheet_hash"] = _sha16(hash_inputs(sheet))
    return sheet


def confirm(store: Store, mid: str, *, confirmed_by: str) -> dict:
    sheet = assemble(store, mid)
    if not sheet["can_confirm"]:
        raise ValueError("cannot confirm: " + "; ".join(sheet["blockers"]))
    digest = _sha16(hash_inputs(sheet))
    sheet["status"] = "confirmed"
    sheet["confirmed_at"] = now()
    sheet["confirmed_by"] = confirmed_by
    sheet["revision_id"] = f"rev_{digest}"
    sheet["sheet_hash"] = digest
    store.sheet_put(mid, sheet)
    store.set_state(mid, "confirmed", None)
    _write_handoff(store, mid, sheet)
    return sheet


def current_hash_matches(store: Store, mid: str) -> bool:
    frozen = store.sheet_get(mid)
    if not frozen or frozen.get("status") != "confirmed":
        return False
    return frozen.get("sheet_hash") == _sha16(hash_inputs(assemble(store, mid)))


def _write_handoff(store: Store, mid: str, sheet: dict) -> None:
    path = store.data_dir / "handoffs" / mid
    path.mkdir(parents=True, exist_ok=True)
    (path / "build-sheet.json").write_text(json.dumps(sheet, sort_keys=True, indent=2), encoding="utf-8")
