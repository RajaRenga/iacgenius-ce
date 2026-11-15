"""Expert capability bundle: deterministic rule selection, generation context, summary, detectors."""
from iacg_desk import capability, ledger


def test_minimal_excludes_standard_only_rules():
    ids = {r["id"] for r in capability.select_rules("aws", "minimal")}
    assert "aws.storage.bucket-versioning" in ids
    assert "aws.storage.bucket-logging" not in ids  # standard,enterprise only


def test_standard_includes_logging():
    ids = {r["id"] for r in capability.select_rules("aws", "standard")}
    assert "aws.storage.bucket-logging" in ids


def test_provider_filter_keeps_craft_rules():
    ids = {r["id"] for r in capability.select_rules("azure", "minimal")}
    assert not any(i.startswith("aws.") for i in ids)
    assert "hcl.craft.required-version" in ids  # provider '*'


def test_context_block_carries_ledger_and_rules(store, mid):
    ledger.add(store, mid, "aws_region", "us-east-1")
    block = capability.context_block(store, mid)
    assert "aws_region = us-east-1" in block
    assert "aws.storage.public-access-block" in block
    assert "apply ALL before validate" in block


def test_summary_renders_decisions_and_posture(store, mid):
    ledger.add(store, mid, "aws_region", "us-east-1")
    text = capability.summary(store, mid)
    assert "test mission" in text
    assert "aws_region = us-east-1" in text
    assert "storage:" in text


def test_check_flags_bare_bucket(tmp_path):
    (tmp_path / "main.tf").write_text('resource "aws_s3_bucket" "b" {\n  bucket = "demo"\n}\n', encoding="utf-8")
    findings = capability.check(tmp_path, "aws", "minimal")
    ids = {f["id"] for f in findings}
    assert {"aws.storage.public-access-block", "aws.storage.bucket-versioning",
            "aws.storage.bucket-encryption"} <= ids


def test_check_passes_secure_bucket(tmp_path):
    (tmp_path / "main.tf").write_text(
        'resource "aws_s3_bucket" "b" {\n  bucket = "demo"\n}\n'
        'resource "aws_s3_bucket_public_access_block" "b" {\n  bucket = aws_s3_bucket.b.id\n'
        '  block_public_acls = true\n  block_public_policy = true\n'
        '  ignore_public_acls = true\n  restrict_public_buckets = true\n}\n'
        'resource "aws_s3_bucket_versioning" "b" {\n  bucket = aws_s3_bucket.b.id\n'
        '  versioning_configuration {\n    status = "Enabled"\n  }\n}\n'
        'resource "aws_s3_bucket_server_side_encryption_configuration" "b" {\n  bucket = aws_s3_bucket.b.id\n'
        '  rule {\n    apply_server_side_encryption_by_default {\n      sse_algorithm = "aws:kms"\n    }\n  }\n}\n',
        encoding="utf-8")
    findings = capability.check(tmp_path, "aws", "minimal")
    assert not any(f["id"].startswith("aws.storage.") for f in findings)


def test_write_bundle_persists_rules(store, mid):
    bundle = capability.write_bundle(store, mid)
    path = store.data_dir / "missions" / mid / "capability.json"
    assert path.is_file()
    assert bundle["mission_id"] == mid
    assert any(r["id"] == "aws.storage.public-access-block" for r in bundle["rules"])