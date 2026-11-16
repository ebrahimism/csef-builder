"""Durable intent/outcome journal. Entries are observations, never Gate permits."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import time
import uuid

from ..core import Refused, encoded, parse_json
from .sqlite import DATABASE, connection


RUNTIME_TABLES = ("event_journal", "stage_leases", "stored_artifacts")
RUNTIME_DDL = (
    "CREATE TABLE runtime_meta(id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL CHECK(version=1))",
    "CREATE TABLE event_journal(seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL, intent_id TEXT UNIQUE REFERENCES event_journal(event_id), kind TEXT NOT NULL CHECK(kind IN ('intent','outcome')), scope TEXT NOT NULL, action TEXT NOT NULL, body TEXT NOT NULL, created REAL NOT NULL, CHECK((kind='intent' AND intent_id IS NULL) OR (kind='outcome' AND intent_id IS NOT NULL)))",
    "CREATE TABLE stage_leases(stage TEXT PRIMARY KEY REFERENCES stages(name), generation INTEGER NOT NULL CHECK(generation>0), owner TEXT, token TEXT, expires REAL NOT NULL, intent_id TEXT REFERENCES event_journal(event_id), active INTEGER NOT NULL CHECK(active IN (0,1)))",
    "CREATE TABLE stored_artifacts(sha256 TEXT PRIMARY KEY, bytes INTEGER NOT NULL CHECK(bytes>=0), media_type TEXT NOT NULL, provenance TEXT NOT NULL, created REAL NOT NULL)",
)


def ensure_runtime(db: Path):
    if db.name != DATABASE:
        raise Refused("migrate the legacy store before running stages")
    with connection(db) as con:
        con.execute("BEGIN IMMEDIATE")
        present = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "runtime_meta" not in present:
            if present & set(RUNTIME_TABLES):
                raise Refused("partial runtime schema; inspect before recovery")
            for statement in RUNTIME_DDL:
                con.execute(statement)
            con.execute("INSERT INTO runtime_meta VALUES(1,1)")
        else:
            if [tuple(r) for r in con.execute("SELECT id,version FROM runtime_meta")] != [(1, 1)] or not set(RUNTIME_TABLES) <= present:
                raise Refused("unsupported runtime schema")


def append_intent(con, scope: str, action: str, data: dict) -> str:
    if not isinstance(scope, str) or not scope.strip() or not isinstance(action, str) or not action.strip() or not isinstance(data, dict):
        raise Refused("intent requires scope, action and structured data")
    body = encoded(data).decode()
    if len(body.encode()) > 1_000_000:
        raise Refused("journal entry too large")
    key = "intent-" + uuid.uuid4().hex
    con.execute("INSERT INTO event_journal(event_id,kind,scope,action,body,created) VALUES(?,'intent',?,?,?,?)",
                (key, scope, action, body, time.time()))
    return key


def append_outcome(con, intent_id: str, status: str, data: dict) -> str:
    if status not in ("ok", "failed", "denied", "unknown") or not isinstance(data, dict):
        raise Refused("invalid outcome; a caller verdict is not authority")
    intent = con.execute("SELECT * FROM event_journal WHERE event_id=? AND kind='intent'", (intent_id,)).fetchone()
    if intent is None:
        raise Refused("outcome has no persisted intent")
    body = encoded({"status": status, "data": data}).decode()
    if len(body.encode()) > 1_000_000:
        raise Refused("journal entry too large")
    if con.execute("SELECT 1 FROM event_journal WHERE intent_id=?", (intent_id,)).fetchone():
        raise Refused("outcome is already recorded")
    key = "outcome-" + uuid.uuid4().hex
    con.execute("INSERT INTO event_journal(event_id,intent_id,kind,scope,action,body,created) VALUES(?,?,'outcome',?,?,?,?)",
                (key, intent_id, intent["scope"], intent["action"], body, time.time()))
    return key


class Journal:
    def __init__(self, root: Path):
        self.db = Path(root).absolute() / DATABASE
        ensure_runtime(self.db)

    def append_intent(self, scope, action, data):
        with connection(self.db) as con:
            con.execute("BEGIN IMMEDIATE")
            return append_intent(con, scope, action, data)

    def append_outcome(self, intent_id, status, data):
        with connection(self.db) as con:
            con.execute("BEGIN IMMEDIATE")
            return append_outcome(con, intent_id, status, data)

    def replay(self, scope=None):
        with connection(self.db) as con:
            rows = con.execute("SELECT * FROM event_journal ORDER BY seq").fetchall() if scope is None else con.execute("SELECT * FROM event_journal WHERE scope=? ORDER BY seq", (scope,)).fetchall()
        return [{**dict(row), "body": parse_json(row["body"])} for row in rows]

    def pending(self):
        with connection(self.db) as con:
            rows = con.execute("SELECT i.* FROM event_journal i WHERE i.kind='intent' AND NOT EXISTS(SELECT 1 FROM event_journal o WHERE o.intent_id=i.event_id) ORDER BY i.seq").fetchall()
        return [{**dict(row), "body": parse_json(row["body"]), "outcome": "unknown"} for row in rows]
