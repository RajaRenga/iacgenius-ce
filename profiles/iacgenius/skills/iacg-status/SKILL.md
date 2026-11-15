---
name: iacg-status
status: candidate
description: One-word health/status/onboarding report. When the user says status, health, onboarding, versions, or "how is the desk", return ONE clean report — no complex instruction needed from them.
---

# iacg-status

## Why this exists

The owner should not have to type "Run the desk onboarding (iacg_mission action=onboard) and show me the
full status report". A plain word — `status`, `health`, `onboarding?`, `versions` — must return one clean,
readable report of the desk's health, the toolchain, onboarding, and the missions.

## Trigger

Any of: "status", "health", "onboarding", "onboard?", "versions", "how is the desk", "what's installed",
"is it ready". Do not ask the user to rephrase or to name a tool action.

## What to do

Gather these with the desk tools, then present ONE report:

1. `iacg_mission action=onboard` — returns the onboarding record: status (CONFIRMED / AWAITING_CONFIRMATION),
   `reused` (true means no download), the toolchain versions (terraform / tflint / checkov), the provider pin,
   `disk_used_bytes`, and the schema cache step. This is the toolchain + onboarding health.
2. `iacg_mission action=board` — the mission summary: each mission's id, state, repair spent/allowed,
   disposition, next owner.

## The report (keep it short and legible)

```
IaC Genius desk — status
Toolchain   terraform <v> · tflint <v> · checkov <v>   (all present)
Onboarding  <CONFIRMED/reused> · provider aws <v> · cache <MB> MB · schema <CACHE_HIT/EXTRACTED>
Missions    <n> total
  - <id> [<state>] <title> · repair <spent>/<allowed> · <disposition> · next: <owner>
Ready       <one line: what proves readiness, what is pending, the next action>
```

## Readiness line (always include it)

Name the hard gates that prove validity (validate + secret_scan PASS), separate soft findings as
accept-or-fix recommendations, and give the next action. Never let an aggregate "failed" stand alone:
say which failures are security posture (checkov — fix or accept) versus code correctness (validate or a
tflint ERROR — must fix, never shipped).

## Never

- Make the user type a tool action or a long instruction.
- Re-warm the cache or re-download when onboarding is already CONFIRMED (it returns reused).
- Claim a check passed that did not run. NOT_RUN is honest.