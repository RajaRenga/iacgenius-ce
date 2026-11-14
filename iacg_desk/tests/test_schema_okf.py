import json

from iacg_desk import schema_okf

SCHEMA = {"format_version": "1.0", "provider_schemas": {
    "registry.terraform.io/hashicorp/aws": {"resource_schemas": {
        "aws_s3_bucket": {"block": {"attributes": {"bucket": {"type": "string"}}}}}}}}


def fake_runner(calls):
    def run(args, cwd=None, env=None):
        calls.append(list(args))
        if "init" in args:
            return 0, "", ""
        if "schema" in args:
            return 0, json.dumps(SCHEMA), ""
        raise AssertionError(f"unexpected args {args}")
    return run


def which_ok(name):
    return f"/usr/bin/{name}"


def test_extract_once_then_cache_hit(store):
    calls = []
    first = schema_okf.extract(store, "aws", "6.58.0", runner=fake_runner(calls), which=which_ok)
    assert first["status"] == "EXTRACTED"
    assert schema_okf.cache_path(store, "aws", "6.58.0").is_file()
    assert store.schema_get("aws", "6.58.0")["status"] == "EXTRACTED"
    n = len(calls)
    second = schema_okf.extract(store, "aws", "6.58.0", runner=fake_runner(calls), which=which_ok)
    assert second["status"] == "CACHE_HIT"
    assert len(calls) == n  # no re-extraction on the same version


def test_version_change_re_extracts(store):
    calls = []
    schema_okf.extract(store, "aws", "6.58.0", runner=fake_runner(calls), which=which_ok)
    n = len(calls)
    result = schema_okf.extract(store, "aws", "6.59.0", runner=fake_runner(calls), which=which_ok)
    assert result["status"] == "EXTRACTED" and len(calls) > n
    assert schema_okf.cache_path(store, "aws", "6.58.0").is_file()  # old version kept


def test_missing_binary_is_not_run_never_fabricated(store):
    def no_runner(args, cwd=None, env=None):
        raise AssertionError("must not run anything without the binary")
    result = schema_okf.extract(store, "aws", "6.58.0", runner=no_runner, which=lambda name: None)
    assert result["status"] == "NOT_RUN" and result["reason"]
    assert not schema_okf.cache_path(store, "aws", "6.58.0").exists()
    assert store.schema_get("aws", "6.58.0")["status"] == "NOT_RUN"


def test_failed_extraction_is_not_run(store):
    def failing(args, cwd=None, env=None):
        return 1, "", "provider not available"
    result = schema_okf.extract(store, "aws", "6.58.0", runner=failing, which=which_ok)
    assert result["status"] == "NOT_RUN" and "provider not available" in result["reason"]


def test_excerpts_declared_only(store):
    schema_okf.extract(store, "aws", "6.58.0", runner=fake_runner([]), which=which_ok)
    loaded = schema_okf.load(store, "aws", "6.58.0")
    ex = schema_okf.excerpts(loaded, "aws", ["aws_s3_bucket", "aws_nonexistent"])
    assert "block" in ex["aws_s3_bucket"]
    assert "NOT_FOUND" in ex["aws_nonexistent"]