"""One SQLite transaction domain, retaining the existing logical repositories."""
from __future__ import annotations

from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3

from ..core import Refused, plain


VERSION = 1
DATABASE = "control.sqlite3"
# These frozen definitions describe the two supported pre-migration stores.
PROJECT_SQL = """CREATE TABLE revisions(version INTEGER PRIMARY KEY, body TEXT NOT NULL, sha256 TEXT NOT NULL, reason TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE stages(position INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, status TEXT NOT NULL, version INTEGER, packet_hash TEXT, handoff TEXT);
CREATE TABLE changes(id INTEGER PRIMARY KEY, proposal TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE calls(id INTEGER PRIMARY KEY, role TEXT NOT NULL, status TEXT NOT NULL, receipt TEXT, created TEXT NOT NULL);
CREATE TABLE settings(max_calls INTEGER NOT NULL);
CREATE TABLE stage_definitions(position INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, title TEXT NOT NULL, role TEXT NOT NULL);
"""
GATE_SQL = """CREATE TABLE config(spec_hash TEXT NOT NULL, baseline_hash TEXT NOT NULL, project TEXT NOT NULL);
CREATE TABLE runs(id TEXT PRIMARY KEY, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL);
CREATE TABLE evaluations(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, source_hash TEXT NOT NULL, spec_hash TEXT NOT NULL, status TEXT NOT NULL, snapshot TEXT NOT NULL, report TEXT NOT NULL, report_hash TEXT, created TEXT NOT NULL);
CREATE TABLE attempts(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, status TEXT NOT NULL, artifact TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE checkpoints(id TEXT PRIMARY KEY, run_id TEXT UNIQUE NOT NULL, evaluation_id TEXT UNIQUE NOT NULL, source_hash TEXT NOT NULL, spec_hash TEXT NOT NULL, snapshot TEXT NOT NULL, report_hash TEXT NOT NULL, created TEXT NOT NULL);
"""
PROJECT_TABLES = ("revisions", "stages", "changes", "calls", "settings", "stage_definitions")
GATE_TABLES = ("config", "runs", "evaluations", "attempts", "checkpoints")
META_SQL = """CREATE TABLE control_meta(id INTEGER PRIMARY KEY CHECK(id=1), schema_version INTEGER NOT NULL CHECK(schema_version=1));
INSERT INTO control_meta VALUES(1,1);
"""


def initialize(path: Path):
    plain(path)
    if path.exists():
        raise Refused("control database must be new")
    with closing(sqlite3.connect(path)) as con:
        # Reuse established names, adding the FKs at their ownership boundary.
        sql = PROJECT_SQL.replace("version INTEGER, packet_hash", "version INTEGER REFERENCES revisions(version), packet_hash")
        sql += GATE_SQL.replace("run_id TEXT NOT NULL", "run_id TEXT NOT NULL REFERENCES runs(id)")
        sql = sql.replace("run_id TEXT UNIQUE NOT NULL", "run_id TEXT UNIQUE NOT NULL REFERENCES runs(id)")
        sql = sql.replace("evaluation_id TEXT UNIQUE NOT NULL", "evaluation_id TEXT UNIQUE NOT NULL REFERENCES evaluations(id)")
        con.executescript(sql + META_SQL + f"PRAGMA user_version={VERSION};")


@contextmanager
def connection(path: Path):
    plain(path)
    # mode=rw prevents an accidentally missing file from becoming an empty DB.
    con = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys=ON")
        if path.name == DATABASE:
            if con.execute("PRAGMA user_version").fetchone()[0] != VERSION:
                raise Refused("unsupported control schema version")
            meta = con.execute("SELECT schema_version FROM control_meta WHERE id=1").fetchall()
            if len(meta) != 1 or meta[0][0] != VERSION:
                raise Refused("invalid control schema metadata")
        with con:
            yield con
    finally:
        con.close()


def database_for(root: Path, component: str) -> Path:
    plain(root)
    unified = root / DATABASE
    legacy = root / ("project.sqlite3" if component == "project" else "gate.sqlite3")
    if unified.exists():
        if any((root / name).exists() for name in ("project.sqlite3", "gate.sqlite3")):
            raise Refused("ambiguous legacy and unified stores")
        selected = unified
    else:
        selected = legacy
    if not selected.is_file():
        raise Refused(f"{component} store not initialized")
    with connection(selected) as con:
        table = "revisions" if component == "project" else "config"
        if not con.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone():
            raise Refused(f"{component} store not initialized")
    return selected


class ControlStore:
    def __init__(self, root: Path):
        self.root = root.absolute()
        self.db = self.root / DATABASE
        with connection(self.db):
            pass

    def transaction(self):
        """Trusted application transaction across project and Gate tables."""
        return connection(self.db)

    def project_repository(self):
        from ..project import ProjectBook
        return ProjectBook(self.root)

    def run_repository(self):
        from ..core import Gate
        return Gate(self.root)
