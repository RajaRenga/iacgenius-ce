# IaCGenius

IaCGenius for [Hermes Agent](https://github.com/NousResearch/hermes-agent): turn a
plain-language infrastructure request into **validated Terraform/OpenTofu and a reviewable pull request**.
The model proposes; the toolchain decides.

## What it does

- Records every input in a **decision ledger** (STATED / SOURCE / MUST_ASK) and asks the costly or
  irreversible questions before any generation spend. The cloud + IaC tool are **locked at mission creation**.
- Freezes the agreed scope as **one build-sheet hash**; generation runs only on the frozen revision.
- Grounds every resource argument on the **pinned binary provider schema** (`terraform providers schema -json`),
  not on prose. Read-only MCPs (Terraform registry, AWS Knowledge, DeepWiki) are guidance only.
- Runs the deterministic toolchain — `terraform fmt/init/validate`, `tflint`, `checkov`, and a secret scan —
  and records each as evidence with tool + version. A scanner that did not run is `NOT_RUN`, never `PASS`.
- Repairs within a **bounded budget**, then escalates to a person. Soft findings need a **named human acceptance**.
- Packages each mission as one folder (the `.tf` stack plus a separate `work/` provenance folder) and can zip
  it for download. Delivers a PR whose body is the ledger, verified only after read-back.

## Surfaces used

- Tools: `iacg_mission` (structured desk access), `iacg_templates` (read-only grounding guidance).
- Hooks: `on_session_start` (surfaces the mission board snapshot), `pre_tool_call` (the hard boundary below).
- No middleware. No override of Hermes core.

## Disclosure (what it runs and reads)

- Talks to a local **Unix socket** (`/run/iacg/desk.sock`) served by the `iacg_desk` desk service; falls back
  to running `python -m iacg_desk` as a **subprocess** when no socket is configured.
- Reads its own `local.json` (gitignored) and `IACG_*` environment variables for the socket path, data dir and
  Python interpreter. These are **config paths, not secrets**. It reads no credential store.
- The desk service runs the validation toolchain. `terraform init` **fetches providers from the public registry**
  (read-only network) into a shared cache; `tflint`/`checkov` run locally. The secret scan reads the mission tree.
- **Hard-refuses** `terraform apply` / `tofu apply` / `destroy` and cloud **write** commands (`aws`/`gcloud`/`az`/
  `kubectl` writes) at `pre_tool_call`. It holds **no cloud credentials** and never changes cloud state.
- Delivery to GitHub uses a token the desk holds, only after the gates pass and a named human approval; it reads
  the commit back. No other network writes.

## Install

```bash
hermes plugins install iacg-desk
hermes plugins enable iacg-desk
```

The desk service (`iacg_desk`) must be running on the Unix socket, or the `iacg_desk` CLI must be importable
(`PYTHONPATH`). The `iacgenius` profile in the [repo](https://github.com/RajaRenga/iacgenius-ce) wires both.

## Limits

- **Linux only**: the desk API uses `AF_UNIX` and `/run/iacg`, `/data/iacg` paths. The CLI fallback is portable,
  but the service and the pinned toolchain deployment target Linux.
- It **proposes** validated code and a PR; a person applies the infrastructure elsewhere. It never applies.
- Early build (0.1.0). Validation truth comes from the real binaries; the desk never claims a scan it did not run.

Apache-2.0. Part of [IaC Genius Community Edition](https://github.com/RajaRenga/iacgenius-ce).