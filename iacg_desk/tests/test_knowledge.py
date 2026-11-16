from iacg_desk import build_sheet, capability, knowledge, ledger, resolver, versions


def test_remember_renders_okf_card_and_valid_source(store):
    out = knowledge.remember(store, "aws", "region", "eu-west-1", "rajagopal")
    assert out["source"].startswith("knowledge:aws-region@")
    assert ledger.SOURCE_RE.match(out["source"])  # the ledger accepts this resolving source
    card = store.data_dir / "knowledge" / "okf" / "facts" / "aws-region.md"
    assert card.is_file()
    text = card.read_text(encoding="utf-8")
    assert "type: Fact" in text and 'value: "eu-west-1"' in text and "rajagopal" in text


def test_resolver_reuses_knowledge_without_asking(store):
    knowledge.remember(store, "aws", "region", "eu-west-1", "rajagopal")
    mid = store.new_mission("second mission")
    summary = resolver.resolve(store, mid, stated={}, ask=True)
    rows = {r["key"]: r for r in store.ledger_rows(mid)}
    assert rows["region"]["value"] == "eu-west-1"
    assert rows["region"]["origin"] == "SOURCE"
    assert rows["region"]["source"].startswith("knowledge:aws-region@")
    assert "region" not in [q["key"] for q in summary["must_ask"]]


def test_stated_overrides_knowledge(store):
    knowledge.remember(store, "aws", "region", "eu-west-1", "rajagopal")
    mid = store.new_mission("override")
    resolver.resolve(store, mid, stated={"region": "us-east-1"}, ask=True)
    rows = {r["key"]: r for r in store.ledger_rows(mid)}
    assert rows["region"]["value"] == "us-east-1" and rows["region"]["origin"] == "STATED"


def test_confirm_auto_learns_profile_keys(store, mid):
    resolver.resolve(store, mid, stated={"region": "eu-west-1", "naming.prefix": "acme", "environment": "prod"}, ask=False)
    versions.pin(store, mid)
    build_sheet.confirm(store, mid, confirmed_by="rajagopal")
    facts = {f["key"]: f["value"] for f in knowledge.facts(store, "aws")}
    assert facts.get("region") == "eu-west-1"
    assert facts.get("naming.prefix") == "acme"
    assert "environment" not in facts  # per-mission choice, not auto-captured
    m2 = store.new_mission("next")
    resolver.resolve(store, m2, stated={}, ask=True)
    rows = {r["key"]: r for r in store.ledger_rows(m2)}
    assert rows["region"]["value"] == "eu-west-1" and rows["region"]["origin"] == "SOURCE"


def test_brief_includes_knowledge(store, mid):
    knowledge.remember(store, "aws", "region", "eu-west-1", "rajagopal")
    resolver.resolve(store, mid, stated={}, ask=False)
    brief = capability.context_block(store, mid)
    assert "Profile knowledge" in brief and "region = eu-west-1" in brief


def test_forget_and_validation(store):
    knowledge.remember(store, "aws", "region", "eu-west-1", "rajagopal")
    knowledge.forget(store, "aws", "region")
    assert knowledge.lookup(store, "aws", "region") is None
    try:
        knowledge.remember(store, "aws", "region", "not-a-region", "x")
        raise AssertionError("invalid region accepted")
    except ValueError:
        pass
    try:
        knowledge.remember(store, "aws", "target.provider", "aws", "x")
        raise AssertionError("target key accepted as knowledge")
    except ValueError:
        pass