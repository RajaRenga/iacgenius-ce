"""Plugin unit tests: the hard apply/cloud-write boundary, registration, board briefing."""
import importlib.util
import json
from pathlib import Path

import pytest

PLUGIN_PATH = Path(__file__).resolve().parents[2] / "profiles" / "iacgenius" / "plugins" / "iacg-desk" / "__init__.py"
spec = importlib.util.spec_from_file_location("iacg_desk_plugin", PLUGIN_PATH)
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


@pytest.mark.parametrize("command", [
    "terraform apply",
    "terraform apply -auto-approve",
    "tofu apply -auto-approve",
    "cd infra && terraform apply -target=aws_s3_bucket.b",
    "terraform destroy -auto-approve",
    "aws ec2 run-instances --image-id ami-123",
    "aws s3api put-bucket-acl --bucket x --acl public-read",
    "aws iam create-user --user-name x",
    "aws s3 cp local.txt s3://bucket/x",
    "gcloud compute instances create vm1",
    "az group create --name x --location westeu",
    "kubectl apply -f manifest.yaml",
])
def test_refuses_apply_and_cloud_writes(command):
    assert plugin.refused_command(command)
    verdict = plugin.on_pre_tool_call(tool_name="terminal", args={"command": command})
    assert verdict and verdict["action"] == "block"
    assert "REFUSED" in verdict["message"]


@pytest.mark.parametrize("command", [
    "terraform plan",
    "terraform validate",
    "terraform fmt -check",
    "tofu init",
    "aws ec2 describe-instances",
    "aws s3 ls",
    "aws sts get-caller-identity",
    "gcloud compute instances list",
    "ls -la",
])
def test_allows_reads_and_proposals(command):
    assert plugin.refused_command(command) is None
    assert plugin.on_pre_tool_call(tool_name="terminal", args={"command": command}) is None


def test_non_shell_tools_pass():
    assert plugin.on_pre_tool_call(tool_name="read_file", args={"path": "main.tf"}) is None


class FakeCtx:
    def __init__(self):
        self.tools, self.hooks = {}, {}

    def register_tool(self, name, **kw):
        self.tools[name] = kw

    def register_hook(self, name, fn, **kw):
        self.hooks[name] = fn


def test_register():
    ctx = FakeCtx()
    plugin.register(ctx)
    assert set(ctx.tools) == {"iacg_mission", "iacg_templates"}
    assert set(ctx.hooks) == {"on_session_start", "pre_tool_call"}
    enum = ctx.tools["iacg_mission"]["schema"]["parameters"]["properties"]["action"]["enum"]
    assert enum == list(plugin.ACTIONS)  # the schema enum tracks the dispatch actions
    assert {"create", "confirm", "validate", "package", "schema"} <= set(enum)


def test_mission_action_validation():
    assert "Unknown action" in plugin.handle_mission({"action": "apply"})
    assert "mission_id" in plugin.handle_mission({"action": "status"})
    assert "by" in plugin.handle_mission({"action": "approve", "mission_id": "m_1"})


def test_templates_is_read_only_guidance():
    out = plugin.handle_templates({"query": "private s3 bucket"})
    assert "read-only" in out and "schema" in out and "private s3 bucket" in out


def test_session_start_surfaces_board(tmp_path, monkeypatch):
    monkeypatch.setenv("IACG_HOME", str(tmp_path))
    monkeypatch.setenv("IACG_SOCKET", "")
    (tmp_path / "board.json").write_text(json.dumps({
        "generated_at": "2026-01-01T00:00:00+00:00",
        "missions": [{"id": "m_abc123abc123", "state": "needs_human", "title": "a bucket",
                      "attempts": {"spent": 2, "allowed": 2}, "disposition": "needs_human",
                      "next_owner": "human"}]}), encoding="utf-8")
    result = plugin.on_session_start()
    assert result and "m_abc123abc123" in result["context"] and "2/2" in result["context"]


def test_session_start_without_board_is_quiet(tmp_path, monkeypatch):
    monkeypatch.setenv("IACG_HOME", str(tmp_path))
    assert plugin.on_session_start() is None