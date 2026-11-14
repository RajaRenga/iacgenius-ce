---
name: size-minimal
status: candidate
description: Build the smallest stack that satisfies the request. Do not add infrastructure the request did not ask for.
---

# size-minimal

## Why this exists

Three real missions asking for a three-resource static site burned ~53,200 output tokens
and none converged. The repair loop's only move was to add infrastructure, so a KMS key
arrived, then an IAM policy for the key, then findings on the policy; a WAF arrived, then
a delivery stream to log it, then findings on the stream. Findings went from 12 to 17
between attempts. The stack grew because nobody had said how big it was allowed to be.

This procedure says it. At this size the answer is: **as small as the request allows.**

## Inputs

The job manifest and the compiled capability bundle, and nothing else: `decisions.json`
(the settled ledger), `rules.json`, `facts.json`, the manifest's `target` block, the
reference files when the job has them, and the user's stated requirement.

## Rules

### Build what was asked, and the things it cannot run without

A resource belongs in this stack when the request named it, or when the named resources
cannot function without it - a subnet needs a route to be reachable, a function needs a
role to execute. That is the whole test. "A reviewer might like it" is not the test, and
neither is "a scanner mentions it".

### The settled decisions still bind

Every value in `decisions.json` applies here exactly as it does at any other size. Small
does not mean unencrypted, public, or untagged. If the ledger settles a key, use that
value; a value in the ledger and a different value in the code is the failure this system
exists to stop. Size changes *how much you build*, never *what a settled decision says*.

### A finding you cannot close from the ledger is an assumption, not a construction

When a check would only pass by adding a resource nobody asked for, do not add it. Record
it in your assumptions, in one sentence, naming the check and what closing it would have
cost. A person reading the evidence can then decide to move up a size - which is a
decision they get to make, and cheaply, because the diff is small.

### Prefer the provider's own defaults over new infrastructure

Where a managed default and a hand-built equivalent both satisfy the request, take the
default. The tenant's standards and the size baseline say when that is not enough, and
they say it in `decisions.json` - you do not need to guess it.

### Say what the next size would add

Close with a short list: what a larger size would add to this same request, one line each.
Not a recommendation - an inventory. It is what makes moving up an informed act instead of
a shot in the dark.

## Never

- Add a resource to make a scanner quiet.
- Substitute your own value for one the ledger settled.
- Quote a provider version, a retention period, a key owner or any other concrete value -
  those are in `decisions.json` and `facts.json` for the job you were handed.
- Claim the result is compliant, verified or ready. Validators decide that.
