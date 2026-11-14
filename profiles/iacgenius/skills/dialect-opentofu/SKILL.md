---
name: dialect-opentofu
status: candidate
description: The OpenTofu delta from the Terraform baseline. Five things, and no cloud knowledge at all.
---

# dialect-opentofu

## Why this exists

Terraform is the baseline every other procedure is written against. OpenTofu is
compatible with it — same HCL, same providers, same file layout, same security defaults —
so a full dialect procedure would be a copy of the craft skill with five lines changed,
free to drift from it.

This file is only the delta. Everything in `iac-authoring` and in `cloud-<provider>`
applies unchanged, and there is deliberately **no** `dialect-terraform`: a file saying
"do what the baseline says" would exist only to be symmetrical.

## Inputs

The compiled bundle and the job manifest. Nothing here reads cloud state, and nothing here
has an opinion about a cloud.

## Rules

### The file names and the block keyword do not change

OpenTofu reads the block named `terraform`, so `versions.tf` keeps it. Do not rename any
file and do not use a `.tofu` extension. The reference layout every downstream step
assumes is the same layout.

### Use no OpenTofu-only language feature

No state encryption block, no `for_each` on a provider block, no OpenTofu-only function.
The stack must also parse on the Terraform baseline: portability both ways is the reason
this dialect is expressed as a delta rather than as its own baseline, and a stack that
parses on one binary cannot be validated on the other.

### Provider source addresses stay in the `hashicorp` namespace

That address resolves on the OpenTofu registry. Do not rewrite it to an
OpenTofu-namespaced source — the mirror the engine carries is keyed on the original
address, and the engine has no registry access to fall back on.

### The constraint still comes from the manifest, verbatim

Any extra provider a resource needs must be one of
`manifest.target.availableProviders`, at the exact constraint string that map gives. The
OpenTofu mirror carries the same closed set as the Terraform one, and neither is larger
than the other.

### Command names in prose are `tofu`

Any command named in a comment or an output description is `tofu init`, `tofu plan`,
`tofu apply`. You never invoke it yourself; the validation step runs the right binary
against the right workspace and plugin cache.

## What this deliberately does not cover

Cloud security defaults, resource choice, argument shapes, and the provider version
deltas. All four are identical between the two binaries and all four belong to the cloud
procedure and the compiled facts. If this file grows an opinion about one of them, that
is a defect in this file.

## Never

- Run any tool, read a credential, or reach a cloud API.
- Quote a version number or a provider constraint. Both are in the manifest.
- State an account id, a real environment name or a CIDR that was not supplied as an
  input.
- Restate anything the craft or cloud procedure already says.

## Must not claim

- That validation passed, that the stack is compliant, or that a delivery succeeded.
- That a Checkov or tflint finding is resolved, accepted or out of scope.
