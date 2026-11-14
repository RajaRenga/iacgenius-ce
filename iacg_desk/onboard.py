"""`iacg onboard`: warm the closed provider set once, confirm, reuse.

Warms the shared TF_PLUGIN_CACHE_DIR, records checksums, extracts the schema OKF,
reports versions + disk used, and writes <data>/onboarding.json. A confirmed record
with unchanged versions is reused, never re-downloaded.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from . import schema_okf, versions
from .store import now
from .validate import default_runner, _version

PROVIDERS = {"aws": "6.58.0"}  # the closed CE provider set


def _disk_used(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _checksums(cache: Path) -> dict:
    out = {}
    for f in sorted(cache.rglob("*")):
        if f.is_file():
            out[f.relative_to(cache).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def onboard(store, runner=None, which=shutil.which, confirmed_by=None) -> dict:
    record_path = store.data_dir / "onboarding.json"
    desired = {"terraform": versions.terraform_version(), "tflint": versions.BASELINE["tflint"],
               "checkov": versions.BASELINE["checkov"],
               "providers": {p: os.environ.get(f"IACG_{p.upper()}_PROVIDER_VERSION", v) for p, v in PROVIDERS.items()}}
    if record_path.is_file():
        try:
            prior = json.loads(record_path.read_text(encoding="utf-8"))
        except ValueError:
            prior = {}
        if prior.get("status") == "CONFIRMED" and prior.get("versions") == desired:
            return {**prior, "reused": True}
    runner = runner or default_runner
    cache = store.data_dir / "plugins"
    cache.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TF_PLUGIN_CACHE_DIR=str(cache), TF_IN_AUTOMATION="1", CHECKPOINT_DISABLE="1")
    observed = {name: _version(runner, which, name) for name in ("terraform", "tflint", "checkov")}
    steps = {}
    if which("terraform") is None:
        steps["warm"] = {"status": "NOT_RUN", "reason": "terraform binary not found; nothing downloaded"}
        for provider, version in desired["providers"].items():
            steps[f"schema:{provider}"] = schema_okf.extract(store, provider, version, runner=runner, which=which)
    else:
        with tempfile.TemporaryDirectory(prefix="iacg-onboard-") as tmp:
            required = "\n".join(
                f"    {p} = {{\n      source = \"{schema_okf.PROVIDER_SOURCE[p]}\"\n      version = \"{v}\"\n    }}"
                for p, v in desired["providers"].items())
            Path(tmp, "main.tf").write_text(f"terraform {{\n  required_providers {{\n{required}\n  }}\n}}\n",
                                            encoding="utf-8")
            rc, out, err = runner(["terraform", f"-chdir={tmp}", "init", "-backend=false", "-input=false"], tmp, env)
        steps["warm"] = ({"status": "PASS"} if rc == 0 else
                         {"status": "NOT_RUN", "reason": f"provider warm-up init failed (exit {rc}): {(err or out).strip()[-300:]}"})
        for provider, version in desired["providers"].items():
            steps[f"schema:{provider}"] = schema_okf.extract(store, provider, version, runner=runner, which=which)
    ok = all(s.get("status") in ("PASS", "EXTRACTED", "CACHE_HIT") for s in steps.values())
    status = ("CONFIRMED" if confirmed_by else "AWAITING_CONFIRMATION") if ok else "NOT_RUN"
    record = {"created_at": now(), "status": status, "versions": desired, "observed_versions": observed,
              "cache_dir": str(cache), "disk_used_bytes": _disk_used(cache), "checksums": _checksums(cache),
              "steps": steps, "confirmed_by": confirmed_by,
              "note": "once, confirm, reuse — every later init reads this cache with the registry off"
                      if ok else "toolchain incomplete; NOT_RUN steps are honest, nothing was fabricated"}
    record_path.write_text(json.dumps(record, sort_keys=True, indent=2), encoding="utf-8")
    return record