"""Bounded repair: default 2 attempts (env IACG_REPAIR_BUDGET ceiling). Never an unbounded loop."""
from __future__ import annotations

import os

SPENT = "the_bounded_repair_budget_is_spent"
DEFAULT_BUDGET = 2


def budget() -> int:
    try:
        return max(0, int(os.environ.get("IACG_REPAIR_BUDGET", DEFAULT_BUDGET)))
    except ValueError:
        return DEFAULT_BUDGET


def record_attempt(store, mid, note="") -> dict:
    mission = store.mission(mid)
    if mission is None:
        raise KeyError(f"unknown mission {mid}")
    spent, allowed = mission["attempts_spent"], mission["attempts_allowed"]
    if spent >= allowed:
        store.set_state(mid, "needs_human", SPENT)
        return {"allowed": False, "state": "needs_human", "reason": SPENT,
                "attempts_spent": spent, "attempts_allowed": allowed}
    attempt = spent + 1
    store.update_mission(mid, attempts_spent=attempt)
    store.repair_add(mid, attempt, note)
    return {"allowed": True, "attempt_number": attempt, "attempts_spent": attempt, "attempts_allowed": allowed}