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

- List every assumption you made and every unknown that would change the design — but put them in a
  separate `assumptions.md` (markdown) or as `#` comment lines. NEVER write prose, markdown bullets, or an
  "Assumptions" section as raw text inside a `.tf` file: raw prose breaks `terraform validate`.
- A finding that no code change closes is a finding a person decides about — record it, do not add
  infrastructure to silence a scanner.

### References, required args, secrets (field-learned hard rules)

- Every resource reference is THREE parts: `<type>.<name>.<attribute>` (e.g. `aws_instance.app.private_ip`).
  NEVER `<type>.<attribute>` (e.g. `aws_instance.private_ip`) — that is a reference to an undeclared resource.
- Include EVERY required argument the pinned schema declares (e.g. `aws_kms_alias.target_key_id`). Check the
  schema excerpt before writing each resource.
- Never hardcode a secret/password/token. Use a variable with `sensitive = true` and `default = null`.
- Close every block you open; never leave a truncated/unclosed block at end of file.
- Mark any output whose value contains sensitive data with `sensitive = true` (terraform rejects
  unmarked sensitive outputs).
- NEVER create a dependency cycle. A resource policy that references a resource which references back
  is a cycle (e.g. S3 bucket policy ↔ CloudFront distribution ↔ KMS; SQS queue ↔ its DLQ redrive; API
  Gateway resource policy ↔ the REST API). Break cycles: scope a bucket/service policy with an account or
  ARN-string condition instead of a resource reference that loops back, attach the policy as a separate
  resource that depends on (not references) the target, or omit the mutual redrive/policy link. Run
  `terraform validate` mentally for cycles before finishing.
- When the request describes deploying into a VPC/subnets (e.g. "RDS in private subnets", "Lambda in a
  VPC"), CREATE the VPC and subnets it needs — they are part of the request. Reference the created
  `aws_subnet` resources (directly or via a local that resolves to them). Only use existing-subnet data
  sources when the request explicitly says to use existing/pre-existing subnets.

## After writing

1. `iacg_desk rules-check <mission_id>` — the deterministic expert-rule detectors. Fix every violation.
2. `iacg_desk validate <mission_id>` — the toolchain. Repair within the bounded budget; then a person decides.

## Pitfalls (field-learned)

- Grounding is socket-exposed on `iacg_mission`: `action=schema` (provider + version + resource[] →
  per-resource excerpts from the cached binary provider schema OKF, with sha256; binary schema is truth,
  MCP is guidance), `action=brief` (mission_id → settled ledger + applicable expert rules + output
  contract), `action=rules-check` (mission_id → deterministic expert-rule violations over the mission
  tree). Prefer these over CLI/registry fallbacks. If a deployment lacks them, say NOT_RUN honestly,
  ground arguments on read-only registry docs at the EXACT pinned provider version, and let `validate`
  (real binary) arbitrate the schema.
- `rules-check` returning 0 violations does NOT mean the mission passes: checkov soft findings (e.g. KMS
  root delegation, ledger-vs-scanner retention conflicts) are separate and still need named human
  acceptance. Check `status` evidence + gate before claiming anything.
- Full checkov finding text (id, message, file, line, severity) lives in `/data/iacg/board.json`; the
  sqlite auto-extract truncates the findings cells, and grep on the raw .sqlite3 misses binary-stored text.
- A KMS key policy's root-delegation statement (`kms:*` on `*`) trips CKV_AWS_109/111/356. In a key policy
  `*` means THIS key; this is the AWS-standard pattern — propose named acceptance, do not narrow root
  delegation below the AWS default to silence the scanner.
- Checkov findings that conflict with a frozen ledger value (e.g. retention 30d vs CKV_AWS_338's 365d) are
  human decisions: accept the ledger value or revise+re-confirm the sheet. Never silently change a settled value.
- `approve` needs the human's name in their own words. A timed-out clarify leaves findings UNACCEPTED —
  never record an acceptance under a name inferred from another mission; stop and report the open decisions.

## Never

- Run `terraform apply` / `tofu apply`, read a credential, or reach a cloud write API.
- Invent a resource argument the pinned schema does not declare.
- Claim validation passed, that the stack is compliant, or that a finding is resolved. Validators decide.