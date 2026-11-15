"""Decision ledger: STATED / SOURCE / DEFAULTED / MUST_ASK rows.

Wire shape: contracts/decision-ledger-packet.schema.json. SOURCE rows render as
DEFAULTED with their resolving source (the contract has no fourth class).
MUST_ASK rows must be answered before any generation.
"""
from __future__ import annotations

import json
import re

from . import __version__, catalogue
from .store import now

ORIGINS = ("STATED", "SOURCE", "DEFAULTED", "MUST_ASK")
# DecisionSource pattern from the contract: free text is refused so "best practice" cannot resolve a row.
SOURCE_RE = re.compile(r"^(?:mission_profile:[A-Za-z0-9._-]{1,128}|target_profile:[A-Za-z0-9._-]{1,128}|"
                       r"policy_baseline:[A-Za-z0-9._-]{1,128}@[a-f0-9]{16}|knowledge:[A-Za-z0-9._/-]{1,256}@[a-f0-9]{16}|"
                       r"catalogue:(?:aws|azure|gcp))$")


def add(store, mid, key, value=None, origin="STATED", source=None, rationale="", reversibility=None):
    if origin not in ORIGINS:
        raise ValueError(f"origin must be one of {ORIGINS}")
    if origin == "MUST_ASK":
        if value is not None or source is not None:
            raise ValueError("a MUST_ASK row carries no value or source; ask the human")
        reversibility = reversibility if reversibility in ("costly", "irreversible") else "costly"
    else:
        if value is None:
            raise ValueError(f"{origin} row {key!r} needs a value")
        if origin == "STATED":
            source = "intake_conversation"
        elif not source or not SOURCE_RE.match(source):
            raise ValueError(f"{origin} row {key!r} needs a resolving source (mission_profile:..., knowledge:...@hash, "
                             "catalogue:aws, ...); free text is refused")
        reversibility = reversibility or "cheap"
    rationale = rationale or f"{origin} during intake"
    store.ledger_upsert(mid, key, value, origin, source, rationale, reversibility)


def answer(store, mid, key, value):
    """A human answered a MUST_ASK question: the row becomes STATED."""
    rows = {r["key"]: r for r in store.ledger_rows(mid)}
    if key not in rows:
        raise KeyError(f"no ledger row {key!r} on {mid}")
    store.ledger_upsert(mid, key, value, "STATED", "intake_conversation",
                        "you answered this when asked", rows[key]["reversibility"])


def open_questions(store, mid) -> list[dict]:
    return [r for r in store.ledger_rows(mid) if r["origin"] == "MUST_ASK"]


def generation_ready(store, mid) -> tuple[bool, list[str]]:
    """MUST_ASK gating: no generation token is spent while a question is open."""
    keys = [r["key"] for r in open_questions(store, mid)]
    return (not keys, keys)


def prompt_block(store, mid) -> str:
    mission = store.mission(mid)
    lines = [f"## Decision ledger — {mid} ({mission['title']})",
             f"provider={mission['provider']} iac_tool={mission['iac_tool']} build_tier={mission['build_tier']}"]
    rows = store.ledger_rows(mid)
    must = [r for r in rows if r["origin"] == "MUST_ASK"]
    if must:
        lines.append("MUST_ASK — answer before generation:")
        lines += [f"- {r['key']}: {r['rationale']}" for r in must]
    for origin in ("STATED", "SOURCE", "DEFAULTED"):
        group = [r for r in rows if r["origin"] == origin]
        if group:
            lines.append(f"{origin}:")
            lines += [f"- {r['key']} = {r['value']}" + (f"  ({r['source']})" if origin != "STATED" else "")
                      for r in group]
    return "\n".join(lines)


def packet(store, mid) -> dict:
    """decision-ledger-packet wire shape; rows sorted by key for a stable PR body."""
    mission = store.mission(mid)
    rows = []
    for r in store.ledger_rows(mid):
        row = {"key": r["key"], "reversibility": r["reversibility"], "rationale": r["rationale"]}
        if r["origin"] == "MUST_ASK":
            row["decision_class"] = "MUST_ASK"
        elif r["origin"] == "STATED":
            row.update(decision_class="STATED", value=r["value"], source="intake_conversation")
        else:  # SOURCE / DEFAULTED both resolve from a named source
            row.update(decision_class="DEFAULTED", value=r["value"], source=r["source"],
                       confidence="low" if str(r["source"]).startswith("catalogue:") else "high")
        rows.append(row)
    return {
        "schema_version": "1.0.0", "packet_type": "decision_ledger", "mission_id": mid, "created_at": now(),
        "provenance": {"producer": "iacg_desk.ledger", "producer_version": __version__},
        "provider": mission["provider"], "iac_tool": mission["iac_tool"], "rows": rows,
        "coverage": _coverage(mission, rows),
        "missing_keys": _missing(mission, rows),
    }


def _covered(mission, rows) -> set:
    return {r["key"] for r in rows if r.get("decision_class") in ("STATED", "DEFAULTED")}


def _missing(mission, rows) -> list:
    required = set(catalogue.required_keys(mission["provider"], mission["iac_tool"]))
    asked = {r["key"] for r in rows if r.get("decision_class") == "MUST_ASK"}
    return sorted(required - _covered(mission, rows) - asked)


def _coverage(mission, rows) -> str:
    required = set(catalogue.required_keys(mission["provider"], mission["iac_tool"]))
    asked = {r["key"] for r in rows if r.get("decision_class") == "MUST_ASK"}
    unsettled = required - _covered(mission, rows) - asked
    return "FAIL" if unsettled else "PASS"


def sorted_json(store, mid) -> str:
    return json.dumps(packet(store, mid), sort_keys=True, indent=2)