import base64
import json

from conftest import evidence

from iacg_desk import deliver

SHA_BASE, SHA_HEAD = "a" * 40, "b" * 40
DATA = b'resource "aws_s3_bucket" "b" {\n  bucket = "demo"\n}\n'


def ready_mission(store, mid, tree):
    evidence(store, mid, "validate", "PASS", tool="terraform", version="1.15.9")
    evidence(store, mid, "secret_scan", "PASS", tool="iacg-secret-scan", version="0.1.0")
    store.accept(mid, "delivery", "alice", "reviewed the ledger")
    store.update_mission(mid, tree=str(tree))


def make_api(calls, tamper=False, content=None):
    def api(method, path, payload, token):
        calls.append({"method": method, "path": path, "payload": payload})
        assert token == "test-token-not-a-real-secret"
        if method == "GET" and path.endswith("git/ref/heads/main"):
            return 200, {"object": {"sha": SHA_BASE}}
        if method == "POST" and path.endswith("git/refs"):
            return 201, {}
        if method == "PUT" and "/contents/" in path:
            return 201, {"commit": {"sha": SHA_HEAD}}
        if method == "POST" and path.endswith("/pulls"):
            return 201, {"html_url": "https://github.com/o/r/pull/1"}
        if method == "GET" and "git/ref/heads/iacgenius/" in path:
            return 200, {"object": {"sha": SHA_HEAD}}
        if method == "GET" and "/contents/" in path:
            body = content if tamper else DATA
            return 200, {"content": base64.b64encode(body).decode()}
        raise AssertionError(f"unexpected api call {method} {path}")
    return api


def test_no_token_is_not_run(store, mid, tree, monkeypatch):
    monkeypatch.delenv("IACG_GITHUB_TOKEN", raising=False)
    ready_mission(store, mid, tree)
    def no_api(*a):
        raise AssertionError("no GitHub call may happen without a token")
    result = deliver.deliver(store, mid, "o/r", api=no_api)
    assert result["status"] == "NOT_RUN"
    assert store.mission(mid)["state"] != "delivered"
    assert store.receipts(mid)[-1]["status"] == "NOT_RUN"


def test_gate_refusal_before_token(store, mid, tree, monkeypatch):
    monkeypatch.setenv("IACG_GITHUB_TOKEN", "test-token-not-a-real-secret")
    # no evidence, no approval
    result = deliver.deliver(store, mid, "o/r", api=lambda *a: (_ for _ in ()).throw(AssertionError("gate first")))
    assert result["status"] == "REFUSED" and result["reasons"]


def test_verified_only_on_read_back(store, mid, tree, monkeypatch):
    monkeypatch.setenv("IACG_GITHUB_TOKEN", "test-token-not-a-real-secret")
    ready_mission(store, mid, tree)
    calls = []
    result = deliver.deliver(store, mid, "o/r", api=make_api(calls))
    assert result["status"] == "VERIFIED"
    receipt = result["receipt"]
    assert receipt["read_back_verified"] is True
    assert receipt["commit_sha"] == SHA_HEAD
    assert receipt["branch"] == f"iacgenius/{mid}" and receipt["branch"] != "main"
    assert receipt["approval"]["approved_by"] == "alice"
    assert receipt["pr_url"] == "https://github.com/o/r/pull/1"
    assert receipt["written_paths"][0]["path"] == "main.tf"
    assert store.mission(mid)["state"] == "delivered"
    # the PR body is the ledger
    pr_call = next(c for c in calls if c["path"].endswith("/pulls"))
    assert "Decision ledger" in pr_call["payload"]["body"]
    assert json.loads(pr_call["payload"]["body"].split("```json\n")[1].split("\n```")[0])["mission_id"] == mid
    # the token never appears in any output
    assert "test-token-not-a-real-secret" not in json.dumps(result)


def test_tampered_read_back_is_unverified(store, mid, tree, monkeypatch):
    monkeypatch.setenv("IACG_GITHUB_TOKEN", "test-token-not-a-real-secret")
    ready_mission(store, mid, tree)
    result = deliver.deliver(store, mid, "o/r", api=make_api([], tamper=True, content=b"tampered"))
    assert result["status"] == "UNVERIFIED"
    assert result["receipt"]["read_back_verified"] is False
    assert store.mission(mid)["state"] != "delivered"
    assert store.receipts(mid)[-1]["status"] == "UNVERIFIED"