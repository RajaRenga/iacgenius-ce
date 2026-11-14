from conftest import evidence

from iacg_desk import gates


def _pass_hard(store, mid):
    evidence(store, mid, "validate", "PASS", tool="terraform", version="1.15.9")
    evidence(store, mid, "secret_scan", "PASS", tool="iacg-secret-scan", version="0.1.0")


def test_no_evidence_refuses(store, mid):
    gate = gates.delivery_gate(store, mid)
    assert not gate["allowed"]
    assert any("validate" in r and "NOT_RUN" in r for r in gate["reasons"])
    assert any("secret_scan" in r for r in gate["reasons"])


def test_hard_fail_refuses_even_with_approval(store, mid):
    evidence(store, mid, "validate", "FAIL", findings=[{"id": "v:0", "severity": "high", "message": "bad"}])
    evidence(store, mid, "secret_scan", "PASS")
    store.accept(mid, "delivery", "alice", "ship it")
    gate = gates.delivery_gate(store, mid)
    assert not gate["allowed"]
    assert any("validate: FAIL" in r for r in gate["reasons"])


def test_hard_not_run_refuses(store, mid):
    evidence(store, mid, "validate", "PASS")
    evidence(store, mid, "secret_scan", "NOT_RUN", not_run_reason="scanner missing")
    store.accept(mid, "delivery", "alice", "ship it")
    gate = gates.delivery_gate(store, mid)
    assert not gate["allowed"]
    assert any("secret_scan: NOT_RUN" in r for r in gate["reasons"])


def test_missing_human_approval_refuses(store, mid):
    _pass_hard(store, mid)
    gate = gates.delivery_gate(store, mid)
    assert not gate["allowed"]
    assert any("approval" in r for r in gate["reasons"])


def test_pass_plus_approval_allows(store, mid):
    _pass_hard(store, mid)
    store.accept(mid, "delivery", "alice", "reviewed the ledger")
    gate = gates.delivery_gate(store, mid)
    assert gate["allowed"] and gate["approved_by"] == "alice"


def test_soft_findings_need_named_acceptance(store, mid):
    _pass_hard(store, mid)
    evidence(store, mid, "checkov", "FAIL", tool="checkov", version="3.3.16",
             findings=[{"id": "CKV_AWS_18", "severity": "medium", "message": "no access logging"}])
    store.accept(mid, "delivery", "alice", "ship it")
    gate = gates.delivery_gate(store, mid)
    assert not gate["allowed"] and gate["unaccepted_findings"] == ["CKV_AWS_18"]
    store.accept(mid, "CKV_AWS_18", "bob", "logging not needed for this bucket")
    assert gates.delivery_gate(store, mid)["allowed"]