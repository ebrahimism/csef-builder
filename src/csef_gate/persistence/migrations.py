"""Explicit offline copy migration. Sources are preserved; no in-place upgrade.

Pairing project and Gate roots is the caller's decision, never auto-discovery.
Backups use SQLite's backup API so committed WAL data is included. A failed
migration leaves its private staging copy for inspection and publishes nothing.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, closing, contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import uuid

from ..contracts import ProjectRevision, checked
from ..core import Gate, Refused, digest, encoded, plain, read_json
from ..project import ProjectBook, STAGES
from .sqlite import (
    DATABASE, GATE_SQL, GATE_TABLES, PROJECT_SQL, PROJECT_TABLES,
    VERSION, connection, database_for, initialize,
)


MANIFEST = "migration.json"
BACKUP = "migration-backup"


def _canonical(path: Path) -> Path:
    path = Path(path).absolute()
    # Check before resolving: resolution must not hide a junction or symlink.
    plain(path)
    path = path.resolve()
    plain(path)
    return path


def _read_manifest(store: Path) -> dict:
    plain(store / MANIFEST)
    record = read_json(store / MANIFEST)
    if (not isinstance(record, dict)
            or set(record) != {"schema_version", "sources", "files", "authority"}
            or type(record["schema_version"]) is not int
            or record["schema_version"] != VERSION
            or not isinstance(record["authority"], str)):
        raise Refused("unsupported migration manifest")

    def file_map(value):
        if not isinstance(value, dict):
            raise Refused("invalid migration file manifest")
        for name, sha in value.items():
            if (not isinstance(name, str) or not name or "\\" in name or ":" in name
                    or any(part in ("", ".", "..") for part in name.split("/"))
                    or not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha)):
                raise Refused("invalid migration file manifest")

    file_map(record["files"])
    sources = record["sources"]
    if not isinstance(sources, dict) or set(sources) != {"project", "gate"}:
        raise Refused("invalid migration sources")
    for kind, tables in (("project", PROJECT_TABLES), ("gate", GATE_TABLES)):
        source = sources[kind]
        if (not isinstance(source, dict)
                or set(source) != {"root", "database", "tables", "files", "fingerprint"}
                or not isinstance(source["root"], str) or not Path(source["root"]).is_absolute()
                or source["database"] not in (DATABASE, kind + ".sqlite3")
                or not isinstance(source["tables"], dict)):
            raise Refused("invalid migration source metadata")
        allowed_tables = [set(tables)]
        if kind == "project" and source["database"] == "project.sqlite3":
            allowed_tables.append(set(tables) - {"stage_definitions"})
        if (set(source["tables"]) not in allowed_tables
                or any(not isinstance(rows, list) or any(not isinstance(row, list) for row in rows)
                       for rows in source["tables"].values())):
            raise Refused("invalid migration source tables")
        file_map(source["files"])
        if source["fingerprint"] != digest(encoded([source["tables"], source["files"]])):
            raise Refused("invalid migration source fingerprint")
        prefix = BACKUP + "/" + kind + "/"
        backup_files = {name[len(prefix):]: sha for name, sha in record["files"].items()
                        if name.startswith(prefix)}
        if (set(backup_files) != set(source["files"]) | {source["database"]}
                or any(backup_files[name] != sha for name, sha in source["files"].items())):
            raise Refused("incomplete migration backup manifest")
    return record


def _tree(root: Path, excluded=()) -> dict[str, str]:
    plain(root)
    files, aliases = {}, set()
    for folder, dirs, names in os.walk(root):
        for name in sorted([*dirs, *names]):
            path = Path(folder) / name
            plain(path)
            relative = path.relative_to(root).as_posix()
            if relative in excluded:
                continue
            alias = relative.casefold()
            if alias in aliases:
                raise Refused("case-colliding migration path: " + relative)
            aliases.add(alias)
            if path.is_file():
                files[relative] = digest(path.read_bytes())
    return dict(sorted(files.items()))


def _disjoint(*paths):
    for i, path in enumerate(paths):
        plain(path)
        for other in paths[:i]:
            if path == other or path in other.parents or other in path.parents:
                raise Refused("migration paths must be disjoint trees")


def _schema(con, kind):
    """Inspect metadata only; never execute source sqlite_master SQL."""
    tables = PROJECT_TABLES if kind == "project" else GATE_TABLES
    version = con.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, VERSION):
        raise Refused("unsupported source schema version")
    objects = con.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
    if any(row[0] != "table" for row in objects):
        raise Refused("source triggers, views and custom indexes are unsupported")
    names = {row[1] for row in objects}
    expected = set(tables) if version == 0 else set(PROJECT_TABLES + GATE_TABLES) | {"control_meta"}
    # The original ProjectBook explicitly supported the pre-stage-definitions DB.
    if kind == "project" and version == 0 and "stage_definitions" not in names:
        expected.remove("stage_definitions")
    if names != expected:
        raise Refused("unsupported source tables")
    with closing(sqlite3.connect(":memory:")) as reference:
        reference.executescript(PROJECT_SQL + GATE_SQL)
        for name in names - {"control_meta"}:
            actual = [tuple(r)[1:] for r in con.execute(f'PRAGMA table_info("{name}")')]
            wanted = [tuple(r)[1:] for r in reference.execute(f'PRAGMA table_info("{name}")')]
            if actual != wanted:
                raise Refused("unsupported source columns: " + name)
    if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise Refused("source database integrity check failed")
    if version == VERSION:
        meta = con.execute("SELECT id,schema_version FROM control_meta").fetchall()
        if [tuple(r) for r in meta] != [(1, VERSION)]:
            raise Refused("unsupported source metadata")
        other = GATE_TABLES if kind == "project" else PROJECT_TABLES
        if any(con.execute(f'SELECT 1 FROM "{name}" LIMIT 1').fetchone() for name in other):
            raise Refused("source is already combined; do not merge unrelated stores")
    return [name for name in tables if name in names]


def _rows(con, tables):
    return {name: [list(row) for row in con.execute(f'SELECT * FROM "{name}" ORDER BY rowid')]
            for name in tables}


def _describe(root, kind, con):
    db = database_for(root, kind)
    tables = _schema(con, kind)
    rows = _rows(con, tables)
    excluded = (db.name, db.name + "-wal", db.name + "-shm", db.name + "-journal")
    files = _tree(root, excluded)
    reserved = {DATABASE, "project.sqlite3", "gate.sqlite3", MANIFEST, BACKUP}
    reserved |= {name + suffix for name in (DATABASE, "project.sqlite3", "gate.sqlite3")
                 for suffix in ("-wal", "-shm", "-journal")}
    if any(name.split("/")[0].casefold() in reserved for name in files):
        raise Refused("source data conflicts with migration metadata")
    singleton = "settings" if kind == "project" else "config"
    if len(rows[singleton]) != 1:
        raise Refused("source component requires exactly one " + singleton + " row")
    return {"root": str(root), "database": db.name, "tables": rows, "files": files,
            "fingerprint": digest(encoded([rows, files]))}


@contextmanager
def _sources(project, gate, *, lock=False):
    with ExitStack() as stack:
        result = {}
        for kind, root in (("project", project), ("gate", gate)):
            db = database_for(root, kind)
            if lock:
                # A separate reserved writer lock prevents source DB changes
                # while the read-only connection takes its backup snapshot.
                guard = sqlite3.connect(db.resolve().as_uri() + "?mode=rw", uri=True, timeout=1)
                stack.callback(guard.close)
                guard.execute("BEGIN IMMEDIATE")
            con = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
            stack.callback(con.close)
            con.execute("PRAGMA trusted_schema=OFF")
            con.execute("BEGIN")
            result[kind] = con
        yield result


def preflight(project: Path, gate: Path, destination: Path) -> dict:
    project, gate, destination = (_canonical(p) for p in (project, gate, destination))
    _disjoint(project, gate, destination)
    with _sources(project, gate) as sources:
        info = {kind: _describe(root, kind, sources[kind])
                for kind, root in (("project", project), ("gate", gate))}
    # Reject file/directory prefix collisions as well as same-name files.
    aliases = set()
    for kind in ("project", "gate"):
        for name in info[kind]["files"]:
            alias = name.casefold()
            if alias in aliases or any(alias.startswith(old + "/") or old.startswith(alias + "/") for old in aliases):
                raise Refused("source path collision: " + name)
            aliases.add(alias)
    # Validate the supported project body and current frozen Gate inputs.
    ProjectBook(project).current()
    for row in info["project"]["tables"]["revisions"]:
        body = json.loads(row[1])
        if not isinstance(body, dict) or set(body) != {"goal", "answers", "facts"} or digest(encoded(body)) != row[2]:
            raise Refused("invalid historical project revision")
        checked(ProjectRevision, {"version": row[0], "sha256": row[2], **body})
    Gate(gate).spec()
    # No host registry change is needed. Keep staging short on Windows and
    # reject an unsupported destination before copying any data.
    if os.name == "nt":
        stage_example = destination.parent / ("m-" + "0" * 12)
        for root in (destination, stage_example):
            for kind in ("project", "gate"):
                for name in info[kind]["files"]:
                    if max(len(str(root / name)), len(str(root / BACKUP / kind / name))) >= 260:
                        raise Refused("destination paths exceed Windows limits; choose a shorter destination")
    return info


def _copy_files(source, destination, files):
    for name, expected in files.items():
        # Names come from a checked tree, not caller-supplied manifest paths.
        path = source / name
        plain(path)
        data = path.read_bytes()
        if digest(data) != expected:
            raise Refused("source artifact changed during copy: " + name)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)


def _rebase(con, original: Path, target: Path):
    for table, columns in (("evaluations", ("snapshot", "report")), ("attempts", ("artifact",)), ("checkpoints", ("snapshot",))):
        for row in con.execute(f'SELECT rowid,* FROM "{table}"').fetchall():
            values = []
            for column in columns:
                old = Path(row[column]).absolute()
                plain(old)
                if not old.is_relative_to(original) or old == original:
                    raise Refused("stored Gate artifact escapes its source root")
                relative = old.relative_to(original)
                if ".." in relative.parts:
                    raise Refused("noncanonical Gate artifact path")
                values.append(str(target / relative))
            assignments = ",".join(f'"{column}"=?' for column in columns)
            con.execute(f'UPDATE "{table}" SET {assignments} WHERE rowid=?', (*values, row["rowid"]))
    # Original statuses and bytes remain in backups. Accepted runs stay immutable;
    # every other imported run needs new execution before Gate.accept can succeed.
    con.execute("UPDATE runs SET status='migration_review' WHERE status!='accepted'")
    con.execute("UPDATE evaluations SET status='stale'")
    con.execute("UPDATE attempts SET status='failed_or_unknown' WHERE status='started'")


@contextmanager
def _publication_lock(destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock = destination.with_name(destination.name + ".migration.lock")
    plain(lock)
    handle = lock.open("xb")
    try:
        yield
    finally:
        handle.close()
        lock.unlink()


def migrate(project: Path, gate: Path, destination: Path, *, offline=False) -> dict:
    if offline is not True:
        raise Refused("stop source writers and explicitly select offline migration")
    project, gate, destination = (_canonical(p) for p in (project, gate, destination))
    info = preflight(project, gate, destination)
    with _publication_lock(destination):
        if destination.exists():
            record = _read_manifest(destination)
            if (record.get("sources") != info or record.get("files") != _tree(destination, (MANIFEST,))):
                raise Refused("migration source or destination changed; never overwrite")
            return {"status": "unchanged", "destination": str(destination)}
        stage = destination.parent / ("m-" + uuid.uuid4().hex[:12])
        _disjoint(project, gate, stage)
        stage.mkdir()
        with _sources(project, gate, lock=True) as sources:
            locked_info = {kind: _describe(root, kind, sources[kind])
                           for kind, root in (("project", project), ("gate", gate))}
            if locked_info != info:
                raise Refused("source changed after preflight")
            for kind, root in (("project", project), ("gate", gate)):
                backup = stage / BACKUP / kind
                backup.mkdir(parents=True)
                _copy_files(root, backup, info[kind]["files"])
                with closing(sqlite3.connect(backup / info[kind]["database"])) as target:
                    sources[kind].backup(target)
                _copy_files(root, stage, info[kind]["files"])
            initialize(stage / DATABASE)
            with connection(stage / DATABASE) as con:
                con.execute("BEGIN IMMEDIATE")
                for kind in ("project", "gate"):
                    for table, rows in info[kind]["tables"].items():
                        for row in rows:
                            values = ",".join("?" for _ in row)
                            con.execute(f'INSERT INTO "{table}" VALUES({values})', row)
                if "stage_definitions" not in info["project"]["tables"]:
                    con.executemany("INSERT INTO stage_definitions VALUES(?,?,?,?)", [(i, *s) for i, s in enumerate(STAGES)])
                _rebase(con, gate, destination)
                con.execute("UPDATE stages SET status='stale' WHERE status='running'")
                if con.execute("PRAGMA foreign_key_check").fetchall():
                    raise Refused("source contains orphaned records")
            for kind, root in (("project", project), ("gate", gate)):
                if _describe(root, kind, sources[kind]) != info[kind]:
                    raise Refused("source changed during migration")
            record = {"schema_version": VERSION, "sources": info, "files": _tree(stage),
                      "authority": "historical verification quarantined; fresh evaluation required"}
            (stage / MANIFEST).write_bytes(encoded(record))
            if destination.exists():
                raise Refused("destination appeared during migration")
            os.rename(stage, destination)
    return {"status": "migrated", "destination": str(destination), "release_approved": False}


def rollback_copy(store: Path, destination: Path) -> dict:
    """Restore verified pre-migration data into NEW roots, never overwrite live data."""
    store, destination = _canonical(store), _canonical(destination)
    _disjoint(store, destination)
    record = _read_manifest(store)
    actual = _tree(store / BACKUP)
    expected = {name.removeprefix(BACKUP + "/"): value for name, value in record["files"].items() if name.startswith(BACKUP + "/")}
    if actual != expected:
        raise Refused("migration backup was modified")
    with _publication_lock(destination):
        if destination.exists():
            raise Refused("restore destination must be new")
        stage = destination.parent / ("m-" + uuid.uuid4().hex[:12])
        stage.mkdir()
        for kind in ("project", "gate"):
            source = store / BACKUP / kind
            output = stage / kind
            output.mkdir()
            files = {name.removeprefix(kind + "/"): value for name, value in actual.items() if name.startswith(kind + "/")}
            _copy_files(source, output, files)
            if kind == "gate":
                # Rebase copied paths and quarantine authority on restored copies.
                dbname = record["sources"][kind]["database"]
                if dbname not in (DATABASE, "gate.sqlite3"):
                    raise Refused("unsupported backup database path")
                with connection(output / dbname) as con:
                    _rebase(con, Path(record["sources"][kind]["root"]), destination / kind)
        if destination.exists():
            raise Refused("restore destination appeared during copy")
        os.rename(stage, destination)
    return {"status": "restored_copy", "destination": str(destination), "release_approved": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    for name in ("preflight", "migrate"):
        cmd = sub.add_parser(name)
        for flag in ("project", "gate", "destination"):
            cmd.add_argument("--" + flag, type=Path, required=True)
        if name == "migrate":
            cmd.add_argument("--offline", action="store_true")
    restore = sub.add_parser("restore-copy")
    restore.add_argument("--store", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.operation == "restore-copy":
            result = rollback_copy(args.store, args.destination)
        elif args.operation == "preflight":
            result = preflight(args.project, args.gate, args.destination)
        else:
            result = migrate(args.project, args.gate, args.destination, offline=args.offline)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (Refused, ValueError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
