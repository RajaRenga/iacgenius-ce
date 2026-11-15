"""SQLite mission store. Data dir: env IACG_HOME, default ./iacg-data."""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS missions(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, provider TEXT NOT NULL, iac_tool TEXT NOT NULL,
  build_tier TEXT NOT NULL, state TEXT NOT NULL, reason TEXT, tree TEXT,
  attempts_spent INTEGER NOT NULL DEFAULT 0, attempts_allowed INTEGER NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger(
  mission_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT, origin TEXT NOT NULL,
  source TEXT, rationale TEXT NOT NULL DEFAULT '', reversibility TEXT NOT NULL DEFAULT 'cheap',
  updated_at TEXT NOT NULL, PRIMARY KEY(mission_id, key));
CREATE TABLE IF NOT EXISTS evidence(
  id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL, attempt_number INTEGER NOT NULL,
  check_name TEXT NOT NULL, tool TEXT NOT NULL, version TEXT NOT NULL, status TEXT NOT NULL,
  findings TEXT NOT NULL DEFAULT '[]', not_run_reason TEXT, packet TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS acceptances(
  id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL, scope TEXT NOT NULL,
  accepted_by TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS delivery_receipts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL, status TEXT NOT NULL,
  receipt TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS schema_cache(
  provider TEXT NOT NULL, version TEXT NOT NULL, status TEXT NOT NULL, path TEXT,
  sha256 TEXT, reason TEXT, extracted_at TEXT NOT NULL, PRIMARY KEY(provider, version));
CREATE TABLE IF NOT EXISTS repairs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL, attempt_number INTEGER NOT NULL,
  note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS build_sheets(
  mission_id TEXT PRIMARY KEY, status TEXT NOT NULL, sheet_hash TEXT, confirmed_by TEXT,
  confirmed_at TEXT, sheet TEXT NOT NULL, updated_at TEXT NOT NULL);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def data_home() -> Path:
    return Path(os.environ.get("IACG_HOME") or "./iacg-data").resolve()


class Store:
    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir).resolve() if data_dir else data_home()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "iacg.sqlite3"
        with closing(self._conn()) as conn, conn:
            conn.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _rows(self, sql: str, params=()) -> list[dict]:
        with closing(self._conn()) as conn:
            return [dict(r) for r in conn.execute(sql, params)]

    def _exec(self, sql: str, params=()) -> None:
        with closing(self._conn()) as conn, conn:
            conn.execute(sql, params)

    # -- missions ------------------------------------------------------
    def new_mission(self, title: str, provider="aws", iac_tool="terraform", build_tier="minimal",
                    tree=None, attempts_allowed=2) -> str:
        mid = "m_" + secrets.token_hex(6)
        ts = now()
        self._exec("INSERT INTO missions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                   (mid, title, provider, iac_tool, build_tier, "intake", None, tree, 0, attempts_allowed, ts, ts))
        return mid

    def mission(self, mid: str) -> dict | None:
        rows = self._rows("SELECT * FROM missions WHERE id=?", (mid,))
        return rows[0] if rows else None

    def missions(self) -> list[dict]:
        return self._rows("SELECT * FROM missions ORDER BY created_at")

    def set_state(self, mid: str, state: str, reason: str | None = None) -> None:
        self._exec("UPDATE missions SET state=?, reason=?, updated_at=? WHERE id=?", (state, reason, now(), mid))

    def update_mission(self, mid: str, **fields) -> None:
        for key, value in fields.items():
            self._exec(f"UPDATE missions SET {key}=?, updated_at=? WHERE id=?", (value, now(), mid))

    # -- ledger --------------------------------------------------------
    def ledger_upsert(self, mid, key, value, origin, source, rationale, reversibility) -> None:
        self._exec("INSERT INTO ledger VALUES (?,?,?,?,?,?,?,?) "
                   "ON CONFLICT(mission_id,key) DO UPDATE SET value=excluded.value, origin=excluded.origin, "
                   "source=excluded.source, rationale=excluded.rationale, reversibility=excluded.reversibility, "
                   "updated_at=excluded.updated_at",
                   (mid, key, value, origin, source, rationale, reversibility, now()))

    def ledger_rows(self, mid) -> list[dict]:
        return self._rows("SELECT * FROM ledger WHERE mission_id=? ORDER BY key", (mid,))

    # -- evidence ------------------------------------------------------
    def evidence_add(self, mid: str, packet: dict) -> None:
        self._exec("INSERT INTO evidence (mission_id,attempt_number,check_name,tool,version,status,findings,"
                   "not_run_reason,packet,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (mid, packet["attempt_number"], packet["check"], packet["tool"]["name"], packet["tool"]["version"],
                    packet["status"], json.dumps(packet.get("findings", []), sort_keys=True),
                    packet.get("not_run_reason"), json.dumps(packet, sort_keys=True), now()))

    def latest_evidence(self, mid: str) -> dict[str, dict]:
        """Latest evidence row per check (highest id wins)."""
        out: dict[str, dict] = {}
        for row in self._rows("SELECT * FROM evidence WHERE mission_id=? ORDER BY id", (mid,)):
            row["findings"] = json.loads(row["findings"])
            out[row["check_name"]] = row
        return out

    # -- acceptances ---------------------------------------------------
    def accept(self, mid, scope, by, reason) -> None:
        self._exec("INSERT INTO acceptances (mission_id,scope,accepted_by,reason,created_at) VALUES (?,?,?,?,?)",
                   (mid, scope, by, reason, now()))

    def acceptances(self, mid) -> list[dict]:
        return self._rows("SELECT * FROM acceptances WHERE mission_id=? ORDER BY id", (mid,))

    # -- delivery receipts ----------------------------------------------
    def receipt_add(self, mid, status, receipt: dict) -> None:
        self._exec("INSERT INTO delivery_receipts (mission_id,status,receipt,created_at) VALUES (?,?,?,?)",
                   (mid, status, json.dumps(receipt, sort_keys=True), now()))

    def receipts(self, mid) -> list[dict]:
        rows = self._rows("SELECT * FROM delivery_receipts WHERE mission_id=? ORDER BY id", (mid,))
        for row in rows:
            row["receipt"] = json.loads(row["receipt"])
        return rows

    # -- schema cache ----------------------------------------------------
    def schema_get(self, provider, version) -> dict | None:
        rows = self._rows("SELECT * FROM schema_cache WHERE provider=? AND version=?", (provider, version))
        return rows[0] if rows else None

    def schema_put(self, provider, version, status, path=None, sha256=None, reason=None) -> None:
        self._exec("INSERT INTO schema_cache VALUES (?,?,?,?,?,?,?) "
                   "ON CONFLICT(provider,version) DO UPDATE SET status=excluded.status, path=excluded.path, "
                   "sha256=excluded.sha256, reason=excluded.reason, extracted_at=excluded.extracted_at",
                   (provider, version, status, path, sha256, reason, now()))

    # -- repair attempts --------------------------------------------------
    def repair_add(self, mid, attempt_number, note="") -> None:
        self._exec("INSERT INTO repairs (mission_id,attempt_number,note,created_at) VALUES (?,?,?,?)",
                   (mid, attempt_number, note, now()))

    def repairs(self, mid) -> list[dict]:
        return self._rows("SELECT * FROM repairs WHERE mission_id=? ORDER BY attempt_number", (mid,))

    # -- build sheets -----------------------------------------------------
    def sheet_put(self, mid, sheet: dict) -> None:
        self._exec("INSERT INTO build_sheets VALUES (?,?,?,?,?,?,?) "
                   "ON CONFLICT(mission_id) DO UPDATE SET status=excluded.status, sheet_hash=excluded.sheet_hash, "
                   "confirmed_by=excluded.confirmed_by, confirmed_at=excluded.confirmed_at, sheet=excluded.sheet, "
                   "updated_at=excluded.updated_at",
                   (mid, sheet["status"], sheet.get("sheet_hash"), sheet.get("confirmed_by"),
                    sheet.get("confirmed_at"), json.dumps(sheet, sort_keys=True), now()))

    def sheet_get(self, mid) -> dict | None:
        rows = self._rows("SELECT * FROM build_sheets WHERE mission_id=?", (mid,))
        if not rows:
            return None
        return json.loads(rows[0]["sheet"])