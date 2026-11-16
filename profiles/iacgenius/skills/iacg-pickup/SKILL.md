---
name: iacg-pickup
status: candidate
description: Resume or finish a mission from ONE deterministic packet. Trigger: "pick up", "continue mission", "resume", "finish this", "where did I leave off", or a board "Continue in chat". Call pickup first; never hunt for files.
---

# iacg-pickup

## Why this exists

Continuing a mission used to burn many tool calls hunting for the tree, ledger and findings — and when
a tree had been lost, the agent searched in vain. The desk now returns the whole picture in one call.
Use it. Do not explore the filesystem to discover state.

## The one rule

**Call `iacg_mission action=pickup mission_id=<id>` FIRST.** It returns a single packet:

- `state`, `target`, `build_tier`, `revision_id`, `confirmed_by`
- `tree` and **`tree_exists`** — whether the generated code is actually on disk
- `ledger` — the settled decisions (key, value, origin, source)
- `evidence` — each check's status, tool, version, findings
- `gate` — allowed, reasons, unaccepted findings
- `repair_budget` — spent / allowed
- **`next_step`** — the exact thing to do next

Read the packet and act on `next_step`. That is the whole flow.

## Branch on `tree_exists`

- **`tree_exists: true`** — the code is on disk. Use `next_step`:
  - correctness gate failed → read the failing check's findings, repair within budget, re-validate;
  - valid but soft findings open → review each, accept by name with a reason or fix, then approve;
  - gate allowed → get a named delivery approval, then deliver a PR or package a ZIP.
- **`tree_exists: false`** — the tree is gone. **Do not search for it.** The frozen ledger and build
  sheet survive in the desk. Tell the user plainly the code was lost, and offer to **regenerate from the
  frozen scope** (`brief` → generate → `validate`). Only regenerate on the user's go-ahead.

## Never

- Search files, read the sqlite, or probe writability to discover state — `pickup` already has it.
- Invent a finding, a decision, or a pass that is not in the packet.
- Accept a finding or approve delivery without the user's explicit named word.
- Run apply or call a cloud write API.