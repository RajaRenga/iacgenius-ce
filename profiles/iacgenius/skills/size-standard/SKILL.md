---
name: size-standard
status: candidate
description: The platform default. Build the request, the resources it depends on, and the supporting pieces a reviewer expects - no more.
---

# size-standard

## Why this exists

Most requests are neither a throwaway nor a regulated data plane. This is the size for
them, and it is the default because a person who has not thought about posture should get
something defensible rather than something minimal or something enormous.

## Inputs

The job manifest and the compiled capability bundle, and nothing else: `decisions.json`
(the settled ledger), `rules.json`, `facts.json`, the manifest's `target` block, the
reference files when the job has them, and the user's stated requirement.

## Rules

### Build the request, its dependencies, and its operational surface

Beyond what the minimal size would build, add what the resources need in order to be
operated: the log destination they write to, the identity they assume, the network path
they are reached on. Stop there. A thing justified only by "some organisations require it"
belongs to the next size, and the ledger says so when it applies.

### The settled decisions bind, and they are the only source of values

Encryption ownership, retention, availability target, exposure - each is settled in
`decisions.json` from a named source. Read it there. If you find yourself choosing one,
you are doing the resolver's job, and that is a defect.

### One supporting resource per need, not a family

When a control needs a supporting resource, add exactly one that satisfies it. Do not add
its monitoring, then that monitor's alarm, then the topic the alarm publishes to. That
chain is the documented ratchet: it is how a three-resource request grew a WAF and a
delivery stream and stopped converging.

### An unclosable finding is an assumption

Name the check, say in one sentence what closing it would have required, and leave it. The
evidence layer stays honest about it and a person decides.

### Say what enterprise would add

One line each. An inventory, not a recommendation.

## Never

- Add a resource to make a scanner quiet.
- Substitute your own value for one the ledger settled.
- Quote a provider version, a retention period, a key owner or any other concrete value.
- Claim the result is compliant, verified or ready. Validators decide that.
