"""Expert capability bundle: the deterministic harness that makes generation secure-by-default.

WHY THIS EXISTS
    Prose skills alone produced a bare bucket that failed five Checkov checks. The model was
    asked to recall best practice instead of being handed it. This module ports the curated,
    sealed V2 rule corpus (cloud-aws-storage / network / data + iac-authoring-common) into a
    lean CE bundle and COMPILES it per mission, so the generator receives the exact security
    rules and craft rules that apply — each with its id, instruction and consequence — rather
    than relying on the model to remember them. Checkov then confirms; it does not drive.

    The rules are data, never model output. `check()` runs the machine-checkable detectors over
    the generated HCL so a rule violation is caught deterministically, independent of the LLM.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import ledger

# Curated from the sealed V2 rule-sets. Each rule: id, instruction, consequence, severity,
# scope (provider/service/tier), and an optional detector the desk can verify on the HCL.
# detector kinds: companion_resource_present | resource_attribute_equals | file_present.
RULES = [
    # --- AWS storage (S3 / KMS) ---
    {"id": "aws.storage.public-access-block", "severity": "high", "service": "storage",
     "scope": {"provider": "aws", "tier": "*"},
     "instruction": "Pair every aws_s3_bucket with an aws_s3_bucket_public_access_block whose four flags "
                    "(block_public_acls, block_public_policy, ignore_public_acls, restrict_public_buckets) are all true.",
     "consequence": "without the block a later ACL or bucket policy can make the bucket world-readable — the most "
                    "common cloud data leak, and the first one Checkov reports",
     "detector": {"kind": "companion_resource_present", "resource_type": "aws_s3_bucket",
                  "companion_type": "aws_s3_bucket_public_access_block"}},
    {"id": "aws.storage.bucket-versioning", "severity": "medium", "service": "storage",
     "scope": {"provider": "aws", "tier": "*"},
     "instruction": "Give every aws_s3_bucket an aws_s3_bucket_versioning resource with versioning_configuration "
                    "status Enabled.",
     "consequence": "an unversioned bucket cannot recover an overwritten or deleted object; a single bad write is permanent",
     "detector": {"kind": "companion_resource_present", "resource_type": "aws_s3_bucket",
                  "companion_type": "aws_s3_bucket_versioning"}},
    {"id": "aws.storage.bucket-encryption", "severity": "high", "service": "storage",
     "scope": {"provider": "aws", "tier": "*"},
     "instruction": "Give every aws_s3_bucket an aws_s3_bucket_server_side_encryption_configuration with "
                    "apply_server_side_encryption_by_default sse_algorithm aws:kms (or AES256 when no key is settled).",
     "consequence": "unencrypted data at rest fails the most basic compliance bar and exposes data if the bucket leaks",
     "detector": {"kind": "companion_resource_present", "resource_type": "aws_s3_bucket",
                  "companion_type": "aws_s3_bucket_server_side_encryption_configuration"}},
    {"id": "aws.storage.bucket-logging", "severity": "medium", "service": "storage",
     "scope": {"provider": "aws", "tier": "standard,enterprise"},
     "instruction": "Give every aws_s3_bucket an aws_s3_bucket_logging resource pointing at a dedicated log bucket.",
     "consequence": "without access logging there is no audit trail of who read or changed the data",
     "detector": {"kind": "companion_resource_present", "resource_type": "aws_s3_bucket",
                  "companion_type": "aws_s3_bucket_logging"}},
    {"id": "aws.storage.kms-key-rotation", "severity": "medium", "service": "storage",
     "scope": {"provider": "aws", "tier": "*"},
     "instruction": "Set enable_key_rotation = true on every aws_kms_key you create, with a key policy granting the "
                    "consuming service principal exactly what it needs.",
     "consequence": "a key that never rotates keeps one piece of key material valid for the life of the data",
     "detector": {"kind": "resource_attribute_equals", "resource_type": "aws_kms_key",
                  "attribute": "enable_key_rotation", "value": "true"}},
    # --- AWS network ---
    {"id": "aws.network.sg-no-open-ingress", "severity": "high", "service": "network",
     "scope": {"provider": "aws", "tier": "*"},
     "instruction": "Never allow ingress from 0.0.0.0/0 on SSH (22) or RDP (3389). Open-world ingress is allowed only "
                    "on a load balancer's HTTP/HTTPS ports. Every security group carries a description.",
     "consequence": "an open management port is a direct remote-compromise path",
     "detector": None},
    # --- AWS data (RDS) ---
    {"id": "aws.data.rds-encrypted", "severity": "high", "service": "data",
     "scope": {"provider": "aws", "tier": "*"},
     "instruction": "Set storage_encrypted = true on every aws_db_instance / aws_rds_cluster.",
     "consequence": "unencrypted database storage fails compliance and exposes data at rest",
     "detector": {"kind": "resource_attribute_equals", "resource_type": "aws_db_instance",
                  "attribute": "storage_encrypted", "value": "true"}},
    {"id": "aws.data.rds-not-public", "severity": "high", "service": "data",
     "scope": {"provider": "aws", "tier": "*"},
     "instruction": "Set publicly_accessible = false on every aws_db_instance; set deletion_protection = true and a "
                    "backup_retention_period >= 7.",
     "consequence": "a public database is an immediate data-breach surface; no backups means no recovery",
     "detector": {"kind": "resource_attribute_equals", "resource_type": "aws_db_instance",
                  "attribute": "publicly_accessible", "value": "false"}},
    # --- AWS compute ---
    {"id": "aws.compute.ec2-imdsv2", "severity": "high", "service": "compute",
     "scope": {"provider": "aws", "tier": "*"},
     "instruction": "On every aws_instance / aws_launch_template set metadata_options http_tokens = required "
                    "(IMDSv2) and encrypt the root volume.",
     "consequence": "IMDSv1 lets an SSRF steal instance credentials; an unencrypted volume leaks data at rest",
     "detector": None},
    # --- HCL craft (every job) ---
    {"id": "hcl.craft.required-version", "severity": "medium", "service": "craft",
     "scope": {"provider": "*", "tier": "*"},
     "instruction": "Pin terraform { required_version } and the provider version in versions.tf, copied from the "
                    "settled ledger pins. Never leave required_version unset.",
     "consequence": "an unpinned stack drifts across terraform/provider versions and fails tflint",
     "detector": None},
    {"id": "hcl.craft.file-split", "severity": "medium", "service": "craft",
     "scope": {"provider": "*", "tier": "*"},
     "instruction": "Split code across versions.tf, providers.tf, variables.tf, main.tf, outputs.tf. providers.tf "
                    "declares the provider with region = var.aws_region and a default_tags block from local.common_tags.",
     "consequence": "a single dumped main.tf is unreadable and unreviewable",
     "detector": None},
    {"id": "hcl.craft.variables-defaults", "severity": "high", "service": "craft",
     "scope": {"provider": "*", "tier": "*"},
     "instruction": "Give every variable a description and a default that lets plan run with no tfvars (a secret takes "
                    "default = null, sensitive = true). Add validation where sensible. Never use an empty string as a "
                    "stand-in for a required value.",
     "consequence": "a variable with no default stops plan before anything can be checked",
     "detector": None},
    {"id": "hcl.craft.default-tags", "severity": "medium", "service": "craft",
     "scope": {"provider": "*", "tier": "*"},
     "instruction": "Carry Project, Environment and ManagedBy in local.common_tags and apply them via provider "
                    "default_tags. Do not add per-resource tags where default_tags covers it.",
     "consequence": "untagged resources are unowned cost and invisible to audit",
     "detector": None},
    {"id": "hcl.craft.no-readme-backend", "severity": "medium", "service": "craft",
     "scope": {"provider": "*", "tier": "*"},
     "instruction": "Do not emit a README.md or a backend block unless the request asks for one. Output blocks accept "
                    "only value, description, sensitive, depends_on, precondition.",
     "consequence": "an unrequested backend points state somewhere the user did not choose",
     "detector": None},
]


def _tier_match(rule_tier: str, tier: str) -> bool:
    return rule_tier == "*" or tier in [t.strip() for t in rule_tier.split(",")]


def select_rules(provider: str, tier: str) -> list[dict]:
    """Deterministic selection: rules whose provider and tier scope match the mission."""
    out = []
    for r in RULES:
        p = r["scope"]["provider"]
        if p not in ("*", provider):
            continue
        if not _tier_match(r["scope"]["tier"], tier):
            continue
        out.append(r)
    return out


def context_block(store, mid: str) -> str:
    """The generation contract: settled ledger + the exact rules that apply, with consequences.

    This is the harness — the generator is handed the rules, not asked to recall them.
    """
    mission = store.mission(mid)
    rules = select_rules(mission["provider"], mission["build_tier"])
    lines = [ledger.prompt_block(store, mid), "",
             f"## Expert rules that apply ({mission['provider']} / {mission['build_tier']}) — apply ALL before validate",
             "These are deterministic requirements, not suggestions. Each names the consequence of ignoring it."]
    for r in rules:
        lines.append(f"- [{r['id']} | {r['severity']}] {r['instruction']}")
        lines.append(f"    why: {r['consequence']}")
    lines += ["", "## Output contract",
              "- Emit versions.tf, providers.tf, variables.tf, main.tf, outputs.tf (flat, relative paths).",
              "- Secure defaults are the floor: encryption, public access blocked, least privilege, tags.",
              "- List every assumption and every unknown that would change the design.",
              "- Never run apply, never reference credentials, never claim a check passed."]
    return "\n".join(lines)


def summary(store, mid: str) -> str:
    """Human-facing high-level design summary: what you get and why, for confirmation before generation."""
    mission = store.mission(mid)
    rules = select_rules(mission["provider"], mission["build_tier"])
    by_service: dict[str, list[str]] = {}
    for r in rules:
        by_service.setdefault(r["service"], []).append(r["id"])
    lines = [f"# Design summary — {mission['title']} ({mid})",
             f"Provider {mission['provider']} · {mission['iac_tool']} · tier {mission['build_tier']}", "",
             "## Settled decisions (from the ledger)"]
    for row in store.ledger_rows(mid):
        if row["origin"] == "MUST_ASK":
            lines.append(f"- MUST ASK: {row['key']} — {row['rationale']}")
        else:
            lines.append(f"- {row['key']} = {row['value']}  [{row['origin']}]")
    lines += ["", "## Security & craft posture that will be applied (deterministic rules)"]
    for service, ids in sorted(by_service.items()):
        lines.append(f"- {service}: " + ", ".join(ids))
    lines += ["", "## Tier trade-off",
              "minimal builds only what the request needs plus the security floor; it deliberately skips "
              "cross-region replication, event notifications and access logging unless asked. A larger tier adds "
              "those. Moving up is a small, informed diff.", "",
              "Confirm the MUST_ASK answers, then generation proceeds. Checkov confirms the result; it does not drive it."]
    return "\n".join(lines)


def _resources(hcl: str) -> dict[str, list[str]]:
    """Map resource type -> list of resource bodies (rough but deterministic)."""
    out: dict[str, list[str]] = {}
    for m in re.finditer(r'resource\s+"([^"]+)"\s+"[^"]+"\s*\{', hcl):
        rtype = m.group(1)
        start = m.end() - 1
        depth, i = 0, start
        while i < len(hcl):
            if hcl[i] == "{":
                depth += 1
            elif hcl[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        out.setdefault(rtype, []).append(hcl[start:i + 1])
    return out


def check(tree: str | Path, provider: str, tier: str) -> list[dict]:
    """Run the machine-checkable detectors over the generated HCL. Deterministic, no LLM.

    Returns one finding per violated rule (id, severity, message). Rules with no detector are
    left to validate/checkov and are not guessed here.
    """
    tree = Path(tree)
    hcl = "\n".join(p.read_text(encoding="utf-8") for p in sorted(tree.glob("*.tf")))
    resources = _resources(hcl)
    findings = []
    for r in select_rules(provider, tier):
        d = r.get("detector")
        if not d:
            continue
        if d["kind"] == "companion_resource_present":
            if resources.get(d["resource_type"]) and not resources.get(d["companion_type"]):
                findings.append({"id": r["id"], "severity": r["severity"],
                                 "message": f"{d['resource_type']} present without {d['companion_type']}"})
        elif d["kind"] == "resource_attribute_equals":
            for body in resources.get(d["resource_type"], []):
                if not re.search(rf'\b{re.escape(d["attribute"])}\s*=\s*{re.escape(d["value"])}\b', body):
                    findings.append({"id": r["id"], "severity": r["severity"],
                                     "message": f"{d['resource_type']} missing {d['attribute']} = {d['value']}"})
                    break
    return findings


def write_bundle(store, mid: str) -> dict:
    """Persist the compiled bundle next to the mission for the generator and the PR body."""
    mission = store.mission(mid)
    rules = select_rules(mission["provider"], mission["build_tier"])
    bundle = {"mission_id": mid, "provider": mission["provider"], "build_tier": mission["build_tier"],
              "rules": [{"id": r["id"], "severity": r["severity"], "instruction": r["instruction"],
                         "consequence": r["consequence"]} for r in rules]}
    path = store.data_dir / "missions" / mid / "capability.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
    return bundle