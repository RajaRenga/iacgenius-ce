import json

import pytest

from iacg_desk import cli, server


def test_help_and_commands(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    for cmd in ("onboard", "create", "validate", "board", "approve", "deliver", "serve"):
        assert cmd in help_text


def test_create_answer_board_cli(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("IACG_HOME", str(tmp_path / "data"))
    monkeypatch.delenv("IACG_REPAIR_BUDGET", raising=False)
    tree = tmp_path / "tree"
    tree.mkdir()  # the board is filesystem-grounded: a mission shows only if its tree exists
    assert cli.main(["create", "a bucket", "--requirement", "one private bucket",
                     "--must-ask", "budget", "--tree", str(tree)]) == 0
    created = json.loads(capsys.readouterr().out)
    mid = created["mission_id"]
    assert mid.startswith("m_") and len(mid) == 14
    assert created["generation_ready"] is False and created["must_ask"] == ["budget"]
    assert cli.main(["answer", mid, "budget", "10 USD"]) == 0
    assert json.loads(capsys.readouterr().out)["generation_ready"] is True
    assert cli.main(["status", mid]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["versions"]["terraform"] and status["versions"]["providers"]["aws"] == "6.58.0"
    assert cli.main(["board"]) == 0
    assert mid in capsys.readouterr().out
    assert (tmp_path / "data" / "board.json").is_file()
    assert (tmp_path / "data" / "board.html").is_file()


def test_pickup_packet_flags_missing_tree(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("IACG_HOME", str(tmp_path / "data"))
    assert cli.main(["create", "a bucket", "--tree", str(tmp_path / "gone")]) == 0
    mid = json.loads(capsys.readouterr().out)["mission_id"]
    assert cli.main(["pickup", mid]) == 0
    pkt = json.loads(capsys.readouterr().out)
    assert pkt["tree_exists"] is False
    assert "NOT on disk" in pkt["next_step"] and "Regenerate" in pkt["next_step"]
    assert "ledger" in pkt and "evidence" in pkt and "gate" in pkt
    # with a real tree present, the flag flips
    (tmp_path / "gone").mkdir()
    assert cli.main(["pickup", mid]) == 0
    assert json.loads(capsys.readouterr().out)["tree_exists"] is True


def test_unknown_mission_errors(tmp_path, capsys):
    assert cli.main(["--home", str(tmp_path), "status", "m_000000000000"]) == 2
    assert "unknown mission" in capsys.readouterr().err


def test_socket_execute_allowlist(tmp_path, monkeypatch):
    monkeypatch.setenv("IACG_HOME", str(tmp_path / "data"))
    reply = server.execute(["board"])
    assert reply["rc"] == 0 and "No missions" in reply["stdout"]
    assert server.execute(["serve", "--socket", "x"])["rc"] == 2  # serve is not exposed
    assert server.execute(["apply"])["rc"] == 2
    assert server.execute("board")["rc"] == 2
    assert server.execute([])["rc"] == 2


def test_socket_execute_create_and_bad_args(tmp_path, monkeypatch):
    monkeypatch.setenv("IACG_HOME", str(tmp_path / "data"))
    reply = server.execute(["create", "socket mission"])
    assert reply["rc"] == 0
    assert json.loads(reply["stdout"])["mission_id"].startswith("m_")
    assert server.execute(["status"])["rc"] != 0  # argparse error surfaced, server keeps serving