"""Schema OKF: extract `terraform providers schema -json` ONCE per provider@version.

Cache: <data>/schema/<provider>@<version>.json. Re-extract only on version change.
If the binary/provider is absent, record NOT_RUN — never fabricate a schema.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from .validate import default_runner

PROVIDER_SOURCE = {"aws": "hashicorp/aws", "azure": "hashicorp/azurerm", "gcp": "hashicorp/google"}


def cache_path(store, provider, version) -> Path:
    return store.data_dir / "schema" / f"{provider}@{version}.json"


def extract(store, provider, version, iac_tool="terraform", runner=None, which=shutil.which):
    path = cache_path(store, provider, version)
    cached = store.schema_get(provider, version)
    if path.is_file() and cached and cached["status"] == "EXTRACTED":
        return {"status": "CACHE_HIT", "provider": provider, "version": version, "path": str(path),
                "sha256": cached["sha256"]}
    binary = "tofu" if iac_tool == "opentofu" else "terraform"
    if which(binary) is None:
        reason = f"{binary} binary not found; schema not extracted"
        store.schema_put(provider, version, "NOT_RUN", reason=reason)
        return {"status": "NOT_RUN", "provider": provider, "version": version, "reason": reason}
    runner = runner or default_runner
    source = PROVIDER_SOURCE.get(provider, f"hashicorp/{provider}")
    with tempfile.TemporaryDirectory(prefix="iacg-schema-") as tmp:
        Path(tmp, "main.tf").write_text(
            "terraform {\n  required_providers {\n"
            f"    {provider} = {{\n      source = \"{source}\"\n      version = \"{version}\"\n    }}\n  }}\n}}\n",
            encoding="utf-8")
        cache = store.data_dir / "plugins"
        cache.mkdir(parents=True, exist_ok=True)
        import os
        env = dict(os.environ, TF_PLUGIN_CACHE_DIR=str(cache), TF_IN_AUTOMATION="1", CHECKPOINT_DISABLE="1")
        # Use the shared provider cache: init symlinks from it on Linux (no per-mission copy). Do NOT pass
        # -plugin-dir — it disables cache-based installation and demands the provider already be in that dir.
        rc, out, err = runner([binary, f"-chdir={tmp}", "init", "-backend=false", "-input=false"], tmp, env)
        if rc == 0:
            rc, out, err = runner([binary, f"-chdir={tmp}", "providers", "schema", "-json"], tmp, env)
        if rc != 0:
            reason = f"schema extraction failed (exit {rc}): {(err or out).strip()[-300:]}"
            store.schema_put(provider, version, "NOT_RUN", reason=reason)
            return {"status": "NOT_RUN", "provider": provider, "version": version, "reason": reason}
        try:
            schema = json.loads(out)
            assert schema.get("provider_schemas")
        except (ValueError, AssertionError):
            reason = "schema output was not valid provider-schema JSON; nothing cached"
            store.schema_put(provider, version, "NOT_RUN", reason=reason)
            return {"status": "NOT_RUN", "provider": provider, "version": version, "reason": reason}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(schema, sort_keys=True), encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    store.schema_put(provider, version, "EXTRACTED", path=str(path), sha256=digest)
    return {"status": "EXTRACTED", "provider": provider, "version": version, "path": str(path), "sha256": digest}


def load(store, provider, version) -> dict | None:
    path = cache_path(store, provider, version)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def excerpts(schema, provider, resource_types) -> dict:
    """Per-resource schema excerpts for the generation/fix context. Missing types are reported, not invented."""
    source = PROVIDER_SOURCE.get(provider, f"hashicorp/{provider}")
    block = (schema.get("provider_schemas") or {}).get(f"registry.terraform.io/{source}") or {}
    resources = block.get("resource_schemas") or {}
    out = {}
    for rtype in resource_types:
        out[rtype] = resources.get(rtype) if rtype in resources else {"NOT_FOUND": "not declared by the pinned schema"}
    return out