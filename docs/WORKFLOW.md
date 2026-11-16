# Using IaCGenius: from the board to finished work

This is the path you follow as a user. The **board** tells you where each mission stands; **chat** is
where you investigate and make decisions; the **Files tab** is where you read the code and download your
work. Nothing is applied to your cloud automatically — you stay in control of that.

## 1. Read the board

Open the **IaC Board** tab. Each mission card shows:

- **State and disposition** — where it stands (intake, validated, approved, delivered) and whether it is
  blocked, deliverable, or needs you.
- **Evidence** — one chip per check, with the tool and version that ran:
  - `validate` and `secret_scan` are the **hard gates**. When both pass, the code is *valid*. This is what
    proves the stack is sound.
  - `tflint` and `checkov` are **soft** — style and security recommendations. A `checkov FAIL` does *not*
    mean the code is broken; it means there are hardening choices for you to accept or fix.
- **Repair budget** — how many automatic fix attempts were spent out of the allowance.
- **Disposition reasons** — exactly what is still open (e.g. "soft findings need a named acceptance",
  "human delivery approval missing").
- **Readiness & next step** — a plain-language line telling you what to do next.

A card can say `failed` while the code is perfectly valid: that label means "not yet delivered because a
decision is pending", not "the Terraform is wrong". Read the hard gates and the readiness line.

## 2. Investigate a mission

In chat, ask for what you want to see (use the mission id from the card):

- *"Show code m_abc123"* — the generated `versions.tf`, `providers.tf`, `variables.tf`, `main.tf`,
  `outputs.tf`, exactly as written.
- *"Status of m_abc123"* — the evidence, the gate, and what is blocking.
- *"Show the ledger for m_abc123"* — every decision and where it came from (you said it, a disclosed
  default, or a remembered convention).
- *"Show the build sheet for m_abc123"* — the frozen scope and its hash.

Or open the **Files tab** and browse `m_abc123/`: the `.tf` files at the top, and a `work/` folder holding
the ledger, build sheet, evidence, and acceptances — the record of what was decided and who decided it.

## 3. Decide on the findings

- **Correctness** (`validate` or `secret_scan` failed): IaCGenius repairs within the bounded budget and
  re-runs the checks. If it cannot fix something, it stops and asks you.
- **Security soft findings** (`checkov`): review each one. Either fix it, or **accept it by name** with a
  reason — e.g. *"Accept CKV_AWS_18 for m_abc123: access logging is handled by our central bucket."*
  Accepting is a recorded, named decision, not a silent pass.

## 4. Finish up

Once the hard gates pass and the soft findings are decided:

1. **Approve delivery** — *"Approve delivery for m_abc123"* (in your name). This is the human go-ahead.
2. Then either:
   - **Deliver a PR** — *"Deliver m_abc123 to owner/repo."* IaCGenius opens a pull request whose body is
     the decision ledger, and reads the commit back to verify it landed. (Delivery needs a GitHub token
     configured; without one it reports `NOT_RUN` rather than pretending.)
   - **Download your work** — *"Package m_abc123."* This zips the whole mission folder; download it from
     the Files tab and apply it yourself, wherever you like.

IaCGenius never runs `terraform apply`. Applying is always yours to do, elsewhere, after you have reviewed
the diff.

## 5. Pick it up later

Every mission keeps its `work/` folder (decisions, freeze hash, evidence, who accepted what). A later
session reads it to recover exactly where you left off. Change a decision and re-confirm to freeze a new
revision; your remembered conventions (region, naming, owner tag) carry forward unless you override them
for a special request.

## Quick reference

| You want to… | Say in chat |
|---|---|
| See the code | `show code <id>` |
| See evidence + gate | `status <id>` |
| See decisions | `show the ledger for <id>` |
| Accept a soft finding | `accept <finding-id> for <id>: <reason>` |
| Approve delivery | `approve delivery for <id>` |
| Open a PR | `deliver <id> to owner/repo` |
| Download a ZIP | `package <id>` |
| Remember a convention | `remember our region is us-east-1` |
| Review conventions | `show my knowledge` |
| Override for one mission | `special request — use eu-west-1 for this one` |