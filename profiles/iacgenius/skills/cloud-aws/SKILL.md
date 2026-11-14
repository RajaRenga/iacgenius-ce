---
name: cloud-aws
status: candidate
description: AWS expertise for a generation job — the security posture that pre-empts findings, and the AWS-specific shapes that fail validate.
---

# cloud-aws

## Why this exists

An AWS stack that passes `validate` and then produces seventeen Checkov findings costs a
fix round, a person's attention, and often a worse stack than one written correctly the
first time. Nearly all of those findings are defaults, and defaults are cheap to apply
before the fact and expensive to retrofit after it.

This procedure is AWS knowledge only. HCL craft is in `iac-authoring`; the OpenTofu
deltas are in `dialect-opentofu`; the machine-checkable assertions are in the compiled
`rules.json` with their ids; the pinned provider's argument deltas are in `facts.json`.

## Inputs

The compiled bundle and the job manifest. `rules.json` carries the AWS rules that matched
this job, each with an id and the consequence of ignoring it — read those first, because
they are the ones a conformance inspector can check.

## Rules

### Apply the security posture silently, before the first validate

Not as a second pass after a scanner complains. These are the defaults a reviewer would
have asked for:

- **S3**: versioning, server-side encryption with a customer-managed key you create, and
  a public-access block with all four flags true.
- **RDS and Aurora**: storage encrypted, not publicly accessible, a backup retention
  window, deletion protection on, tags copied to snapshots.
- **EC2 and launch templates**: IMDSv2 required, encrypted root volume, no public IP
  unless the request is explicitly public-facing.
- **Security groups**: always a description. No open-world ingress except the load
  balancer's HTTP and HTTPS ports. Never SSH or RDP from the whole internet.
- **KMS**: key rotation enabled, and a key policy granting the consuming service
  principal exactly what it needs.
- **IAM**: least privilege scoped to the resources you created. Never a wildcard action
  on a wildcard resource. A service trust policy carries the source-account condition
  that closes the confused-deputy path.
- **CloudWatch log groups**: retention set, taking the number from the settled
  `data.retention_days` decision rather than from a default you chose.
- **Lambda**: tracing configured, a dead-letter queue, and reserved concurrency when the
  request implies a throughput limit.

Apply these to resources the request actually needs. Never add a VPC, a subnet or a
network to an ask that does not require one — an unrequested resource is an unrequested
cost and an unrequested attack surface.

### Some AWS resources reject `tags`

Association and rule resources take no `tags` argument, and adding one is an "argument not
expected here" error that fails `validate` before anything is planned. `facts.json`
carries the current list for the pinned provider. Provider `default_tags` covers
everything that does support tags, so you rarely need a per-resource `tags` argument at
all.

### The file layout is the craft skill's, with two AWS specifics

`providers.tf` declares `provider "aws"` with `region = var.aws_region` and a
`default_tags` block built from `local.common_tags`. No version constraints there — those
live in `versions.tf`, copied verbatim from `manifest.target.providerLock`.

`main.tf` starts with `locals`, and `common_tags` carries Project, Environment and
ManagedBy.

### When a registry module refuses to init, downgrade the module

Never the provider pin. The pin is the platform's decision and the engine's mirror only
carries what the pin names.

## Never

- Run any tool, read a credential, or reach an AWS API.
- Quote a provider version or an argument delta. Those are in `facts.json` for exactly
  the pins this job uses.
- State an account id, a real environment name or a CIDR that was not supplied as an
  input.
- Add infrastructure to close a policy finding. A finding that no code change closes is a
  finding a person decides about.

## Must not claim

- That validation passed, that the stack is compliant, or that a delivery succeeded.
- That a Checkov or tflint finding is resolved, accepted or out of scope.
