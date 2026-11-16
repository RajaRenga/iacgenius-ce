"""Model-free decision resolver — catalogue-only (CE v0.1).

Ported from iacgenius-v2 services/workflow/app/decision_resolver.py, simplified to the single
source CE ships today: the decision catalogue. NO MODEL RUNS HERE. The Hermes agent extracts
what the user STATED (one model call, elsewhere) and passes it in; this module settles every
other key by lookup and cites the source. A model never supplies a value for an unstated key.

Balance rule: a CHEAP key is defaulted and disclosed; a COSTLY/IRREVERSIBLE key with no stated
value becomes MUST_ASK (one batched ask) with its fallback disclosed up front. management.tier
is DISCLOSED_NOT_ASKED (managed-first stance). The mission target is locked at creation.

Each call writes the ledger handoff file (handoffs/<mid>/ledger.json) the next stage reads.
"""
from __future__ import annotations

import json

from . import catalogue, knowledge, ledger
from .store import Store, now


def _handoff_dir(store: Store, mid: str):
    path = store.data_dir / "handoffs" / mid
    path.mkdir(parents=True, exist_ok=True)
    return path


def _fits(provider: str, key: str, value: str) -> bool:
    return catalogue.in_domain(key, value) and catalogue.provider_misfit(provider, key, value) is None


def resolve(store: Store, mid: str, stated: dict | None = None, ask: bool = True) -> dict:
    """Settle every catalogue key. STATED wins; the rest default or become MUST_ASK."""
    mission = store.mission(mid)
    if mission is None:
        raise KeyError(f"unknown mission {mid}")
    provider, iac_tool = mission["provider"], mission["iac_tool"]

    existing = {r["key"]: r for r in store.ledger_rows(mid)}
    stated_map = {k: r["value"] for k, r in existing.items() if r["origin"] == "STATED" and r["value"]}
    stated_map.update({k: str(v) for k, v in (stated or {}).items()})

    must_ask: list[dict] = []
    discarded: dict[str, str] = {}
    for key in catalogue.required_keys(provider, iac_tool):
        rev = catalogue.reversibility(key)
        entry = catalogue.key(key)

        if key in catalogue.MISSION_TARGET_KEYS:
            value = mission[catalogue.MISSION_TARGET_KEYS[key]]
            ledger.add(store, mid, key, value, origin="STATED", reversibility=rev,
                       rationale="locked when the mission was created; changing it is a new mission")
            continue

        if key in stated_map:
            value = str(stated_map[key]).strip()
            if _fits(provider, key, value):
                ledger.add(store, mid, key, value, origin="STATED", reversibility=rev,
                           rationale="you said this in the request")
                continue
            discarded[key] = f"{value!r} is not an accepted value for {provider}"

        fact = knowledge.lookup(store, provider, key)
        if fact and _fits(provider, key, fact["value"]):
            ledger.add(store, mid, key, fact["value"], origin="SOURCE",
                       source=knowledge.source_ref(provider, key, fact["value"]), reversibility=rev,
                       rationale="remembered profile fact you declared earlier")
            continue

        fallback = catalogue.catalogue_default(provider, key)
        if ask and catalogue.is_askable(key) and key not in catalogue.DISCLOSED_NOT_ASKED and fallback is not None:
            ledger.add(store, mid, key, origin="MUST_ASK", reversibility=rev,
                       rationale=f"no source supplies this; if you skip we use {fallback}. {entry.why_it_matters}")
            must_ask.append({"key": key, "question": entry.question, "fallback": fallback,
                             "reversibility": rev, "why": entry.why_it_matters})
            continue

        if fallback is not None:
            ledger.add(store, mid, key, fallback, origin="SOURCE", source=f"catalogue:{provider}",
                       reversibility=rev, rationale="disclosed platform default")
            continue
        discarded[key] = "no defensible default"

    summary = _summary(store, mid, must_ask, discarded)
    _write_handoff(store, mid)
    return summary


def apply_answers(store: Store, mid: str, answers: dict | None = None) -> dict:
    """Fold answers into MUST_ASK rows: answered -> STATED, skipped -> disclosed SOURCE default.

    Nothing stays MUST_ASK afterwards (no deadlock); the fallback was disclosed before use.
    """
    mission = store.mission(mid)
    if mission is None:
        raise KeyError(f"unknown mission {mid}")
    provider = mission["provider"]
    answers = {k: str(v) for k, v in (answers or {}).items()}
    for row in store.ledger_rows(mid):
        if row["origin"] != "MUST_ASK":
            continue
        key = row["key"]
        if key in answers and _fits(provider, key, answers[key].strip()):
            ledger.answer(store, mid, key, answers[key].strip())
            continue
        fallback = catalogue.catalogue_default(provider, key)
        if fallback is not None:
            ledger.add(store, mid, key, fallback, origin="SOURCE", source=f"catalogue:{provider}",
                       reversibility=row["reversibility"], rationale="skipped the question; disclosed fallback used")
    summary = _summary(store, mid, [], {})
    _write_handoff(store, mid)
    return summary


def _summary(store: Store, mid: str, must_ask: list, discarded: dict) -> dict:
    rows = store.ledger_rows(mid)
    mission = store.mission(mid)
    required = set(catalogue.required_keys(mission["provider"], mission["iac_tool"]))
    covered = {r["key"] for r in rows if r["origin"] != "MUST_ASK"}
    open_keys = [r["key"] for r in rows if r["origin"] == "MUST_ASK"]
    return {
        "mission_id": mid,
        "generated_at": now(),
        "target": {"provider": mission["provider"], "iac_tool": mission["iac_tool"]},
        "must_ask": must_ask or [{"key": r["key"], "rationale": r["rationale"]} for r in rows if r["origin"] == "MUST_ASK"],
        "open_questions": open_keys,
        "discarded": discarded,
        "coverage": "FAIL" if (required - covered - set(open_keys)) else "PASS",
        "missing_keys": sorted(required - covered - set(open_keys)),
        "counts": {o: sum(1 for r in rows if r["origin"] == o) for o in ("STATED", "SOURCE", "MUST_ASK")},
    }


def _write_handoff(store: Store, mid: str) -> None:
    path = _handoff_dir(store, mid) / "ledger.json"
    path.write_text(ledger.sorted_json(store, mid), encoding="utf-8")
