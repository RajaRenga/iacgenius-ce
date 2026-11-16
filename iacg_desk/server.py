"""Unix-socket JSON API the plugin calls; mirrors the RGCE desk socket shape.

Request: {"args": ["subcommand", ...]}\\n  Reply: {"rc": int, "stdout": str, "stderr": str}\\n
Only desk subcommands are accepted; `serve` itself is not exposed over the socket.
"""
from __future__ import annotations

import io
import json
import os
import socketserver
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ALLOWED = {"create", "resolve", "answer", "skip", "sheet", "confirm", "pin", "ledger", "brief",
           "rules-check", "status", "validate", "schema", "repair", "approve", "deliver", "package",
           "remember", "knowledge", "forget", "onboard", "board"}
MAX_REQUEST = 64 * 1024
MAX_OUTPUT = 400 * 1024


def execute(args) -> dict:
    if not isinstance(args, list) or not args or not all(isinstance(a, str) for a in args):
        return {"rc": 2, "stdout": "", "stderr": 'request must be {"args": ["subcommand", ...]}'}
    if args[0] not in ALLOWED:
        return {"rc": 2, "stdout": "", "stderr": f"subcommand {args[0]!r} is not available over the socket"}
    from . import cli
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main(args)
    except SystemExit as exc:  # argparse errors
        rc, _ = exc.code, err.write(str(exc))
    except Exception as exc:  # keep serving; the caller sees the failure
        rc = 1
        err.write(f"{type(exc).__name__}: {exc}")
    return {"rc": rc, "stdout": out.getvalue()[-MAX_OUTPUT:], "stderr": err.getvalue()[-4000:]}


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        raw = self.rfile.readline(MAX_REQUEST + 1)
        try:
            if len(raw) > MAX_REQUEST:
                raise ValueError("request too large")
            reply = execute(json.loads(raw).get("args"))
        except (ValueError, AttributeError) as exc:
            reply = {"rc": 2, "stdout": "", "stderr": f"bad request: {exc}"}
        self.wfile.write(json.dumps(reply).encode() + b"\n")


if hasattr(socketserver, "UnixStreamServer"):  # Linux/macOS; the desk service never runs on Windows
    class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
        daemon_threads = True


def serve(path: str, mode: int = 0o660) -> None:
    if not hasattr(socketserver, "UnixStreamServer"):
        raise RuntimeError("Unix sockets are not available on this platform; run the desk service on Linux")
    sock = Path(path)
    sock.parent.mkdir(parents=True, exist_ok=True)
    if sock.exists():
        sock.unlink()
    with Server(str(sock), Handler) as server:
        os.chmod(sock, mode)
        print(f"iacg desk API listening on {sock}", flush=True)
        server.serve_forever()


def request(path: str, args: list, timeout: float = 960) -> dict:
    """Client used by the Hermes plugin."""
    import socket

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(timeout)
        conn.connect(path)
        conn.sendall(json.dumps({"args": args}).encode() + b"\n")
        chunks = []
        while True:
            chunk = conn.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    return json.loads(b"".join(chunks))