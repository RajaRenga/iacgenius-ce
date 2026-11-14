"""Pin terraform + provider versions into the ledger; read them back.

The baseline is a DEFAULT, not a cage. The desk detects the installed terraform/tofu
version and keys the schema OKF by the actual provider@version, so a newer binary
(e.g. 1.17.2) is used automatically. Upgrading is a re-onboard at the new version:
the schema OKF re-extracts and the old version's cache is retained for rollback.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

from . import ledger

BASELINE = {"terraform": "1.15.9", "tflint": "0.64.0", "checkov": "3.3.16"}
BASELINE_PROVIDERS = {"aws": "6.58.0"}
SOURCE = "mission_profile:toolchain-baseline"


def detect_terraform_version(iac_tool="terraform") -> str | None:
    """Read the installed binary's version; None if absent or unreadable."""
    binary = "tofu" if iac_tool == "opentofu" else "terraform"
    if shutil.which(binary) is None:
        return None
    try:
        got = subprocess.run([binary, "version", "-json"], capture_output=True, text=True, timeout=30)
        if got.returncode == 0:
            return json.loads(got.stdout).get("terraform_version") or None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return None


def terraform_version(iac_tool="terraform") -> str:
    # explicit override > detected installed binary > baseline default
    override = os.environ.get("IACG_TERRAFORM_VERSION")
    if override:
        return override
    return detect_terraform_version(iac_tool) or BASELINE["terraform"]


def pin(store, mid, terraform=None, providers=None, iac_tool="terraform"):
    terraform = terraform or terraform_version(iac_tool)
    ledger.add(store, mid, "terraform_version", terraform, origin="SOURCE", source=SOURCE,
               rationale="pinned binary version; the binary schema is truth")
    for name, version in (providers or BASELINE_PROVIDERS).items():
        ledger.add(store, mid, f"provider_version_{name}", version, origin="SOURCE", source=SOURCE,
                   rationale="pinned provider version; schema OKF is extracted once per provider@version")


def read(store, mid) -> dict:
    rows = {r["key"]: r["value"] for r in store.ledger_rows(mid)}
    return {"terraform": rows.get("terraform_version"),
            "providers": {k.removeprefix("provider_version_"): v for k, v in rows.items()
                          if k.startswith("provider_version_")}}