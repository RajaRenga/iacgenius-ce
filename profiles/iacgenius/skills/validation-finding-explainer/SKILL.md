---
name: validation-finding-explainer
description: Explain raw validator findings and draft the policy questions a human must answer.
exclusive_role: finding_explanation
---

# validation-finding-explainer

Turns raw validator output into something a person can act on, and names the decisions
that are missing. It stands NEXT TO evidence and never inside it.

## Input
Raw deterministic validator findings (rule id, message, file, line range, severity as
the tool reported it), the artifacts those findings point at, and the tool versions that
produced them. Nothing else.

## Output
For each finding, three things and no more:

1. **What the rule is checking**, in plain language, and what the tool actually saw in
   this code.
2. **What would change if it were addressed** — the concrete effect on the resource, not
   a restatement of the rule text.
3. **A proposed classification**, which is a proposal and is labelled as one:
   - `likely defect` — the code is wrong under any reasonable policy;
   - `missing decision` — the answer depends on a parameter nobody has chosen yet, and
     the proposal must name the parameter (for example: log retention days, key
     management model, permitted public exposure);
   - `likely exception` — the control probably does not apply to this workload, with the
     reason it might not.

For a `missing decision`, it drafts the question a human should be asked: the parameter,
the values in play, and what each choice implies. A drafted question is text for a person
to review — it is never an answer.

## The vocabulary is borrowed, not owned

The classification words deliberately echo the policy baseline's dispositions so the two
can be compared. They are not the same thing. The baseline is versioned, hash-bound, and
human-owned; this skill produces a suggestion that a person may accept, edit, or throw
away. Where they disagree, the baseline is right by construction.

## Never
- Changes a finding's status, severity, or count.
- Marks a finding resolved, waived, or accepted.
- Decides that a control applies or does not apply to a workload.
- Edits, adds to, or reinterprets a policy baseline.
- States that code is compliant, secure, or that validation succeeded.
- Runs a validator, a scanner, or any other tool.
- Delivers anything to GitHub, or asks for a delivery to be approved.
- Rewrites the artifacts — repair proposals come from the authoring skill.
