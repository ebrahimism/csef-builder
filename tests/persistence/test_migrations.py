"""Preservation, rollback copies and authority regressions for control schema v1."""
import json
from pathlib import Path
import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager

import pytest

from csef_gate.contracts import ChangeProposal, ProjectRevision, StageSpec, VerificationRecord, checked
from csef_gate.core import Gate, Refused, digest, encoded
from csef_gate.persistence.migrations import migrate, preflight, rollback_copy
from csef_gate.persistence.sqlite import (
    DATABASE, GATE_SQL, GATE_TABLES, PROJECT_SQL, PROJECT_TABLES, ControlStore,
)
from csef_gate.project import ProjectBook


ANSWERS = {"users": "owner", "workflow": "input/result", "success": "preserve", "constraints": "offline"}
FACTS = [{"id": "REQ-101", "kind": "requirement", "text": "اطلاعات قبلی حفظ شوند\nخط دوم"},
         {"id": "ADR-001", "kind": "decision", "text": "Gate retains authority"}]


@contextmanager
def dbconn(path):
    with closing(sqlite3.connect(path)) as con:
        with con:
            yield con


class UnitExecutor:
    def probe(self, **kwargs):
        return {"verified": True, "backend": "UNIT_TEST_FAKE"}

    def run(self, **kwargs):
        return {"exit_code": 0, "stdout": "1", "stderr": "", "timed_out": False, "overflow": False}


def setup_pair(tmp_path):
    book = ProjectBook.create(tmp_path / "book", "حفظ هدف", ANSWERS, FACTS)
    packet = book.begin("discovery")
    book.finish("discovery", packet_hash=digest(encoded(packet)), artifacts={"brief.md": "سند اصلی".encode()},
                checks=[{"id": "fixture", "passed": True, "basis": "test fixture only"}])
    book.suggest_change({"type": "engineering_proposal", "text": "retain as draft"})
    book.reserve_call("interrupted-review")
    project = tmp_path / "code"
    project.mkdir()
    (project / "app.py").write_text("print(1)\n", encoding="utf-8")
    spec = {"version": 1, "objective": "print one", "source_files": ["app.py"], "editable_files": ["app.py"],
            "entrypoint": "app.py", "max_attempts": 2, "agent_timeout_s": 10, "case_timeout_s": 1,
            "cases": [{"id": "ONE", "args": [], "exit_code": 0, "stdout_json": 1}]}
    path = tmp_path / "acceptance.json"
    path.write_bytes(encoded(spec))
    gate = Gate.initialize(tmp_path / "gate", project, path)
    run = gate.prepare()
    gate.evaluate(run, UnitExecutor())
    return book, gate, run


def legacy_copy(root, target, ddl, tables, filename):
    """Materialize the original version-0 DB schema, not a new-schema rename."""
    shutil.copytree(root, target, ignore=shutil.ignore_patterns(DATABASE))
    with dbconn(root / DATABASE) as source, dbconn(target / filename) as dest:
        dest.executescript(ddl)
        for table in tables:
            rows = source.execute(f'SELECT * FROM "{table}"').fetchall()
            if table in ("evaluations", "attempts", "checkpoints"):
                columns = [r[1] for r in source.execute(f'PRAGMA table_info("{table}")')]
                for i, row in enumerate(rows):
                    row = list(row)
                    for name in {"snapshot", "report", "artifact"} & set(columns):
                        pos = columns.index(name)
                        row[pos] = str(target / Path(row[pos]).relative_to(root))
                    rows[i] = row
            if rows:
                marks = ",".join("?" for _ in rows[0])
                dest.executemany(f'INSERT INTO "{table}" VALUES({marks})', rows)


def tree_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("legacy", [False, True])
def test_migration_preserves_data_and_artifacts_and_requires_fresh_gate_execution(tmp_path, legacy):
    book, gate, run = setup_pair(tmp_path)
    if legacy:
        legacy_copy(book.root, tmp_path / "legacy-book", PROJECT_SQL, PROJECT_TABLES, "project.sqlite3")
        legacy_copy(gate.root, tmp_path / "legacy-gate", GATE_SQL, GATE_TABLES, "gate.sqlite3")
        book, gate = ProjectBook(tmp_path / "legacy-book"), Gate(tmp_path / "legacy-gate")
    before_book, before_gate = tree_bytes(book.root), tree_bytes(gate.root)
    original = book.status()
    target = tmp_path / "combined"
    assert migrate(book.root, gate.root, target, offline=True)["status"] == "migrated"
    assert tree_bytes(book.root) == before_book and tree_bytes(gate.root) == before_gate
    merged_book, merged_gate = ProjectBook(target), Gate(target)
    assert merged_book.db == merged_gate.db == target / DATABASE
    assert merged_book.status() == original
    assert merged_book.packet("architecture")["handoffs"][0]["stage"] == "discovery"
    with pytest.raises(Refused, match="trusted verification"):
        merged_gate.accept(run)
    assert migrate(book.root, gate.root, target, offline=True)["status"] == "unchanged"
    assert merged_gate.evaluate(run, UnitExecutor())["status"] == "pass"
    assert merged_gate.accept(run)["evaluation_id"]
    with pytest.raises(Refused, match="changed"):
        migrate(book.root, gate.root, target, offline=True)


def test_rollback_restores_new_copies_even_after_live_store_changes(tmp_path):
    book, gate, run = setup_pair(tmp_path)
    original = book.current()
    merged, restored = tmp_path / "merged", tmp_path / "restored"
    migrate(book.root, gate.root, merged, offline=True)
    ProjectBook(merged).amend(replace_facts={"REQ-101": "explicit later owner amendment"}, reason="owner")
    assert rollback_copy(merged, restored)["status"] == "restored_copy"
    assert ProjectBook(restored / "project").current() == original
    restored_gate = Gate(restored / "gate")
    with pytest.raises(Refused):
        restored_gate.accept(run)
    restored_gate.evaluate(run, UnitExecutor())
    assert restored_gate.accept(run)["snapshot"].startswith(str(restored / "gate"))
    with pytest.raises(Refused, match="must be new"):
        rollback_copy(merged, restored)
    assert book.current() == original


def test_shared_transaction_rolls_back_project_and_gate_together(tmp_path):
    book, gate, run = setup_pair(tmp_path)
    target = tmp_path / "merged"
    migrate(book.root, gate.root, target, offline=True)
    store = ControlStore(target)
    with pytest.raises(RuntimeError):
        with store.transaction() as con:
            con.execute("UPDATE stages SET status='stale'")
            con.execute("UPDATE runs SET attempts=attempts+1")
            raise RuntimeError("simulate failure between the two repositories")
    assert store.project_repository().status()["stages"] == book.status()["stages"]
    with store.run_repository().connect() as con:
        assert con.execute("SELECT attempts FROM runs WHERE id=?", (run,)).fetchone()[0] == 0
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO attempts VALUES('orphan','missing','started','path','time')")


def test_attach_is_serialized_and_never_overwrites_existing_gate(tmp_path):
    book, gate, _ = setup_pair(tmp_path)
    with gate.connect() as con:
        project = Path(con.execute("SELECT project FROM config").fetchone()[0])
    spec = gate.root / "spec.json"
    def attach(_):
        try:
            return Gate.initialize(book.root, project, spec, attach=True)
        except Refused:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attach, range(2)))
    assert sum(r is not None for r in results) == 1
    assert ProjectBook(book.root).current()["facts"] == FACTS
    with Gate(book.root).connect() as con:
        assert con.execute("SELECT count(*) FROM config").fetchone()[0] == 1


@pytest.mark.parametrize("change", ["trigger", "columns", "version", "collision", "source_changed", "missing_stage_defs"])
def test_preflight_rejects_unknown_inputs_and_supports_known_old_pipeline(tmp_path, change):
    book, gate, _ = setup_pair(tmp_path)
    if change == "missing_stage_defs":
        legacy_copy(book.root, tmp_path / "old", PROJECT_SQL, PROJECT_TABLES, "project.sqlite3")
        book = ProjectBook(tmp_path / "old")
        with book.connection() as con:
            con.execute("DROP TABLE stage_definitions")
        migrate(book.root, gate.root, tmp_path / "merged", offline=True)
        assert ProjectBook(tmp_path / "merged").packet("architecture")["role"] == "architect"
        return
    if change == "trigger":
        with book.connection() as con:
            con.execute("CREATE TRIGGER extra AFTER INSERT ON changes BEGIN DELETE FROM revisions; END")
    elif change == "columns":
        with book.connection() as con:
            con.execute("ALTER TABLE revisions ADD COLUMN verdict TEXT")
    elif change == "version":
        with book.connection() as con:
            con.execute("PRAGMA user_version=999")
    elif change == "collision":
        (book.root / "shared.txt").write_text("a")
        (gate.root / "shared.txt").write_text("b")
    else:
        target = tmp_path / "merged"
        migrate(book.root, gate.root, target, offline=True)
        book.suggest_change({"new": "source changed"})
        with pytest.raises(Refused, match="changed"):
            migrate(book.root, gate.root, target, offline=True)
        return
    with pytest.raises(Refused):
        preflight(book.root, gate.root, tmp_path / "merged")
    assert not (tmp_path / "merged").exists()


def test_backup_tampering_nested_destination_and_live_overwrite_are_refused(tmp_path):
    book, gate, _ = setup_pair(tmp_path)
    with pytest.raises(Refused, match="offline"):
        migrate(book.root, gate.root, tmp_path / "merged")
    with pytest.raises(Refused, match="disjoint"):
        migrate(book.root, gate.root, book.root / "nested", offline=True)
    target = tmp_path / "merged"
    migrate(book.root, gate.root, target, offline=True)
    (target / "migration-backup/gate/spec.json").write_text("tampered")
    with pytest.raises(Refused, match="modified"):
        rollback_copy(target, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_completed_legacy_checkpoint_stays_historical_and_immutable(tmp_path):
    book, gate, run = setup_pair(tmp_path)
    old_checkpoint = gate.accept(run)
    target = tmp_path / "merged"
    migrate(book.root, gate.root, target, offline=True)
    merged = Gate(target)
    with merged.connect() as con:
        ck = con.execute("SELECT * FROM checkpoints").fetchone()
        assert ck["id"] == old_checkpoint["id"]
        assert ck["snapshot"].startswith(str(target))
    with pytest.raises(Refused):
        merged.accept(run)
    with pytest.raises(Refused, match="accepted"):
        merged.evaluate(run, UnitExecutor())


def test_committed_wal_content_is_included_in_backups(tmp_path):
    book, gate, _ = setup_pair(tmp_path)
    legacy_copy(book.root, tmp_path / "legacy", PROJECT_SQL, PROJECT_TABLES, "project.sqlite3")
    book = ProjectBook(tmp_path / "legacy")
    with dbconn(book.db) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("INSERT INTO changes(proposal,status,created) VALUES(?,?,?)", ('{"wal":"committed"}', "proposed", "now"))
        writer.commit()
        target = tmp_path / "merged"
        migrate(book.root, gate.root, target, offline=True)
        with dbconn(target / "migration-backup/project/project.sqlite3") as backup:
            assert backup.execute("SELECT proposal FROM changes ORDER BY id DESC LIMIT 1").fetchone()[0] == '{"wal":"committed"}'
        assert ProjectBook(target).status()["pending_changes"] == book.status()["pending_changes"]


def test_failed_copy_publishes_nothing_and_source_is_preserved(tmp_path, monkeypatch):
    from csef_gate.persistence import migrations
    book, gate, _ = setup_pair(tmp_path)
    before = tree_bytes(book.root), tree_bytes(gate.root)
    def fail(*args, **kwargs):
        raise OSError("simulated storage failure")
    with monkeypatch.context() as context:
        context.setattr(migrations, "_copy_files", fail)
        with pytest.raises(OSError, match="simulated"):
            migrate(book.root, gate.root, tmp_path / "merged", offline=True)
    assert not (tmp_path / "merged").exists()
    assert before == (tree_bytes(book.root), tree_bytes(gate.root))
    assert migrate(book.root, gate.root, tmp_path / "merged", offline=True)["status"] == "migrated"


def test_extra_legacy_database_cannot_make_a_published_ambiguous_store(tmp_path):
    book, gate, _ = setup_pair(tmp_path)
    legacy_copy(book.root, tmp_path / "legacy", PROJECT_SQL, PROJECT_TABLES, "project.sqlite3")
    (tmp_path / "legacy/gate.sqlite3").write_text("unrelated data")
    with pytest.raises(Refused, match="conflicts"):
        migrate(tmp_path / "legacy", gate.root, tmp_path / "merged", offline=True)
    assert not (tmp_path / "merged").exists()


@pytest.mark.parametrize("model,data", [
    (StageSpec, {"name": "discovery", "title": "title", "role": "analyst"}),
    (ChangeProposal, {"summary": "s", "files": [{"path": "app.py", "content": "print(1)"}]}),
    (ProjectRevision, {"version": 1, "sha256": "a" * 64, "goal": "g", "answers": {}, "facts": FACTS}),
])
def test_contracts_refuse_unknown_properties_and_noninteger_schema_versions(model, data):
    checked(model, data)
    for version in (True, 1.0, "1", 2):
        with pytest.raises(Refused):
            checked(model, {**data, "schema_version": version})
    with pytest.raises(Refused):
        checked(model, {**data, "verdict": "PASS"})


def test_unknown_proposals_or_reports_cannot_mint_pass(tmp_path):
    _, gate, run = setup_pair(tmp_path)
    with pytest.raises(Refused):
        gate.apply_proposal(run, {"summary": "fake", "files": [{"path": "app.py", "content": "print(1)"}], "verdict": "PASS"})
    report = gate.evaluate(run, UnitExecutor())
    with pytest.raises(Refused):
        checked(VerificationRecord, {**report, "permit": "PASS"})
    with gate.connect() as con:
        row = con.execute("SELECT * FROM evaluations WHERE id=?", (report["evaluation_id"],)).fetchone()
        path = Path(row["report"])
        forged = encoded({**report, "unknown_authority": "PASS"})
        path.write_bytes(forged)
        # Even a locally matching report hash does not bypass the runtime schema.
        con.execute("UPDATE evaluations SET report_hash=? WHERE id=?", (digest(forged), row["id"]))
    with pytest.raises(Refused, match="VerificationRecord"):
        gate.accept(run)


def test_dotdot_aliases_cannot_nest_migration_or_restore(tmp_path):
    book, gate, _ = setup_pair(tmp_path)
    # An existing sibling makes this a traversable alias on Windows too.
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    alias = sibling / ".." / "book" / "nested"
    before = tree_bytes(book.root), tree_bytes(gate.root)
    with pytest.raises(Refused, match="disjoint"):
        migrate(book.root, gate.root, alias, offline=True)
    assert before == (tree_bytes(book.root), tree_bytes(gate.root))
    merged = tmp_path / "merged"
    migrate(book.root, gate.root, merged, offline=True)
    before = tree_bytes(merged)
    with pytest.raises(Refused, match="disjoint"):
        rollback_copy(merged, sibling / ".." / "merged" / "restored")
    assert tree_bytes(merged) == before


def test_attach_rejects_aliased_project_inside_control(tmp_path):
    book, gate, _ = setup_pair(tmp_path)
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    project = book.root / "nested"
    project.mkdir()
    (project / "app.py").write_text("print(1)", encoding="utf-8")
    before = tree_bytes(book.root)
    with pytest.raises(Refused, match="disjoint"):
        Gate.initialize(book.root, sibling / ".." / "book" / "nested", gate.root / "spec.json", attach=True)
    assert tree_bytes(book.root) == before


def test_restore_and_repeat_reject_malformed_manifests_before_writing(tmp_path):
    book, gate, _ = setup_pair(tmp_path)
    merged = tmp_path / "merged"
    migrate(book.root, gate.root, merged, offline=True)
    manifest_path = merged / "migration.json"
    original = json.loads(manifest_path.read_bytes())
    variants = [[], {**original, "schema_version": True}, {**original, "schema_version": 1.0},
                {**original, "schema_version": 2}, {**original, "sources": {}},
                {**original, "files": []}, {**original, "files": {}},
                {**original, "unknown_authority": "PASS"}]
    for key, value in (("database", "../control.sqlite3"), ("root", "relative"), ("tables", [])):
        changed = json.loads(json.dumps(original))
        changed["sources"]["gate"][key] = value
        variants.append(changed)
    for record in variants:
        manifest_path.write_bytes(encoded(record))
        before = tree_bytes(merged)
        staging = set(tmp_path.glob("m-*"))
        with pytest.raises(Refused):
            rollback_copy(merged, tmp_path / "restored")
        with pytest.raises(Refused):
            migrate(book.root, gate.root, merged, offline=True)
        assert tree_bytes(merged) == before
        assert set(tmp_path.glob("m-*")) == staging
        assert not (tmp_path / "restored").exists()
    manifest_path.write_bytes(encoded(original))
    assert rollback_copy(merged, tmp_path / "restored")["status"] == "restored_copy"
