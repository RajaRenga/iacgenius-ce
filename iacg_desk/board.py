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


_CSS = """
:root{--bg:#f4f3ef;--surface:#fff;--ink:#1b1b1f;--muted:#6b6b66;--line:#e6e4dd;
--ok:#15803d;--ok-bg:#ecfdf3;--bad:#b91c1c;--bad-bg:#fef2f2;--warn:#b45309;--warn-bg:#fffbeb;
--blue:#1d4ed8;--blue-bg:#eff6ff;--teal:#0f766e;--teal-bg:#f0fdfa;--idle:#52525b;--idle-bg:#f4f4f5;}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;height:100vh;overflow:hidden;display:flex;flex-direction:column;
font:14px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header{flex:0 0 auto;display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;justify-content:space-between;
padding:14px 20px;background:linear-gradient(120deg,#0f766e,#115e59 55%,#134e4a);color:#fff;
box-shadow:0 1px 0 rgba(0,0,0,.08)}
header h1{font-size:16px;font-weight:650;margin:0;letter-spacing:.2px}
header .sub{font-size:12px;color:#cdeae6;margin-top:2px}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:#e6f4f2}
.legend span{display:inline-flex;align-items:center;gap:5px}
.legend i{width:9px;height:9px;border-radius:50%;display:inline-block}
.scroll{flex:1 1 auto;min-height:0;overflow-y:auto;padding:18px 20px 28px}
.scroll::-webkit-scrollbar{width:11px}
.scroll::-webkit-scrollbar-track{background:var(--bg)}
.scroll::-webkit-scrollbar-thumb{background:#cfccc3;border-radius:7px;border:3px solid var(--bg)}
.scroll::-webkit-scrollbar-thumb:hover{background:#b3b0a6}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin:0 auto 14px;
max-width:1100px;box-shadow:0 1px 2px rgba(20,20,20,.05)}
.card-top{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;justify-content:space-between}
.mid{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--teal);background:var(--teal-bg);
border:1px solid #cbe9e5;padding:2px 8px;border-radius:6px}
.title{font-size:15px;font-weight:600;margin:6px 0 2px}
.meta{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 0;font-size:11.5px;color:var(--muted)}
.meta span{background:var(--idle-bg);border:1px solid var(--line);padding:1px 8px;border-radius:20px}
.badges{display:flex;gap:6px;flex-wrap:wrap}
.badge{font-size:11.5px;font-weight:600;padding:3px 10px;border-radius:20px;border:1px solid transparent;white-space:nowrap}
.ok{color:var(--ok);background:var(--ok-bg);border-color:#bbe7cb}
.bad{color:var(--bad);background:var(--bad-bg);border-color:#f3c8c8}
.warn{color:var(--warn);background:var(--warn-bg);border-color:#f0dcb2}
.blue{color:var(--blue);background:var(--blue-bg);border-color:#c7d8f7}
.teal{color:var(--teal);background:var(--teal-bg);border-color:#cbe9e5}
.idle{color:var(--idle);background:var(--idle-bg);border-color:var(--line)}
.section-label{font-size:11px;font-weight:650;letter-spacing:.6px;text-transform:uppercase;color:var(--muted);margin:14px 0 7px}
.chips{display:flex;flex-wrap:wrap;gap:7px}
.chip{display:inline-flex;align-items:center;gap:7px;flex-wrap:wrap;font-size:12px;padding:5px 10px;border-radius:9px;
border:1px solid var(--line);background:#fbfaf7;max-width:100%}
.chip .dot{width:8px;height:8px;border-radius:50%;flex:0 0 auto}
.chip.ok .dot{background:var(--ok)}.chip.bad .dot{background:var(--bad)}.chip.warn .dot{background:var(--warn)}.chip.idle .dot{background:var(--idle)}
.chip .ck{font-weight:600}
.chip .tool{color:var(--muted);font:11px ui-monospace,monospace}
.chip .fc{color:var(--muted);font-size:11px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
@media(max-width:640px){.grid2{grid-template-columns:1fr}}
.panel{border:1px solid var(--line);border-radius:10px;padding:11px 13px;background:#fbfaf7;min-width:0}
.panel h3{font-size:11px;font-weight:650;letter-spacing:.5px;text-transform:uppercase;color:var(--muted);margin:0 0 8px}
.meter{height:8px;border-radius:6px;background:#eceae4;overflow:hidden;margin:2px 0 6px}
.meter-fill{height:100%;border-radius:6px}
.meter-fill.ok{background:var(--ok)}.meter-fill.warn{background:var(--warn)}.meter-fill.bad{background:var(--bad)}
.meter-label{font-size:12px;color:var(--muted)}
.reasons{margin:0;padding-left:18px;font-size:12.5px;color:#3f3f46}
.reasons li{margin:3px 0;overflow-wrap:anywhere}
.owner{display:flex;align-items:center;gap:8px;margin-top:14px;padding-top:12px;border-top:1px dashed var(--line);
font-size:12.5px;color:var(--muted)}
.owner b{color:var(--ink)}
.empty{max-width:560px;margin:8vh auto;text-align:center;background:var(--surface);border:1px solid var(--line);
border-radius:16px;padding:40px 28px;box-shadow:0 1px 2px rgba(20,20,20,.05)}
.empty h2{margin:0 0 8px;font-size:18px}
.empty p{color:var(--muted);margin:0}
.empty code{font:12px ui-monospace,monospace;background:var(--idle-bg);border:1px solid var(--line);padding:1px 6px;border-radius:5px}
"""


def _status_class(status) -> str:
    s = (status or "").upper()
    if s == "PASS":
        return "ok"
    if s == "FAIL":
        return "bad"
    if s in ("NOT_RUN", "SKIPPED"):
        return "idle"
    return "warn"


def _state_class(state) -> str:
    return {"validated": "ok", "approved": "teal", "delivered": "blue",
            "failed": "bad", "needs_human": "warn"}.get(state, "idle")


def _disp_class(disp) -> str:
    return {"deliverable": "ok", "blocked": "warn", "needs_human": "warn", "delivered": "blue"}.get(disp, "idle")


def _ev_chip(e) -> str:
    findings = len(e["findings"])
    nr = f' · {html.escape(e["not_run_reason"])}' if e.get("not_run_reason") else ""
    plural = "s" if findings != 1 else ""
    return (f'<span class="chip {_status_class(e["status"])}"><span class="dot"></span>'
            f'<span class="ck">{html.escape(e["check"])}</span><b>{html.escape(e["status"])}</b>'
            f'<span class="tool">{html.escape(e["tool"])} {html.escape(e["version"])}{nr}</span>'
            f'<span class="fc">{findings} finding{plural}</span></span>')


def _meter(spent, allowed) -> str:
    pct = 0 if allowed <= 0 else min(100, round(spent / allowed * 100))
    cls = "bad" if allowed > 0 and spent >= allowed else ("warn" if spent > 0 else "ok")
    return (f'<div class="meter"><div class="meter-fill {cls}" style="width:{pct}%"></div></div>'
            f'<span class="meter-label">{spent} / {allowed} repair attempts used</span>')


def _guidance(m) -> str:
    """Plain-language readiness + the concrete next step, so a card is self-explanatory."""
    ev = {e["check"]: e["status"] for e in m["evidence"]}
    hard_ok = ev.get("validate") == "PASS" and ev.get("secret_scan") == "PASS"
    if hard_ok:
        readiness = ("Code is valid — terraform validate and the secret scan passed. "
                     "Anything still open is a decision for you, not a bug.")
    else:
        readiness = "A correctness gate has not passed yet — this needs repair before it can be delivered."
    disp, mid, owner = m["disposition"], m["id"], m["next_owner"]
    if disp == "delivered":
        step = "Delivered and read back verified. Nothing more to do."
    elif disp == "deliverable":
        step = (f'Ready. In chat: "deliver {mid} to owner/repo" opens a PR, '
                f'or "package {mid}" zips the folder to download from the Files tab.')
    elif owner.startswith("human"):
        step = (f'Your call. In chat: "show code {mid}" to review, accept any soft findings by name, '
                f'then "approve delivery for {mid}".')
    else:
        step = (f'In chat: "status {mid}" for the evidence, "show code {mid}" to review. '
                f'IaCGenius repairs within the budget, then it comes back to you.')
    return (f'<div class="panel" style="margin-top:14px"><h3>Readiness &amp; next step</h3>'
            f'<p style="margin:0 0 6px;font-size:12.5px">{html.escape(readiness)}</p>'
            f'<p style="margin:0;font-size:12.5px;color:#3f3f46">{html.escape(step)}</p></div>')


def _card(m) -> str:
    badges = (f'<span class="badge {_state_class(m["state"])}">{html.escape(m["state"])}</span>'
              f'<span class="badge {_disp_class(m["disposition"])}">{html.escape(m["disposition"])}</span>')
    meta = "".join(f"<span>{html.escape(str(m[k]))}</span>" for k in ("provider", "iac_tool", "build_tier") if m.get(k))
    chips = "".join(_ev_chip(e) for e in m["evidence"]) or '<span class="chip idle">no evidence yet</span>'
    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in m["gate_reasons"]) or "<li>no blocking reasons</li>"
    questions = ""
    if m["open_questions"]:
        questions = ('<div class="panel"><h3>Must-ask open</h3><ul class="reasons">'
                     + "".join(f"<li>{html.escape(q)}</li>" for q in m["open_questions"]) + "</ul></div>")
    acceptances = ""
    if m["acceptances"]:
        acceptances = ('<div class="panel"><h3>Named acceptances</h3><ul class="reasons">'
                       + "".join(f"<li>{html.escape(a['scope'])} — {html.escape(a['by'])}"
                                 + (f" ({html.escape(a['reason'])})" if a.get("reason") else "") + "</li>"
                                 for a in m["acceptances"]) + "</ul></div>")
    reason = f'<div class="meta"><span>{html.escape(m["reason"])}</span></div>' if m.get("reason") else ""
    return (
        '<article class="card">'
        f'<div class="card-top"><span class="mid">{html.escape(m["id"])}</span><div class="badges">{badges}</div></div>'
        f'<div class="title">{html.escape(m["title"])}</div>'
        f'<div class="meta">{meta}</div>{reason}'
        '<div class="section-label">Evidence — tool + version</div>'
        f'<div class="chips">{chips}</div>'
        '<div class="grid2">'
        f'<div class="panel"><h3>Repair budget</h3>{_meter(m["attempts"]["spent"], m["attempts"]["allowed"])}</div>'
        f'<div class="panel"><h3>Disposition reasons</h3><ul class="reasons">{reasons}</ul></div>'
        f'{questions}{acceptances}'
        '</div>'
        f'{_guidance(m)}'
        f'<div class="owner">Next owner:&nbsp;<b>{html.escape(m["next_owner"])}</b></div>'
        '</article>')


def render_html(snap: dict) -> str:
    count = len(snap["missions"])
    cards = "".join(_card(m) for m in snap["missions"])
    if not cards:
        cards = ('<div class="empty"><h2>No missions yet</h2>'
                 '<p>Create one with <code>iacg_mission action=create</code>, then press Refresh. '
                 'The board shows exactly what the desk holds — no live state is invented here.</p></div>')
    legend = ('<div class="legend"><span><i style="background:#4ade80"></i>PASS</span>'
              '<span><i style="background:#f87171"></i>FAIL</span>'
              '<span><i style="background:#a1a1aa"></i>NOT RUN</span>'
              f'<span>{count} mission{"s" if count != 1 else ""}</span></div>')
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>IaC Genius board</title><style>{_CSS}</style></head><body>"
            "<header><div><h1>IaC Genius mission board</h1>"
            f"<div class=\"sub\">Snapshot {html.escape(str(snap['generated_at']))} — written by the desk</div></div>"
            f"{legend}</header>"
            f'<main class="scroll">{cards}</main></body></html>')


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