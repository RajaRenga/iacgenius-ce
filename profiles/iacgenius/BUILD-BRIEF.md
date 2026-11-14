# BUILD-BRIEF — assemble the IaC Genius CE desk

You are building the deterministic half of IaC Genius CE on this instance. The maintainer feeds the contracts,
skills and toolchain; you assemble the desk, the plugin and the board, then validate end to end. Keep changes
small and test each piece. The PI coding agent may share the work.

## What to build
1. **iacg desk** (`/opt/iacgenius/desk`, a Python package): durable mission state in SQLite under `/data/iacg`.
   - Decision ledger: STATED / SOURCE / DEFAULTED / MUST_ASK, with origin. MUST_ASK asked before any generation.
   - Version pinning: confirm Terraform + provider versions, store them in the ledger.
   - Evidence + gates: run the toolchain, record PASS / FAIL / NOT_RUN with tool name + version. Hard gates:
     `validate` and `secret_scan` must PASS to deliver. Soft findings go to a person, recorded by name.
   - Bounded repair: default 2 attempts (registry ceiling). Exhausted -> `needs_human`, reason
     `the_bounded_repair_budget_is_spent`. Never an endless loop.
   - Delivery: GitHub PR whose body is the ledger, then read the commit back. Key isolated from the agent.
   - A Unix-socket CLI/API the plugin calls (mirror the RGCE desk shape).
2. **iacg-desk plugin** (`profiles/iacgenius/plugins/iacg-desk`): `plugin.yaml` + `__init__.py` with `register(ctx)`.
   - Tools: `iacg_mission` (action=create/status/validate/approve/deliver), `iacg_templates` (ground via MCP).
   - Hooks: `on_session_start` shows the mission board; `pre_tool_call` refuses `terraform apply`/`tofu apply`/cloud writes.
   - Enable it in `config.yaml` once built.
3. **iacg-board dashboard plugin** (`profiles/iacgenius/dashboard-plugins/iacg-board`): serves the issue board the
   desk writes — findings, evidence, attempts spent/allowed, disposition, next owner. Never invent live state.

## Grounding (no template catalog ships)
- Connect read-only MCPs: HashiCorp **Terraform MCP** (7 public read tools, no creds), **AWS Knowledge MCP**, **DeepWiki**.
  Use the RGCE installer pattern (`install-terraform-guidance.sh`): pin the image by digest, enable only read tools.
- The **binary schema is truth**: `terraform providers schema -json` for the pinned provider. MCP docs are guidance.
- **Schema/OKF cache**: at onboarding, extract the provider schema ONCE per provider@version, store it as a versioned
  local knowledge artifact under `/data/iacg/schema/<provider>@<version>.json`. Inject the relevant resource excerpts
  for quick reference during generation/fix. Re-extract only when the version changes. Do not re-run it every call.

## Generation rules
- Inject security up front: the `cloud-aws` posture skill + policy facts enter the generation context. checkov confirms.
- Use exactly one sizing skill per mission (`size-minimal` / `size-standard` / `size-enterprise`), by `build_tier`.
- A resource argument is written only if the pinned binary schema declares it.
- Fix loop: on a validate failure, re-read the failing resource's schema, rewrite only that block, re-validate.
  Adopt a rewrite only if validate still passes and the finding count did not grow.
- Subagents: delegate planner / generator / critic with injected context (ledger, schema, posture, skills). The critic
  advises on intent/risk; the deterministic layer holds the veto.

## Terraform-first, OpenTofu-ready
- One `iac_tool` axis selects the binary (`terraform` or `tofu`). For OpenTofu inject `dialect-opentofu` only.
- MCP, validation, sizing, cloud posture and the provider cache are shared.

## Provider-cache onboarding (once, confirm, reuse)
- `iacg onboard`: warm a closed provider set into one shared `TF_PLUGIN_CACHE_DIR`, verify checksums, extract the
  schema cache, report versions + disk used, and ask the user to confirm. Every later init reads the cache, registry off.
- Baseline to confirm: terraform 1.15.9, aws 6.58.0, tflint 0.64.0, checkov 3.3.16. One AWS provider is ~700 MB; never
  download per mission.

## Contracts and skills
- Contracts: vendored V2 JSON schemas in `contracts/` (task-packet, decision-ledger-packet, validation-packet,
  github-delivery-receipt, human-interrupt-packet). Use them as the wire shape; do not invent new ones.
- Skills: ported V2 PROMOTED skills in `skills/`. Keep their sealed bytes; do not rewrite concrete values into them.

## Validate before you call it done
- Unit-test the desk gates and the bounded-repair escalation. Run one mission end to end: intake -> ground -> generate
  -> validate -> approve -> deliver to a test repo, with read-back. Report failures as prominently as passes.
- State what you did not verify. NOT_RUN is an honest value.

## Boundaries
- Never apply infrastructure or call a cloud write API. No cloud credentials. GitHub key isolated from the agent.
- Do not ship the V1 template catalog. Do not commit secrets. Keep the public repo free of maintainer process.