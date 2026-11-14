---
name: size-enterprise
status: candidate
description: Build for a reviewer who will ask why. Every supporting control the settled decisions call for - and still never a resource added to silence a scanner.
---

# size-enterprise

## Why this exists

Someone asked for this size because a review is waiting: finance, health data, a customer
audit. They need the supporting controls present and the reasoning legible. What they do
not need - and what would fail the review fastest - is a stack that grew by chasing scanner
output until it went quiet.

**Enterprise means a stricter posture, not a bigger pile.** Which controls apply, and with
which values, is in the size's policy baseline and reaches you through `decisions.json`.
Your job is to realise those decisions completely and visibly.

## Inputs

The job manifest and the compiled capability bundle, and nothing else: `decisions.json`
(the settled ledger), `rules.json`, `facts.json`, the manifest's `target` block, the
reference files when the job has them, and the user's stated requirement.

## Rules

### Realise every settled decision, completely

At this size a partially applied decision is the defect. If the ledger settles customer
managed keys, every resource that takes a key takes that key - not most of them. If it
settles a private exposure, the private path is complete: endpoint, DNS, and the link that
makes the name resolve. A hardened service with no route to it is not hardened, it is
broken, and it is the commonest failure of this size.

### Walk the whole chain before you stop

Identity to permission to resource. Application to network path to service. Private
resource to private endpoint to DNS zone to network link. Workload to registry to
image-pull permission. Resource to logging destination. Anything that disables public
access must also gain the private path that replaces it.

### Supporting infrastructure is justified by a decision, never by a finding

You may add the key, the log destination, the endpoint - when a settled decision requires
it. You may not add them because a scanner mentioned them. If a check fails and no settled
decision calls for the resource that would close it, that is an assumption to record and a
question for a person, not a construction. This rule is what separates this size from the
ratchet that burned roughly 53,200 output tokens across three non-converging missions.

### Make the reasoning legible

For each supporting resource, one short comment naming the decision it realises. A reviewer
should be able to read the file and see why each piece is there without opening the ledger.

### Name what you did not do

Close with the checks you could not close and why, each in one sentence. At this size that
list is the most valuable thing you produce, because it is exactly what the review asks
about.

## Never

- Add a resource to make a scanner quiet.
- Substitute your own value for one the ledger settled.
- Quote a provider version, a retention period, a key owner or any other concrete value -
  those are in `decisions.json` and `facts.json` for the job you were handed.
- Claim the result is compliant, verified or ready. Validators decide that.
