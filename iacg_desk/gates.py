"""Hard gates: validate and secret_scan must PASS to deliver.

Soft findings (fmt/tflint/checkov) go to a human, accepted by name. Any hard
FAIL or NOT_RUN refuses delivery — missing evidence is never PASS.
"""
from __future__ import annotations

HARD = ("validate", "secret_scan")
SOFT = ("fmt", "tflint", "checkov")
DELIVERY_SCOPE = "delivery"


def delivery_gate(store, mid) -> dict:
    mission = store.mission(mid)
    if mission is None:
        return {"allowed": False, "reasons": [f"unknown mission {mid}"]}
    latest = store.latest_evidence(mid)
    reasons = []
    for check in HARD:
        row = latest.get(check)
        if row is None:
            reasons.append(f"hard gate {check}: NOT_RUN (no evidence)")
        elif row["status"] != "PASS":
            reasons.append(f"hard gate {check}: {row['status']}"
                           + (f" ({row['not_run_reason']})" if row.get("not_run_reason") else ""))
    accepted = {a["scope"] for a in store.acceptances(mid)}
    unaccepted = []
    for check in SOFT:
        row = latest.get(check)
        if row and row["status"] == "FAIL":
            for finding in row["findings"]:
                if finding["id"] not in accepted:
                    unaccepted.append(finding["id"])
    if unaccepted:
        reasons.append("soft findings need a named human acceptance: " + ", ".join(sorted(unaccepted)))
    approvals = [a for a in store.acceptances(mid) if a["scope"] == DELIVERY_SCOPE]
    if not approvals:
        reasons.append("human delivery approval missing (approve --by NAME)")
    return {"allowed": not reasons, "reasons": reasons, "unaccepted_findings": sorted(unaccepted),
            "approved_by": approvals[-1]["accepted_by"] if approvals else None}