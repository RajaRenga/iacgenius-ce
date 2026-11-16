"""Durable profile knowledge — facts the user/org declares once, reused across missions.

A fact is a decision-key value that should not be re-asked every mission (region, naming prefix,
owner tag, retention policy). The SQLite `knowledge` table is the truth; each fact is also rendered
as an OKF v0.2 concept (Markdown + YAML frontmatter, the RemediGenius format) under
<data>/knowledge/okf/facts/ for human reading and provenance. The resolver cites a fact as
`knowledge:<slug>@<hash16>` — a resolving source the decision ledger already accepts.

Capture is explicit (`remember`) or automatic on confirm for the org-level PROFILE_KEYS. A mission
can always override a fact by stating its own value; knowledge only fills what was not stated.
"""
from __future__ import annotations

import hashlib
import json

from . import catalogue
from .store import Store, now

# Org-level conventions worth remembering across missions. Per-mission choices (environment,
# exposure, encryption owner, ...) are deliberately NOT auto-captured.
PROFILE_KEYS = frozenset({"region", "naming.prefix", "tagging.owner", "data.retention_days"})


def _slug(provider: str, key: str) -> str:
    return f"{provider}-{key.replace('.', '-')}"


def _hash(provider: str, key: str, value: str) -> str:
    raw = json.dumps({"provider": provider, "key": key, "value": value}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def source_ref(provider: str, key: str, value: str) -> str:
    return f"knowledge:{_slug(provider, key)}@{_hash(provider, key, value)}"


def _card_dir(store: Store):
    path = store.data_dir / "knowledge" / "okf" / "facts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _render_card(row: dict) -> str:
    provider, key, value = row["provider"], row["key"], row["value"]
    entry = catalogue.key(key)
    title = f"{key} is {value}"
    desc = f"Declared profile fact reused across {provider} missions so {key} is not re-asked."
    return f"""---
type: Fact
title: "{title}"
description: "{desc}"
tags: [{provider}, profile, {key.replace('.', '-')}]
status: confirmed
sources:
  - id: user
    title: "Declared by {row['captured_by']}"
    author: {row['captured_by']}
iacgenius:
  provider: {provider}
  key: {key}
  value: "{value}"
  slug: {row['slug']}
  hash: {row['hash']}
  captured_by: {row['captured_by']}
  captured_at: "{row['captured_at']}"
---

# Fact

`{key} = {value}` for **{provider}**. Declared by {row['captured_by']} on {row['captured_at']}.

# Why it matters

{entry.why_it_matters if entry else ''}

# How it is used

IaCGenius resolves `{key}` from this fact (`{source_ref(provider, key, value)}`) for every {provider}
mission unless the request states a different value. Change it with `remember`, drop it with `forget`.
"""


def remember(store: Store, provider: str, key: str, value: str, by: str) -> dict:
    if key in catalogue.MISSION_TARGET_KEYS:
        raise ValueError(f"{key} is locked per mission, not profile knowledge")
    if catalogue.key(key) is None:
        raise ValueError(f"unknown decision key {key!r}")
    value = str(value).strip()
    if not catalogue.in_domain(key, value):
        raise ValueError(f"{value!r} is not an accepted value for {key}")
    misfit = catalogue.provider_misfit(provider, key, value)
    if misfit:
        raise ValueError(misfit)
    slug, hash = _slug(provider, key), _hash(provider, key, value)
    store.knowledge_upsert(provider, key, value, slug, hash, by)
    row = store.knowledge_get(provider, key)
    (_card_dir(store) / f"{slug}.md").write_text(_render_card(row), encoding="utf-8")
    return {"provider": provider, "key": key, "value": value, "slug": slug,
            "source": source_ref(provider, key, value), "captured_by": by}


def lookup(store: Store, provider: str, key: str) -> dict | None:
    return store.knowledge_get(provider, key)


def facts(store: Store, provider: str | None = None) -> list[dict]:
    return [dict(r, source=source_ref(r["provider"], r["key"], r["value"])) for r in store.knowledge_rows(provider)]


def forget(store: Store, provider: str, key: str) -> dict:
    row = store.knowledge_get(provider, key)
    if row is None:
        raise KeyError(f"no knowledge fact {provider}/{key}")
    store.knowledge_delete(provider, key)
    card = _card_dir(store) / f"{row['slug']}.md"
    if card.exists():
        card.unlink()
    return {"forgotten": f"{provider}/{key}"}


def learn_from_mission(store: Store, mid: str, by: str) -> list[dict]:
    """Auto-capture the org-level PROFILE_KEYS a mission STATED, once the user confirms it."""
    learned = []
    for row in store.ledger_rows(mid):
        if row["origin"] == "STATED" and row["key"] in PROFILE_KEYS and row["value"]:
            mission = store.mission(mid)
            try:
                learned.append(remember(store, mission["provider"], row["key"], row["value"], by))
            except ValueError:
                continue
    return learned


def context_block(store: Store, provider: str) -> str:
    rows = facts(store, provider)
    if not rows:
        return ""
    lines = ["## Profile knowledge (declared facts, reused across missions)"]
    for r in rows:
        lines.append(f"- {r['key']} = {r['value']}  ({r['source']}, declared by {r['captured_by']})")
    lines.append("Apply these unless the request states a different value; they are inputs, not questions.")
    return "\n".join(lines)