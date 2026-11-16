import json

import pytest

from iacg_desk import ledger, validate


def test_must_ask_blocks_generation(store, mid):
    ledger.add(store, mid, "data_classification", origin="MUST_ASK", rationale="costly; no source could supply it")
    ready, keys = ledger.generation_ready(store, mid)
    assert not ready and keys == ["data_classification"]


def test_must_ask_blocks_validate(store, mid, tree):
    ledger.add(store, mid, "budget_ceiling", origin="MUST_ASK")
    with pytest.raises(ValueError, match="MUST_ASK"):
        validate.run(store, mid, tree=tree)


def test_answer_unblocks(store, mid):
    ledger.add(store, mid, "budget_ceiling", origin="MUST_ASK")
    ledger.answer(store, mid, "budget_ceiling", "50 USD/month")
    ready, keys = ledger.generation_ready(store, mid)
    assert ready and keys == []
    row = {r["key"]: r for r in store.ledger_rows(mid)}["budget_ceiling"]
    assert row["origin"] == "STATED" and row["value"] == "50 USD/month"


def test_must_ask_carries_no_value_or_source(store, mid):
    with pytest.raises(ValueError):
        ledger.add(store, mid, "k", value="v", origin="MUST_ASK")


def test_source_rows_need_resolving_source(store, mid):
    with pytest.raises(ValueError, match="resolving source"):
        ledger.add(store, mid, "k", "v", origin="SOURCE", source="best practice")
    ledger.add(store, mid, "k", "v", origin="SOURCE", source="mission_profile:baseline")


def test_packet_shape_and_sorted_json(store, mid):
    ledger.add(store, mid, "z_key", "z", origin="STATED")
    ledger.add(store, mid, "a_key", "a", origin="SOURCE", source="catalogue:aws")
    ledger.add(store, mid, "m_key", origin="MUST_ASK")
    pkt = ledger.packet(store, mid)
    assert pkt["packet_type"] == "decision_ledger" and pkt["schema_version"] == "1.0.0"
    # Coverage is computed against the catalogue (Phase 1): arbitrary keys don't cover the required set.
    assert pkt["coverage"] == "FAIL" and pkt["missing_keys"]
    rows = {r["key"]: r for r in pkt["rows"]}
    assert [r["key"] for r in pkt["rows"]] == sorted(rows)
    assert rows["m_key"]["decision_class"] == "MUST_ASK"
    assert "value" not in rows["m_key"] and "source" not in rows["m_key"]
    assert rows["a_key"]["decision_class"] == "DEFAULTED" and rows["a_key"]["confidence"] == "low"
    assert rows["z_key"]["source"] == "intake_conversation"
    assert json.loads(ledger.sorted_json(store, mid))["mission_id"] == mid


def test_prompt_block_lists_questions_first(store, mid):
    ledger.add(store, mid, "region", "eu-west-1", origin="STATED")
    ledger.add(store, mid, "budget", origin="MUST_ASK", rationale="costly")
    block = ledger.prompt_block(store, mid)
    assert "MUST_ASK" in block and "budget" in block and "region = eu-west-1" in block