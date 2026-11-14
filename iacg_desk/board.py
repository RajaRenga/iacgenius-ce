"""Mission board snapshot: exactly what the store holds, never invented live state.

Writes <data>/board.json and <data>/board.html; the dashboard plugin serves these files.
"""
from __future__ import annotations

import html
import json

from . import gates, ledger, repair
from .store import now


def _next_owner(mission, open_questions, approvals):
    state = mission["state"]
    if state == "delivered":
        return "none (delivered, read-back verified)"
    if state == "needs_human" or open_questions:
        return "human"
    if state == "failed":
        return "agent (bounded repair)" if mission["attempts_spent"] < mission["attempts_allowed"] else "human"
    if state == "validated":
        return "human (approve delivery)" if not approvals else "desk (deliver)"
    if state == "approved":
        return "desk (deliver)"
    return "agent (intake)"


def snapshot(store) -> dict:
    missions = []
    for m in store.missions():
        mid = m["id"]
        evidence = [{"check": r["check_name"], "tool": r["tool"], "version": r["version"], "status": r["status"],
                     "findings": r["findings"], "not_run_reason": r["not_run_reason"],
                     "attempt_number": r["attempt_number"]}
                    for r in store.latest_evidence(mid).values()]
        acceptances = store.acceptances(mid)
        questions = [r["key"] for r in ledger.open_questions(store, mid)]
        gate = gates.delivery_gate(store, mid)
        missions.append({
            "id": mid, "title": m["title"], "provider": m["provider"], "iac_tool": m["iac_tool"],
            "build_tier": m["build_tier"], "state": m["state"], "reason": m["reason"],
            "created_at": m["created_at"], "updated_at": m["updated_at"],
            "attempts": {"spent": m["attempts_spent"], "allowed": m["attempts_allowed"]},
            "open_questions": questions, "evidence": evidence,
            "acceptances": [{"scope": a["scope"], "by": a["accepted_by"], "reason": a["reason"]} for a in acceptances],
            "disposition": ("delivered" if m["state"] == "delivered" else
                            "needs_human" if m["state"] == "needs_human" else
                            "blocked" if not gate["allowed"] else "deliverable"),
            "gate_reasons": gate["reasons"],
            "next_owner": _next_owner(m, questions, [a for a in acceptances if a["scope"] == gates.DELIVERY_SCOPE]),
            "receipts": [{"status": r["status"]} for r in store.receipts(mid)],
        })
    return {"generated_at": now(), "repair_budget_default": repair.budget(), "missions": missions}


def render_html(snap: dict) -> str:
    rows = []
    for m in snap["missions"]:
        ev = "<br>".join(f"{html.escape(e['check'])}: <b>{e['status']}</b> "
                         f"({html.escape(e['tool'])} {html.escape(e['version'])}"
                         + (f"; {html.escape(e['not_run_reason'])}" if e["not_run_reason"] else "")
                         + f"; {len(e['findings'])} findings)" for e in m["evidence"]) or "no evidence yet"
        rows.append(
            "<tr>"
            f"<td><code>{m['id']}</code><br>{html.escape(m['title'])}</td>"
            f"<td>{html.escape(m['state'])}" + (f"<br><small>{html.escape(m['reason'])}</small>" if m["reason"] else "") + "</td>"
            f"<td>{ev}</td>"
            f"<td>{m['attempts']['spent']} / {m['attempts']['allowed']}</td>"
            f"<td>{html.escape(m['disposition'])}"
            + ("".join(f"<br><small>{html.escape(r)}</small>" for r in m["gate_reasons"])) + "</td>"
            f"<td>{html.escape(m['next_owner'])}</td></tr>")
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>IaC Genius board</title>"
            "<style>body{font:14px/1.5 system-ui,sans-serif;margin:24px;background:#faf9f6;color:#17171a}"
            "table{border-collapse:collapse;width:100%}td,th{border:1px solid #e4e2db;padding:8px;text-align:left;"
            "vertical-align:top}code{font:12px ui-monospace,monospace}small{color:#6b6b66}</style></head><body>"
            f"<h1>IaC Genius mission board</h1><p>Snapshot {snap['generated_at']} — written by the desk; "
            "no live state is invented here.</p>"
            "<table><tr><th>Mission</th><th>State</th><th>Evidence (tool + version)</th><th>Repair attempts</th>"
            "<th>Disposition</th><th>Next owner</th></tr>"
            + ("".join(rows) or "<tr><td colspan=6>No missions yet. Create one with iacg_mission action=create.</td></tr>")
            + "</table></body></html>")


def write(store) -> dict:
    snap = snapshot(store)
    (store.data_dir / "board.json").write_text(json.dumps(snap, sort_keys=True, indent=2), encoding="utf-8")
    (store.data_dir / "board.html").write_text(render_html(snap), encoding="utf-8")
    return snap


def summary(snap: dict) -> str:
    if not snap["missions"]:
        return "No missions yet."
    lines = [f"{len(snap['missions'])} mission(s):"]
    for m in snap["missions"]:
        lines.append(f"- {m['id']} [{m['state']}] {m['title']} · repair {m['attempts']['spent']}/{m['attempts']['allowed']}"
                     f" · {m['disposition']} · next: {m['next_owner']}")
    return "\n".join(lines)