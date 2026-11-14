"""GitHub delivery: a PR whose body is the ledger, then read the commit back.

VERIFIED only on read-back (every written path fetched again, hash matched).
Token: env IACG_GITHUB_TOKEN, isolated here, never logged. Absent token => NOT_RUN.
`api(method, path, payload, token) -> (http_status, json)` is injectable for tests.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__, gates, ledger
from .store import now


def _github_api(method, path, payload, token):
    req = urllib.request.Request("https://api.github.com/" + path.lstrip("/"), method=method,
                                 data=json.dumps(payload).encode() if payload is not None else None,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Accept": "application/vnd.github+json",
                                          "User-Agent": "iacg-desk"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode() or "{}")
        except ValueError:
            body = {}
        return exc.code, body  # never echo request headers: the token stays out of every output


def _tree_files(tree: Path):
    for path in sorted(tree.rglob("*")):
        if path.is_file() and ".terraform" not in path.parts and ".git" not in path.parts:
            data = path.read_bytes()
            yield path.relative_to(tree).as_posix(), data, hashlib.sha256(data).hexdigest()


def deliver(store, mid, repository, base_branch="main", api=None, tree=None) -> dict:
    mission = store.mission(mid)
    if mission is None:
        raise KeyError(f"unknown mission {mid}")
    gate = gates.delivery_gate(store, mid)
    if not gate["allowed"]:
        return {"status": "REFUSED", "reasons": gate["reasons"]}
    token = os.environ.get("IACG_GITHUB_TOKEN")
    if not token:
        result = {"status": "NOT_RUN", "reason": "IACG_GITHUB_TOKEN not set; delivery did not run"}
        store.receipt_add(mid, "NOT_RUN", result)
        return result
    tree = Path(tree or mission["tree"] or "")
    files = list(_tree_files(tree)) if tree.is_dir() else []
    if not files:
        return {"status": "REFUSED", "reasons": [f"no deliverable files under {tree}"]}
    api = api or _github_api
    branch = f"iacgenius/{mid}"

    status, base = api("GET", f"repos/{repository}/git/ref/heads/{base_branch}", None, token)
    if status != 200:
        return {"status": "FAILED", "reasons": [f"base branch {base_branch} not readable (HTTP {status})"]}
    base_sha = base["object"]["sha"]
    status, _ = api("POST", f"repos/{repository}/git/refs", {"ref": f"refs/heads/{branch}", "sha": base_sha}, token)
    if status not in (201, 422):  # 422 = branch already exists (re-delivery)
        return {"status": "FAILED", "reasons": [f"could not create branch {branch} (HTTP {status})"]}

    written = []
    for rel, data, digest in files:
        status, resp = api("PUT", f"repos/{repository}/contents/{rel}",
                           {"message": f"iacgenius {mid}: {rel}", "branch": branch,
                            "content": base64.b64encode(data).decode()}, token)
        if status not in (200, 201):
            return {"status": "FAILED", "reasons": [f"write failed for {rel} (HTTP {status})"]}
        written.append({"path": rel, "sha256": digest, "bytes": len(data)})

    body = ledger.prompt_block(store, mid) + "\n\n```json\n" + ledger.sorted_json(store, mid) + "\n```\n"
    status, pr = api("POST", f"repos/{repository}/pulls",
                     {"title": f"iacgenius {mid}: {mission['title']}", "head": branch,
                      "base": base_branch, "body": body}, token)
    pr_url = pr.get("html_url") if status in (200, 201) else None

    # Read-back: fetch the branch head and every written path again; hashes must match.
    verified = False
    commit_sha = None
    status, ref = api("GET", f"repos/{repository}/git/ref/heads/{branch}", None, token)
    if status == 200:
        commit_sha = ref["object"]["sha"]
        verified = bool(commit_sha)
        for item in written:
            status, content = api("GET", f"repos/{repository}/contents/{item['path']}?ref={branch}", None, token)
            if status != 200:
                verified = False
                break
            remote = base64.b64decode(content.get("content", ""))
            if hashlib.sha256(remote).hexdigest() != item["sha256"]:
                verified = False
                break
    if commit_sha is None:
        result = {"status": "UNVERIFIED", "reason": "branch head could not be read back", "written_paths": written}
        store.receipt_add(mid, "UNVERIFIED", result)
        return result
    receipt = {"schema_version": "1.0.0", "packet_type": "github_delivery_receipt", "mission_id": mid,
               "created_at": now(),
               "provenance": {"producer": "iacg_desk.deliver", "producer_version": __version__},
               "repository": repository, "branch": branch, "written_paths": written,
               "commit_sha": commit_sha, "read_back_verified": verified, "read_back_at": now(),
               "approval": {"approved_by": gate["approved_by"],
                            "approved_at": next(a["created_at"] for a in reversed(store.acceptances(mid))
                                                if a["scope"] == gates.DELIVERY_SCOPE)}}
    if pr_url:
        receipt["pr_url"] = pr_url
    store.receipt_add(mid, "VERIFIED" if verified else "UNVERIFIED", receipt)
    if verified:
        store.set_state(mid, "delivered", None)
    return {"status": "VERIFIED" if verified else "UNVERIFIED", "receipt": receipt}