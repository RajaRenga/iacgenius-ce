"""Deterministic mission pickup — one complete packet so the agent never hunts for state.

Returns the mission's state, whether its tree is actually on disk, the settled ledger, the evidence
and findings, the repair budget, the gate, and the exact next step. If the tree is gone, it says so
up front and points to regeneration from the frozen ledger instead of letting the agent search.
"""
from __future__ import annotations

from pathlib import Path

from . import gates
from .store import Store


def pickup(store: Store, mid: str) -> dict:
    mission = store.mission(mid)
    if mission is None:
        raise KeyError(f"unknown mission {mid}")
    tree = mission.get("tree")
    tree_exists = bool(tree and Path(tree).is_dir())
    evidence = {c: {"status": r["status"], "tool": r["tool"], "version": r["version"],
                    "findings": r["findings"], "not_run_reason": r.get("not_run_reason")}
                for c, r in store.latest_evidence(mid).items()}
    gate = gates.delivery_gate(store, mid)
    sheet = store.sheet_get(mid) or {}
    hard_ok = evidence.get("validate", {}).get("status") == "PASS" and \
        evidence.get("secret_scan", {}).get("status") == "PASS"

    if not tree_exists:
        next_step = ("The generated tree is NOT on disk (lost). The frozen ledger and build sheet survive. "
                     "Regenerate from the frozen scope (brief -> generate -> validate); do not search for the tree.")
    elif not hard_ok:
        next_step = ("A correctness gate has not passed. Read the failing check's findings, repair the code within "
                     "the budget, then re-validate. Correctness must pass before delivery.")
    elif gate["allowed"]:
        next_step = "Ready to deliver. Get a named delivery approval, then deliver a PR or package a ZIP."
    else:
        next_step = ("Code is valid; soft findings need a named human decision. Review each finding, accept by name "
                     "with a reason or fix it, then approve delivery.")

    return {
        "mission_id": mid, "title": mission["title"], "state": mission["state"],
        "target": {"provider": mission["provider"], "iac_tool": mission["iac_tool"]},
        "build_tier": mission["build_tier"],
        "tree": tree, "tree_exists": tree_exists,
        "revision_id": sheet.get("revision_id"), "confirmed_by": sheet.get("confirmed_by"),
        "repair_budget": {"spent": mission["attempts_spent"], "allowed": mission["attempts_allowed"]},
        "ledger": [{"key": r["key"], "value": r["value"], "origin": r["origin"], "source": r["source"]}
                   for r in store.ledger_rows(mid)],
        "evidence": evidence,
        "gate": {"allowed": gate["allowed"], "reasons": gate["reasons"],
                 "unaccepted_findings": gate.get("unaccepted_findings", [])},
        "next_step": next_step,
    }