---
name: iacg-generate
status: candidate
description: The expert generation contract. Consume the compiled capability brief and produce secure-by-default, well-structured Terraform — checkov confirms, it does not drive.
---

# iacg-generate

## Why this exists

Prose alone produced a bare bucket that failed five Checkov checks. The fix is a deterministic
harness: the desk compiles the exact expert security and craft rules that apply to the mission
and hands them to you, each with its consequence. You are not asked to recall best practice —
you are given it. Apply it before the first validate, so checkov confirms quality instead of
catching basics.

## Inputs

Run `iacg_desk brief <mission_id>` FIRST. It returns:
- the settled decision ledger (STATED / SOURCE / DEFAULTED / MUST_ASK),
- the expert rules that apply to this provider and tier, each with an id, instruction and consequence,
- the output contract.

Also ground every resource argument on the pinned binary schema (`iacg_desk schema <provider> <version>
--resource <type>`); never invent an argument the schema does not declare.

## Where to write the code

Write the generated .tf files into the mission's WRITABLE workspace tree: `/data/iacg-work/<mission_id>/`
(the mission `tree` field). NEVER write into `/data/iacg/...` — that is the desk's read-only state and
writes there fail with "Read-only file system". If the mission has no tree yet, create
`/data/iacg-work/<mission_id>/` and use it. Validate with
`iacg_mission action=validate mission_id=<id> tree=/data/iacg-work/<mission_id>`.

## Rules

### Apply every injected rule before the first validate

The brief's rules are requirements, not suggestions. The security floor for AWS:
- **S3**: public-access block (all four flags true), versioning Enabled, server-side encryption
  (aws:kms when a key is settled, else AES256). Access logging and lifecycle when the tier asks.
- **RDS/Aurora**: storage encrypted, not publicly accessible, backup retention, deletion protection.
- **EC2/launch templates**: IMDSv2 required (http_tokens = required), encrypted root volume, no public
  IP unless the request is explicitly public-facing.
- **Security groups**: a description; no open-world ingress except a load balancer's HTTP/HTTPS; never
  SSH/RDP from 0.0.0.0/0.
- **KMS**: key rotation enabled; a key policy granting the consuming principal exactly what it needs.
- **IAM**: least privilege scoped to the resources you created; never wildcard action on wildcard resource.

Apply these to resources the request actually needs. Never add a VPC, subnet or network the request did
not ask for — an unrequested resource is unrequested cost and attack surface.

### Structure the output like an expert

- Split across `versions.tf`, `providers.tf`, `variables.tf`, `main.tf`, `outputs.tf` (flat, relative).
- `versions.tf`: `terraform { required_version }` and the provider pin, copied from the settled ledger.
- `providers.tf`: provider with `region = var.aws_region` and `default_tags` from `local.common_tags`.
- `main.tf` starts with `locals`; `common_tags` carries Project, Environment, ManagedBy.
- Every variable: a description and a default that lets `plan` run with no tfvars (a secret takes
  `default = null`, `sensitive = true`); add validation where sensible. Never an empty string as a
  stand-in for a required value.
- HCL style: NEVER single-line nested blocks. Every nested block opens and closes on its own lines.
- Do not emit a README.md or a backend block unless asked.

### Be honest

- List every assumption you made and every unknown that would change the design.
- A finding that no code change closes is a finding a person decides about — record it, do not add
  infrastructure to silence a scanner.

## After writing

1. `iacg_desk rules-check <mission_id>` — the deterministic expert-rule detectors. Fix every violation.
2. `iacg_desk validate <mission_id>` — the toolchain. Repair within the bounded budget; then a person decides.

## Never

- Run `terraform apply` / `tofu apply`, read a credential, or reach a cloud write API.
- Invent a resource argument the pinned schema does not declare.
- Claim validation passed, that the stack is compliant, or that a finding is resolved. Validators decide.