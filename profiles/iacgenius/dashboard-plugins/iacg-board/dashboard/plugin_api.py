"""Dashboard tab backend: serve the board snapshot the desk writes.

The page is <data>/board.html, written by `iacg_desk board`. Refresh re-renders the
snapshot from the durable store over the desk's Unix socket — never invented live state.
"""
from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

router = APIRouter()
HERE = Path(__file__).resolve().parent
DEFAULTS = {"socket": "/run/iacg/iacg.sock", "board": "/data/iacg/board.html",
            "status": "/data/iacg/board.json"}
REFRESH = threading.Lock()

EMPTY = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>IaC Genius board</title>
<style>body{margin:0;background:#faf9f6;color:#17171a;font:15px/1.55 system-ui,sans-serif;display:grid;
place-items:center;height:100vh}main{max-width:52ch;padding:24px}h1{font-size:20px;margin:0 0 8px}
p{color:#6b6b66}code{font:12px ui-monospace,monospace;background:#fff;border:1px solid #e4e2db;padding:1px 5px;border-radius:5px}</style>
</head><body><main><h1>No board yet</h1><p>The desk has not written a snapshot on this installation. Create a
mission (<code>iacg_mission action=create</code>) or press Refresh once the desk is reachable; the desk writes
<code>board.html</code> and this page appears.</p></main></body></html>"""


def _settings() -> dict:
    try:
        return json.loads((HERE.parent / "local.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _path(name: str) -> Path:
    return Path(_settings().get(name) or DEFAULTS[name])


def _desk(args: list, timeout: int = 300) -> str:
    path = _settings().get("socket") or DEFAULTS["socket"]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(timeout + 30)
            conn.connect(path)
            conn.sendall(json.dumps({"args": args}).encode() + b"\n")
            chunks = []
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        reply = json.loads(b"".join(chunks))
    except (OSError, ValueError) as exc:
        raise HTTPException(503, f"the desk service is not reachable: {exc}") from None
    rc, out, err = reply.get("rc", 1), reply.get("stdout") or "", reply.get("stderr") or ""
    if rc != 0:
        message = (err or out).strip().splitlines()
        raise HTTPException(400, message[-1] if message else f"iacg {args[0]} failed")
    return out


def _status() -> dict:
    try:
        data = json.loads(_path("status").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"generated_at": None, "missions": 0, "summary": "no snapshot yet"}
    return {"generated_at": data.get("generated_at"), "missions": len(data.get("missions", [])),
            "summary": f"{len(data.get('missions', []))} mission(s)"}


@router.get("/status")
def status() -> dict:
    return _status()


@router.post("/refresh")
def refresh() -> dict:
    """Re-render the board from the durable store; the numbers come from the desk, not this page."""
    if not REFRESH.acquire(blocking=False):
        raise HTTPException(409, "a board refresh is already running")
    try:
        _desk(["board"])
        return {"ok": True, **_status()}
    finally:
        REFRESH.release()


@router.get("/page", response_class=HTMLResponse)
def page() -> HTMLResponse:
    try:
        text = _path("board").read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError):
        return HTMLResponse(EMPTY, status_code=404, headers={"Cache-Control": "no-store"})
    return HTMLResponse(text, headers={"Cache-Control": "no-store"})