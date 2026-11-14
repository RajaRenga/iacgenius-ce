---
name: iac-authoring
status: candidate
description: How to build a Terraform or OpenTofu stack that reaches plan on the first try, from the settled ledger and the compiled rules.
---

# iac-authoring

## Why this exists

Code that parses perfectly and cannot deploy scores near zero on the axes that matter.
The two heaviest — deployability and architecture correctness — are the two that syntax
rules cannot reach, and the commonest failure of all is a security control that removes
the only network path.

This procedure is HCL craft and nothing else. Cloud specifics live in `cloud-<provider>`,
dialect deltas in `dialect-opentofu`, version facts in the compiled `facts.json`, and
every domain assertion in `rules.json`. If this file develops an opinion about a provider
argument, that is a defect in this file.

## Inputs

The compiled capability bundle and the job manifest, and nothing else: `decisions.json`
(the settled ledger), `rules.json`, `facts.json`, the manifest's `target` block, the
reference files when the job has them, and the user's stated requirement. Sealed tenant
standards reach you as citations in the bundle, by id and hash — read what you are given
and never go looking for more.

## Rules

### The settled decisions are facts, not suggestions

Every entry in `decisions.json` was stated, defaulted from a named source, or asked. Use
the exact value: a value in the ledger and a different value in the code is the failure
this system exists to stop, and a conformance inspector reports each settled decision
SATISFIED, VIOLATED or UNVERIFIABLE against your output. Where one has no obvious
realisation for the resource at hand, say so in your assumptions rather than substituting
a preference.

### Walk connectivity before you stop

Identity to permission to resource. Application to network path to service. Private
resource to private endpoint to DNS zone to network link. Workload to registry to
image-pull permission. Resource to logging path to monitoring destination. Anything that
disables public access must also get the private path replacing it — a hardened service
nothing can reach is an architecture failure as well as a security one.

### The config must survive plan with no tfvars

Every variable gets a default that lets `plan` run. One exception, and it is the only
one — a sensitive value takes `default = null` with `sensitive = true`, is generated with
a `random_password` gated on `count`, is resolved through a `coalesce`, and is stored in
the cloud's own vault service. An empty string is not a region, a project id, a domain or
an image reference; where you have no real value, keep the reference code's default rather
than blanking it. No circular dependencies, and nothing that depends on a resource you
neither created nor accepted as a variable or data source.

### Arguments come from the pinned schema, never from memory

Every argument and nested block must exist in the version named in
`manifest.target.providerLock` — not a newer one you remember, not a deprecated older
form. `facts.json` carries the deltas for exactly these pins; consult it before writing an
argument you are unsure about, and prefer a long-stable argument to a recent one.
Providers are a closed set: `manifest.target.availableProviders` names every one the
engine carries with its exact constraint, and the engine has no registry access, so
anything outside that map fails `init`.

### The syntax that makes validate fail

The only valid escape sequences are `\n \t \r \\ \" \$` — a forward slash needs none, a
literal backslash in a regex needs two. Wrap ANY multi-line `&&`/`||` condition in
parentheses; HCL closes the expression at the newline unless an open paren says otherwise.
A `validation.condition` may reference only its own variable, and `alltrue`/`anytrue` with
a for-expression beats chained `&&` across multi-line `lookup()` calls. An `output` block
accepts only `value`, `description`, `sensitive`, `depends_on` and `precondition` — use a
ternary inside `value` for a conditional one. `can(regex(...))` returns a bool where
`regex(...)` returns a string; `trimspace()` takes the one argument `trim()` does not.
Arguments are separated by newlines, never commas; multi-line strings use a heredoc; and
`fmt` runs for you, so do not spend turns on alignment.

### File layout, and edit fidelity

`versions.tf` (the `terraform {}` block and nothing else), `providers.tf`, `variables.tf`,
`main.tf` (locals, then data sources, then resources in dependency order), `outputs.tf`,
`terraform.tfvars.example`. In that order. Never a real `terraform.tfvars`, never a
`README.md`, no backend block unless the manifest asks for one. snake_case names that
describe a role; one-line comments on non-obvious choices only. When editing, classify
every difference as REQUESTED, REQUIRED_SIDE_EFFECT, UNREQUESTED or DESTRUCTIVE and keep
everything you were not asked to change; an existing resource may disappear only if its
removal was asked for or is technically required by something that was, because silent
deletion of infrastructure is the worst outcome available here.

## Never

- Run any tool, or produce an `apply`, `import`, `state` or `destroy` command.
- Read cloud credentials, cloud APIs or Terraform state.
- Quote a version number — the pins are in the manifest and the deltas in `facts.json`,
  so a version here would be wrong the day the pin moved.
- Contradict a settled decision, or introduce a fourth kind of input the ledger cannot
  account for.

## Must not claim

- That validation passed, that the code is compliant, or that a delivery succeeded.
- That a policy finding is resolved, accepted or out of scope.
