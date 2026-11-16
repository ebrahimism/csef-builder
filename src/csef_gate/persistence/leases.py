"""Fenced stage ownership; expiry blocks, it never silently retries an effect."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import time
import uuid

from ..core import Refused
from .events import append_intent, append_outcome, ensure_runtime
from .sqlite import DATABASE, connection


@dataclass(frozen=True)
class Lease:
    stage: str
    owner: str
    token: str
    generation: int
    intent_id: str


def ttl_seconds(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 3600:
        raise Refused("lease TTL must be finite and in (0,3600]")
    return value


def acquire(con, stage, owner, ttl=600):
    ttl_seconds(ttl)
    row = con.execute("SELECT * FROM stage_leases WHERE stage=?", (stage,)).fetchone()
    if row is not None and row["active"]:
        raise Refused("stage lease held; expired leases require explicit reconciliation")
    if not isinstance(owner, str) or not owner.strip():
        raise Refused("lease owner required")
    generation = row["generation"] + 1 if row else 1
    token = uuid.uuid4().hex
    intent = append_intent(con, "stage:" + stage, "execute_stage", {"owner": owner, "generation": generation})
    con.execute("INSERT INTO stage_leases VALUES(?,?,?,?,?,?,1) ON CONFLICT(stage) DO UPDATE SET generation=excluded.generation,owner=excluded.owner,token=excluded.token,expires=excluded.expires,intent_id=excluded.intent_id,active=1",
                (stage, generation, owner, token, time.time() + ttl, intent))
    return Lease(stage, owner, token, generation, intent)


def assert_current(con, lease):
    if not isinstance(lease, Lease):
        raise Refused("current controller lease required")
    row = con.execute("SELECT * FROM stage_leases WHERE stage=?", (lease.stage,)).fetchone()
    if row is None or not row["active"] or any(row[key] != getattr(lease, key) for key in ("owner", "token", "generation", "intent_id")):
        raise Refused("stale stage lease")
    if row["expires"] <= time.time():
        raise Refused("stage lease expired; reconcile the previous execution")
    return row


def release(con, lease, status, data):
    assert_current(con, lease)
    append_outcome(con, lease.intent_id, status, data)
    con.execute("UPDATE stage_leases SET active=0,owner=NULL,token=NULL,expires=0 WHERE stage=?", (lease.stage,))


def invalidate_all(con, reason, *, stopped=False):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='stage_leases' AND type='table'").fetchone():
        return
    if stopped:
        for row in con.execute("SELECT * FROM stage_leases WHERE active=1").fetchall():
            append_outcome(con, row["intent_id"], "unknown", {"reason": reason})
        con.execute("UPDATE stage_leases SET active=0,owner=NULL,token=NULL,expires=0,generation=generation+1 WHERE active=1")
    else:
        # Fencing is not proof the old worker stopped. Keep ownership blocked
        # and its outcome unknown until explicit token-bound reconciliation.
        con.execute("UPDATE stage_leases SET expires=0 WHERE active=1")


class LeaseStore:
    def __init__(self, root: Path):
        self.db = Path(root).absolute() / DATABASE
        ensure_runtime(self.db)

    def acquire(self, stage, owner, ttl=600):
        with connection(self.db) as con:
            con.execute("BEGIN IMMEDIATE")
            return acquire(con, stage, owner, ttl)

    def heartbeat(self, lease, ttl=600):
        ttl_seconds(ttl)
        with connection(self.db) as con:
            con.execute("BEGIN IMMEDIATE")
            assert_current(con, lease)
            con.execute("UPDATE stage_leases SET expires=? WHERE stage=?", (time.time() + ttl, lease.stage))

    def release(self, lease, status="ok", data=None):
        with connection(self.db) as con:
            con.execute("BEGIN IMMEDIATE")
            release(con, lease, status, {} if data is None else data)

    def recover(self, lease, *, reconciled=False):
        if reconciled is not True:
            raise Refused("confirm the worker stopped and reconcile its effects before recovery")
        if not isinstance(lease, Lease):
            raise Refused("the observed expired lease is required")
        with connection(self.db) as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM stage_leases WHERE stage=? AND active=1", (lease.stage,)).fetchone()
            if row is None or any(row[k] != getattr(lease, k) for k in ("token", "owner", "generation", "intent_id")):
                raise Refused("recovery observation is stale")
            if row["expires"] > time.time():
                raise Refused("only an expired active lease can be recovered")
            append_outcome(con, row["intent_id"], "unknown", {"reason": "explicit reconciled recovery"})
            con.execute("UPDATE stage_leases SET active=0,owner=NULL,token=NULL,expires=0,generation=generation+1 WHERE stage=?", (lease.stage,))
            con.execute("UPDATE stages SET status='stale',handoff=NULL WHERE name=?", (lease.stage,))
