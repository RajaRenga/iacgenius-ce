# IaC Genius Community Edition

Turn a plain-language infrastructure request into **validated Terraform (or OpenTofu) and a reviewable pull
request**, running on [Hermes Agent](https://github.com/NousResearch/hermes-agent). A deterministic desk holds
the truth; the model proposes, the toolchain decides.

This is the community edition of IaC Genius. It ships **no template catalog**. It grounds on live, read-only
registry knowledge (the HashiCorp Terraform MCP, AWS Knowledge MCP, DeepWiki) and the real provider schema.

## What it does
- Records every input in a decision ledger and asks the must-ask questions before any spend.
- Confirms Terraform and provider versions, then grounds on `terraform providers schema -json` (the truth).
- Injects security posture up front; checkov confirms, it does not drive.
- Repairs within a bounded budget, then escalates to a person. Issues surface on a board with evidence.
- Delivers a PR whose body is the ledger, and reads the commit back.

## What it never does
- Run `terraform apply` / `tofu apply` or call a cloud write API. It proposes; you apply elsewhere.
- Use cloud credentials. Validation needs none.
- Report a scanner that did not run as PASS. NOT_RUN is an honest value.

## Run it
One Spot instance, pinned Hermes, your model key. See `deploy/aws-single/README.md`. The deterministic
toolchain (terraform, tflint, checkov, secret scan) and a shared provider cache are installed once at onboarding
and reused — no per-mission provider downloads.

## Status
Early build. The desk, plugin and board are assembled on the instance from `profiles/iacgenius/BUILD-BRIEF.md`.

## License
Apache-2.0. See LICENSE and NOTICE.