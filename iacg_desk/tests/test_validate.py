import json

from iacg_desk import ledger, validate

CHECKOV_FAIL = {"results": {"failed_checks": [
    {"check_id": "CKV_AWS_18", "check_name": "S3 access logging", "file_path": "/main.tf", "file_line_range": [1]}]}}


def make_runner(calls, checkov_rc=0):
    def run(args, cwd=None, env=None):
        calls.append(list(args))
        if "--version" in args:
            return 0, {"terraform": "Terraform v1.15.9", "tflint": "TFLint version 0.64.0",
                       "checkov": "3.3.16"}[args[0]], ""
        if "fmt" in args:
            return 0, "", ""
        if "init" in args:
            assert any(a.startswith("-plugin-dir=") for a in args)  # registry off
            assert env["TF_PLUGIN_CACHE_DIR"]
            return 0, "", ""
        if "validate" in args:
            return 0, json.dumps({"valid": True, "diagnostics": []}), ""
        if args[0] == "tflint":
            return 0, json.dumps({"issues": []}), ""
        if args[0] == "checkov":
            return checkov_rc, json.dumps(CHECKOV_FAIL if checkov_rc else {"results": {"failed_checks": []}}), ""
        raise AssertionError(f"unexpected args {args}")
    return run


def test_all_pass_with_versions(store, mid, tree):
    calls = []
    packets = validate.run(store, mid, tree=tree, runner=make_runner(calls), which=lambda n: f"/usr/bin/{n}")
    by_check = {p["check"]: p for p in packets}
    assert set(by_check) == {"fmt", "validate", "tflint", "checkov", "secret_scan"}
    assert all(p["status"] == "PASS" for p in packets)
    assert by_check["validate"]["tool"] == {"name": "terraform", "version": "1.15.9"}
    assert by_check["checkov"]["tool"]["version"] == "3.3.16"
    assert store.mission(mid)["state"] == "validated"
    assert store.latest_evidence(mid)["tflint"]["version"] == "0.64.0"


def test_missing_scanners_are_not_run(store, mid, tree):
    calls = []
    packets = validate.run(store, mid, tree=tree, runner=make_runner(calls),
                           which=lambda n: None if n in ("tflint", "checkov") else f"/usr/bin/{n}")
    by_check = {p["check"]: p for p in packets}
    assert by_check["tflint"]["status"] == "NOT_RUN" and by_check["tflint"]["not_run_reason"]
    assert by_check["checkov"]["status"] == "NOT_RUN"
    assert by_check["validate"]["status"] == "PASS"  # terraform present
    assert not any(a[0] in ("tflint", "checkov") and "--version" not in a for a in calls)


def test_no_terraform_hard_checks_not_run(store, mid, tree):
    packets = validate.run(store, mid, tree=tree, runner=make_runner([]),
                           which=lambda n: None if n == "terraform" else f"/usr/bin/{n}")
    by_check = {p["check"]: p for p in packets}
    assert by_check["fmt"]["status"] == "NOT_RUN" and by_check["validate"]["status"] == "NOT_RUN"


def test_checkov_fail_and_secret_fail(store, mid, tree):
    (tree / "secrets.tf").write_text('locals {\n  aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"\n}\n', encoding="utf-8")
    packets = validate.run(store, mid, tree=tree, runner=make_runner([], checkov_rc=1),
                           which=lambda n: f"/usr/bin/{n}")
    by_check = {p["check"]: p for p in packets}
    assert by_check["checkov"]["status"] == "FAIL"
    assert by_check["checkov"]["findings"][0]["id"] == "CKV_AWS_18"
    assert by_check["secret_scan"]["status"] == "FAIL"
    finding = by_check["secret_scan"]["findings"][0]
    assert "AKIAIOSFODNN7EXAMPLE" not in json.dumps(finding)  # never log the secret value
    assert store.mission(mid)["state"] == "failed"


def test_init_failure_makes_validate_not_run(store, mid, tree):
    def run(args, cwd=None, env=None):
        if "--version" in args:
            return 0, "Terraform v1.15.9", ""
        if "fmt" in args:
            return 0, "", ""
        if "init" in args:
            return 1, "", "could not reach the provider mirror"
        if args[0] in ("tflint", "checkov"):
            return 0, "{}", ""
        raise AssertionError(f"validate must not run after failed init: {args}")
    packets = validate.run(store, mid, tree=tree, runner=run, which=lambda n: f"/usr/bin/{n}")
    v = next(p for p in packets if p["check"] == "validate")
    assert v["status"] == "NOT_RUN" and "init failed" in v["not_run_reason"]


def test_must_ask_gate_before_toolchain(store, mid, tree):
    ledger.add(store, mid, "budget", origin="MUST_ASK")
    try:
        validate.run(store, mid, tree=tree, runner=make_runner([]), which=lambda n: f"/usr/bin/{n}")
        raise AssertionError("validate ran with an open MUST_ASK")
    except ValueError as exc:
        assert "MUST_ASK" in str(exc)