"""Run the deterministic toolchain over a mission tree; every check becomes an evidence row.

Wire shape: contracts/validation-packet.schema.json. A scanner that cannot run is
NOT_RUN with a reason — never PASS. `runner(args, cwd, env) -> (rc, stdout, stderr)`
and `which(name)` are injectable so tests need no real toolchain.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

from . import __version__, ledger
from .store import now

SECRET_PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b")),
    ("aws-secret-access-key", re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*[A-Za-z0-9/+=]{16,}")),
    ("generic-secret", re.compile(r"(?i)\b(?:password|passwd|api[_-]?key|secret|token)\s*[=:]\s*[\"']?[^\s\"',;]{8,}")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
]


def default_runner(args, cwd=None, env=None):
    proc = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=600)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _version(runner, which, binary):
    if which(binary) is None:
        return None
    try:
        rc, out, err = runner([binary, "--version"], None, None)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    match = re.search(r"\d+\.\d+\.\d+", (out or "") + (err or ""))
    return match.group(0) if match else "unknown"


def _packet(mid, attempt, check, status, tool, version, findings=None, not_run_reason=None, exit_code=None):
    pkt = {"schema_version": "1.0.0", "packet_type": "validation", "mission_id": mid, "created_at": now(),
           "provenance": {"producer": f"iacg_desk.validate.{check}", "producer_version": __version__},
           "attempt_number": attempt, "check": check, "status": status,
           "tool": {"name": tool, "version": version or "unknown"}}
    if findings:
        pkt["findings"] = findings
    if not_run_reason:
        pkt["not_run_reason"] = not_run_reason
    if exit_code is not None:
        pkt["exit_code"] = exit_code
    return pkt


def _finding(fid, message, severity="medium", file=None, line=None, rule_id=None):
    f = {"id": fid, "severity": severity, "message": message[:500]}
    if rule_id:
        f["rule_id"] = rule_id
    if file:
        f["file"] = file
    if line:
        f["line"] = int(line)
    return f


def secret_scan(tree):
    """stdlib secret scanner; reports file+line only, never the secret value."""
    findings = []
    for path in sorted(tree.rglob("*")):
        if not path.is_file() or ".terraform" in path.parts or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line_text in enumerate(text.splitlines(), 1):
            for name, pattern in SECRET_PATTERNS:
                if pattern.search(line_text):
                    findings.append(_finding(f"secret:{name}:{path.relative_to(tree).as_posix()}:{n}",
                                             f"{name} pattern at line {n} (value withheld)", "critical",
                                             path.relative_to(tree).as_posix(), n, name))
    return findings


def _parse_findings(check, out, err):
    """Best-effort structured findings; falls back to one raw finding, never a silent pass."""
    try:
        data = json.loads(out)
    except (ValueError, TypeError):
        return [_finding(f"{check}:raw", (err or out or "tool failed without output").strip()[-500:], "high")]
    findings = []
    if check == "validate":
        for i, d in enumerate(data.get("diagnostics", [])):
            rng = (d.get("range") or {})
            findings.append(_finding(f"validate:{i}", d.get("summary", "") + ": " + d.get("detail", ""),
                                     "high" if d.get("severity") == "error" else "medium",
                                     rng.get("filename"), (rng.get("start") or {}).get("line")))
    elif check == "tflint":
        for i, issue in enumerate(data.get("issues", [])):
            rng = issue.get("range") or {}
            findings.append(_finding(f"tflint:{i}", issue.get("message", ""),
                                     {"error": "high", "warning": "medium"}.get(issue.get("rule", {}).get("severity"), "low"),
                                     rng.get("filename"), (rng.get("start") or {}).get("line"),
                                     (issue.get("rule") or {}).get("id")))
    elif check == "checkov":
        blocks = data if isinstance(data, list) else [data]
        for block in blocks:
            for i, c in enumerate((block.get("results") or {}).get("failed_checks", [])):
                findings.append(_finding(c.get("check_id", f"checkov:{i}"), c.get("check_name", ""), "medium",
                                         c.get("file_path"), (c.get("file_line_range") or [None])[0],
                                         c.get("check_id")))
    return findings or [_finding(f"{check}:raw", (err or out or "tool failed").strip()[-500:], "high")]


def run(store, mid, tree=None, runner=None, which=shutil.which):
    mission = store.mission(mid)
    if mission is None:
        raise KeyError(f"unknown mission {mid}")
    ready, keys = ledger.generation_ready(store, mid)
    if not ready:
        raise ValueError(f"MUST_ASK unanswered: {', '.join(keys)} — ask before generating or validating")
    from pathlib import Path
    tree = Path(tree or mission["tree"] or "")
    if not tree.is_dir():
        raise ValueError(f"mission tree not found: {tree}")
    runner = runner or default_runner
    binary = "tofu" if mission["iac_tool"] == "opentofu" else "terraform"
    attempt = mission["attempts_spent"] + 1
    cache = store.data_dir / "plugins"
    cache.mkdir(parents=True, exist_ok=True)
    # plugin-dir must differ from the cache dir, else init refuses to "install a provider to itself".
    plug = store.data_dir / "plugin-work"
    plug.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TF_PLUGIN_CACHE_DIR=str(cache), TF_IN_AUTOMATION="1", CHECKPOINT_DISABLE="1")
    packets = []

    def record(pkt):
        store.evidence_add(mid, pkt)
        packets.append(pkt)

    tf_version = _version(runner, which, binary)
    if tf_version is None:
        for check in ("fmt", "validate"):
            record(_packet(mid, attempt, check, "NOT_RUN", binary, None,
                           not_run_reason=f"{binary} binary not found"))
    else:
        rc, out, err = runner([binary, "fmt", "-check", "-recursive", str(tree)], None, env)
        record(_packet(mid, attempt, "fmt", "PASS" if rc == 0 else "FAIL", binary, tf_version,
                       [_finding(f"fmt:{i}", f"not formatted: {name.strip()}", "low", name.strip())
                        for i, name in enumerate(out.splitlines()) if name.strip()] if rc else None,
                       exit_code=rc))
        # init: shared provider cache, separate plugin dir => registry off, no per-mission downloads.
        rc, out, err = runner([binary, f"-chdir={tree}", "init", "-backend=false", "-input=false",
                               f"-plugin-dir={plug}"], str(tree), env)
        if rc != 0:
            record(_packet(mid, attempt, "validate", "NOT_RUN", binary, tf_version,
                           not_run_reason=f"init failed (exit {rc}): {(err or out).strip()[-300:]}"))
        else:
            rc, out, err = runner([binary, f"-chdir={tree}", "validate", "-json"], str(tree), env)
            record(_packet(mid, attempt, "validate", "PASS" if rc == 0 else "FAIL", binary, tf_version,
                           _parse_findings("validate", out, err) if rc else None, exit_code=rc))

    for check, binary_name, args in (
            ("tflint", "tflint", ["tflint", "--format", "json", "--chdir", str(tree)]),
            ("checkov", "checkov", ["checkov", "-d", str(tree), "-o", "json", "--quiet"])):
        version = _version(runner, which, binary_name)
        if version is None:
            record(_packet(mid, attempt, check, "NOT_RUN", binary_name, None,
                           not_run_reason=f"{binary_name} binary not found"))
            continue
        try:
            rc, out, err = runner(args, str(tree), env)
        except (OSError, subprocess.SubprocessError) as exc:
            record(_packet(mid, attempt, check, "NOT_RUN", binary_name, version, not_run_reason=str(exc)[:300]))
            continue
        record(_packet(mid, attempt, check, "PASS" if rc == 0 else "FAIL", binary_name, version,
                       _parse_findings(check, out, err) if rc else None, exit_code=rc))

    findings = secret_scan(tree)
    record(_packet(mid, attempt, "secret_scan", "FAIL" if findings else "PASS", "iacg-secret-scan", __version__,
                   findings or None))

    store.update_mission(mid, tree=str(tree))
    statuses = {p["check"]: p["status"] for p in packets}
    if "FAIL" in statuses.values():
        store.set_state(mid, "failed", "one or more checks failed; repair is bounded")
    else:
        store.set_state(mid, "validated", None)
    return packets