---
name: iacg-risk
status: candidate
description: Risk rubric for a mission's findings. Separates code-correctness bugs (never ship) from security posture (fix or accept) from style (advisory). Trigger: risk, rubric, "is it safe", "what's blocking".
---

# iacg-risk

## Why this exists

An aggregate "failed" with many FAIL chips reads as broken code. It is not. The owner needs a clear risk
rubric: a checkov finding is a security policy choice (fix or accept), but a tflint ERROR may be a real code
bug. Show that the code is usable with accepted security findings — and that a known bug/error is NEVER shipped.

## Trigger

"risk", "risk <mission_id>", "rubric", "is it safe", "is the code good", "what's blocking", "why failed".
If no mission_id is given, use the most recent mission (from `iacg_mission action=board`).

## What to do

1. `iacg_mission action=status mission_id=<id>` — read the evidence (each check's status, tool@version,
   and findings with severity) and the delivery gate.
2. Classify EVERY finding into one of three risk classes:

| Class | What lands here | Meaning | Gate |
|---|---|---|---|
| CORRECTNESS | validate FAIL/NOT_RUN; secret_scan FAIL; tflint ERROR-severity (invalid/removed argument, type error) | the code is broken or unsafe to run | HARD BLOCK — must fix, never ship |
| SECURITY POSTURE | checkov findings (encryption, logging, public access, replication, ...) | code is structurally valid; hardening is a policy choice | fix OR accept-by-name with a reason |
| STYLE / ADVISORY | tflint WARNING-severity (naming, unused var); fmt | cosmetic / best practice | non-blocking |

3. State the readiness verdict explicitly:
   - USABLE (with decisions): validate PASS + secret_scan PASS + no tflint ERROR. The code is correct;
     remaining checkov findings are accept-or-fix decisions. Name them and the next action.
   - BLOCKED (bug): any CORRECTNESS finding. Name the exact bug and that it must be fixed before delivery.
     Never present this code as ready.

## The report (keep it legible)

```
Risk rubric — <id> "<title>"
Correctness   <validate/secret_scan/tflint-ERROR findings, or "clear — code is valid">
Security      <checkov findings: id, severity, one-line meaning>  → fix or accept-by-name
Style         <tflint warnings / fmt, or "none">
Verdict       <USABLE pending N security decisions | BLOCKED by correctness bug>
Next action   <the concrete step: accept <ids> by name, or fix <bug>, or bounded repair>
```

## Never

- Let an aggregate "failed" stand alone — always name which tier each failure is.
- Call a checkov security finding a code bug, or a tflint ERROR mere style.
- Claim code with a CORRECTNESS finding is ready to ship.
- Accept a finding yourself — acceptance is a named human decision.