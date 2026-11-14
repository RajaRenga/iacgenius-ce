from iacg_desk import repair


def test_bounded_budget_escalates(store, mid, monkeypatch):
    monkeypatch.delenv("IACG_REPAIR_BUDGET", raising=False)
    assert repair.budget() == 2
    assert repair.record_attempt(store, mid, "fix 1")["allowed"]
    assert repair.record_attempt(store, mid, "fix 2")["allowed"]
    third = repair.record_attempt(store, mid, "fix 3")
    assert not third["allowed"]
    assert third["reason"] == "the_bounded_repair_budget_is_spent"
    mission = store.mission(mid)
    assert mission["state"] == "needs_human"
    assert mission["reason"] == "the_bounded_repair_budget_is_spent"
    assert mission["attempts_spent"] == 2  # never exceeds the ceiling
    # every attempt was recorded; escalation is sticky, never a loop
    assert [r["attempt_number"] for r in store.repairs(mid)] == [1, 2]
    assert not repair.record_attempt(store, mid, "fix 4")["allowed"]


def test_env_ceiling(store, monkeypatch):
    monkeypatch.setenv("IACG_REPAIR_BUDGET", "1")
    mid = store.new_mission("ceiling mission", attempts_allowed=repair.budget())
    assert repair.record_attempt(store, mid)["allowed"]
    assert repair.record_attempt(store, mid)["state"] == "needs_human"