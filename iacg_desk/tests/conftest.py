import pytest

from iacg_desk.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "data")


@pytest.fixture
def mid(store):
    return store.new_mission("test mission")


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "tree"
    root.mkdir()
    (root / "main.tf").write_bytes(b'resource "aws_s3_bucket" "b" {\n  bucket = "demo"\n}\n')
    return root


def evidence(store, mid, check, status, findings=None, not_run_reason=None, tool="fake", version="1.0.0"):
    packet = {"schema_version": "1.0.0", "packet_type": "validation", "mission_id": mid,
              "created_at": "2026-01-01T00:00:00+00:00",
              "provenance": {"producer": "test", "producer_version": "0"},
              "attempt_number": 1, "check": check, "status": status,
              "tool": {"name": tool, "version": version}}
    if findings:
        packet["findings"] = findings
    if not_run_reason:
        packet["not_run_reason"] = not_run_reason
    store.evidence_add(mid, packet)
    return packet