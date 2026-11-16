---
name: iacg-intake
status: candidate
description: Phase 1 intake & scope finalize. Lock the target (cloud + IaC tool) at the start, extract only what the user STATED, let the desk settle smart defaults model-free, ask ONE batched durable question for costly/irreversible unknowns, show the build-sheet preview, and freeze it only on the user's explicit confirm.
---

# iacg-intake

## Why this exists

A request arrives as a sentence; a stack needs ~15 settled facts. The wrong way is to interrogate the
user with 100 questions or to let a model silently pick values nobody can audit. The right way: the
user states a few things, the **desk resolver** (no model) settles the rest from the catalogue with
disclosed defaults, and only **costly/irreversible** unknowns earn a question — asked **once, batched**,
with the fallback shown up front. The user confirms a preview; generation runs only on that frozen scope.

## Step 0 — lock the target, announce it first

The mission's cloud and IaC tool are fixed when the mission is created. **At the start of the
conversation say so plainly**, e.g.:

> "Target locked: **AWS + Terraform**. To build for another cloud or for OpenTofu, start a new mission."

If the request names a *different* cloud than the mission's target, do not switch it — say the mission
is built for its target and a different cloud needs a new mission. Never mix providers in one stack.

## Knowledge — conventions remembered across missions

IaCGenius remembers org-level conventions (region, naming prefix, owner tag, retention policy) as
knowledge cards and applies them automatically as disclosed defaults, so the user is **not re-asked**.
Onboarding the user on this is part of intake:

- **Review:** `iacg_mission action=knowledge` (optional `provider=<aws>`) lists what is remembered
  (key = value, who declared it). Show it when the user asks "what do you remember / show my knowledge".
- **Add:** when the user says "remember our region is us-east-1" (or any convention), call
  `iacg_mission action=remember key=region value=us-east-1 by="<the user's name>"` and confirm what was
  saved. Confirming a mission also auto-remembers its org-level choices.
- **Override for ONE mission (special request):** if the user says "this is a special request, I need
  eu-west-1 for this one", extract `region=eu-west-1` as STATED (Step 1) for THIS mission. A stated value
  always beats remembered knowledge, for this mission only — the saved default is **not** changed. Say so
  plainly: "Using eu-west-1 for this mission; your saved default stays us-east-1."
- **Forget:** `iacg_mission action=forget key=region` drops a remembered convention.

Right after the target lock, briefly note the conventions that apply, e.g. "Using your saved region
**us-east-1** — name a different region to override it for this mission." If nothing is remembered yet,
invite the user to declare their conventions once so future missions stop asking.

## Step 1 — extract what the user STATED (your only model job)

Read the request and report **only** the catalogue keys it actually states or unambiguously implies.
**You never choose values.** Leaving a key out is the correct, common answer — the desk supplies it.
Do not infer one key from another (a public website does not state a region).

The 15 keys (accepted values):

| key | accepts |
|---|---|
| target.provider | aws / azure / gcp (locked at creation) |
| target.iac_tool | terraform / opentofu (locked at creation) |
| environment | dev / staging / prod ("production","for our customers"→prod; "a test"→dev) |
| region | free text, must fit the cloud (AWS like us-east-1) |
| network.exposure | public / restricted / private ("internet-facing"→public; "internal only"→private) |
| identity.model | workload_identity / static_credentials |
| data.classification | public / internal / confidential / regulated |
| encryption.key_owner | provider_managed / customer_managed ("our own key"→customer_managed) |
| data.retention_days | free text number |
| availability.target | single_zone / multi_zone / multi_region |
| scale.envelope | low / moderate / high |
| state.backend | remote_managed / remote_object_store / local |
| management.tier | managed / self_managed ("on our own VMs"→self_managed; a managed service states nothing) |
| naming.prefix | free text token |
| tagging.owner | free text token |

## Step 2 — create + resolve (the desk does the deciding)

1. `iacg_mission action=create title="<short>" provider=<aws> iac_tool=<terraform> build_tier=<minimal|standard|enterprise> requirement="<the user's request>"`.
2. `iacg_mission action=resolve mission_id=<id> stated={ "<key>": "<value>", ... }` — pass only the STATED
   keys from Step 1. The desk settles every other key: cheap → disclosed default; costly/irreversible
   with no source → **MUST_ASK** (with a disclosed fallback). It returns `must_ask` (the questions).

## Step 3 — ONE batched ask, durable plain text (not a timed menu)

If `must_ask` is non-empty, present **one** message listing every open question, each with its disclosed
fallback, e.g.:

> A few choices are costly to change later. Answer any, or say "use the defaults" to skip all:
> - **environment** — dev / staging / prod? (if you skip: **dev**)
> - **network.exposure** — public / restricted / private? (if you skip: **private**)
> - **encryption.key_owner** — your own key or the provider's? (if you skip: **provider_managed**)

**Do not use a timed Clarify menu** — it expires (~90s) and a late answer is lost. Plain text in the
chat is durable; the user can answer in their own time. Never fabricate a STATED answer on timeout.

Then fold the answers:
- Answered keys: `iacg_mission action=answer mission_id=<id> key=<k> value=<v>` (one per answer), or
- `iacg_mission action=skip mission_id=<id> answers={ "<k>": "<v>", ... }` — answers the listed keys and
  takes the disclosed default for every other open question. Nothing stays MUST_ASK (no deadlock).

## Step 4 — show the preview (scope finalize)

`iacg_mission action=sheet mission_id=<id>` returns the build sheet: the settled decisions (STATED vs
DEFAULTED + source), the pinned versions, and `can_confirm`. Present it as a short preview of **what
will be built**. If `can_confirm` is false, a question is still open — go back to Step 3.

## Step 5 — freeze only on the user's explicit confirm

Ask: "Confirm this scope and generate? (Confirm / Revise)". **Only when the user explicitly confirms**,
call `iacg_mission action=confirm mission_id=<id> by="<the user's name>"`. This freezes ONE hash of the
agreed choices (`revision_id`). The frozen `build-sheet.json` handoff is what generation reads. If the
user wants changes, revise (answer/re-resolve) and show a new preview — never confirm for them.

## Handoff

The frozen build sheet (`handoffs/<id>/build-sheet.json`) is the scope contract for Phase 2 generation.
The ledger (`handoffs/<id>/ledger.json`) records who decided what (STATED vs DEFAULTED + source).

## Never

- Choose a value for an unstated key; the desk resolver owns defaults.
- Mark STATED anything the user did not say or answer.
- Use a timed menu for the ask; keep it durable plain text.
- Confirm for the user, or change the mission's cloud/tool mid-flight.
- Claim validation passed or delivery succeeded — intake only freezes scope.
