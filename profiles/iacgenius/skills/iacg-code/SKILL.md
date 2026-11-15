---
name: iacg-code
status: candidate
description: Show the generated Terraform for a mission so the user can explore it. Trigger: code, "show code", "view code <id>", "explore the code", "what did you generate".
---

# iacg-code

## Why this exists

The mission detail shows a tree path but the user cannot see the code. "How they even try? Where is the
code they can explore it?" This skill surfaces the actual generated .tf files for a mission, on demand.

## Trigger

"code", "show code", "view code", "view code <mission_id>", "explore the code", "what did you generate",
"show the terraform". If no mission_id is given, use the most recent mission (from `iacg_mission action=board`).

## What to do

1. `iacg_mission action=status mission_id=<id>` — read the mission's `tree` path (e.g. /data/iacg/e2e-mission).
2. List the `.tf` files in that tree (search_files or a directory listing via the file toolset).
3. Read each `.tf` file (read_file) and show its full content, labelled by filename, in a fenced hcl block.
   Order: versions.tf, providers.tf, variables.tf, main.tf, outputs.tf, then any others.
4. Close with one line: where the tree lives on disk and how to validate it (`iacg_mission action=validate`).

## The report

```
Generated code — <id> "<title>"  (tree: <path>)

── versions.tf ──
<hcl>
── providers.tf ──
<hcl>
── main.tf ──
<hcl>
...
Validate: iacg_mission action=validate mission_id=<id>
```

## Never

- Invent or paraphrase the code — show the exact file bytes.
- Run apply or modify the files when asked only to view.
- Hide a file because it is short; show every .tf in the tree.