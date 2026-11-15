---
name: iacg-wrapup
status: candidate
description: Decision guide for unanswered questions + a final summary of finished work. Never invent a value the user did not give; record assumptions honestly and summarize what was asked, assumed, and decided.
---

# iacg-wrapup

## Why this exists

When a question times out or goes unanswered, the agent must NOT "make up a value and move on" as if the
user said it. Every value has an origin: STATED (the user said it), DEFAULTED (a documented default with a
named source), or MUST_ASK (still open). This skill guides that decision and then summarizes the finished
work so the user can see exactly what was asked, what was assumed, and what still needs their call.

## Decision guide — when a question is unanswered or a Clarify prompt times out

1. **Never fabricate a STATED value.** If the user did not give a value, it is not STATED. Do not write a
   guess into the ledger as if the user said it.
2. **MUST_ASK blocks generation.** Costly or irreversible unknowns stay MUST_ASK and block generation
   (`generation_ready=false`) until answered. Do not bypass the gate by inventing an answer.
3. **A timed-out question becomes a flagged DEFAULT, not a silent guess.** If a non-blocking question times
   out and a documented default exists, record it as DEFAULTED with a resolving source
   (e.g. `mission_profile:baseline`, `catalogue:aws`) and a one-line rationale. Tell the user plainly:
   "you didn't answer X, so I defaulted it to Y from <source> — override anytime." If no defensible default
   exists, leave it MUST_ASK and stop; do not invent.
4. **Prefer the ledger's settled values.** A value already in the ledger binds; never substitute a guess.

## Final summary — produce this when work finishes (or on "summary" / "wrap up")

```
Work summary — <mission id> "<title>"
Built        <resources / what was generated, in one or two lines>
Evidence     fmt/validate/tflint/checkov/secret_scan — status + tool@version (NOT_RUN is honest)
Questions
  answered   <key = value (STATED)>
  assumed    <key = value (DEFAULTED from <source>) — flag for review>
  still open <MUST_ASK keys that block generation>
Decisions    <what was decided and why; repair attempts spent/allowed>
Needs you    <named acceptances for soft findings, delivery approval, any assumed value to confirm>
Code         tree path; view with `code <id>` or the Files > missions folder
```

## Never

- Present an assumed value as something the user stated.
- Skip the summary's "assumed" and "still open" sections — those are the point.
- Claim a check passed that did not run, or that a finding is resolved without evidence.