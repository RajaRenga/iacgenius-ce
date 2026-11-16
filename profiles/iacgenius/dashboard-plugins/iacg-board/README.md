# IaCGenius Board

A web dashboard tab for [Hermes Agent](https://github.com/NousResearch/hermes-agent) showing the IaC Genius
**mission board**: findings, evidence with tool + version, repair attempts spent/allowed, disposition and next
owner. It renders the snapshot the desk writes — it never invents live state.

## What it shows

- One card per mission: state, title, repair budget spent/allowed, disposition, and who acts next.
- The validation evidence behind each mission (which tool ran, its version, PASS / FAIL / NOT_RUN).
- Soft findings awaiting a named human acceptance, separate from correctness bugs that hard-block.

## Surfaces used

- A **web dashboard tab** (`/iacg-board`, positioned after the kanban tab), served by a FastAPI router
  (`plugin_api.py`) that reads the desk's board snapshot.
- Registers **no agent tools, hooks or middleware**. No override of Hermes core.

## Disclosure (what it reads)

- Read-only. It reads the board snapshot (`board.json` / `board.html`) the `iacg-desk` service writes, over the
  local Unix socket or the shared data dir. It makes **no network calls**, runs no subprocess, and stores nothing.
- It reports only what the desk recorded; an empty state is shown until the desk writes a snapshot.

## Install

```bash
hermes plugins install iacg-board
hermes plugins enable iacg-board
```

Requires `iacg-desk` to write the board snapshot. The `iacgenius` profile in the
[repo](https://github.com/RajaRenga/iacgenius-ce) enables both.

## Limits

- **Linux only** (the desk snapshot lives at `/data/iacg`). Shows an empty state until `iacg-desk` writes a board.
- The tab bundle (`dashboard/dist/index.js`, `style.css`) is committed, readable, non-minified source built from
  the dashboard source; it stays inside the Hermes dashboard SDK surface.

Apache-2.0. Part of [IaC Genius Community Edition](https://github.com/RajaRenga/iacgenius-ce).