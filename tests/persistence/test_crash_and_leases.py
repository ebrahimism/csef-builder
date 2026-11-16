"""Cross-controller/process ownership, crash and immutable-content regressions."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
import json
import os
import subprocess
import sys

import pytest

from csef_gate.core import Refused, digest, encoded
from csef_gate.project import ProjectBook
from csef_gate.persistence.artifacts import ArtifactStore
from csef_gate.persistence.events import Journal
from csef_gate.persistence.leases import Lease, LeaseStore, assert_current
from csef_gate.persistence.migrations import migrate


ANSWERS = {"users": "owner", "workflow": "input/result", "success": "preserve", "constraints": "offline"}


def create(tmp_path):
    return ProjectBook.create(tmp_path / "book", "هدف ثابت", ANSWERS,
                              [{"id": "REQ-101", "kind": "requirement", "text": "Keep prior data"}])


def finish(book, packet, passed=True):
    return book.finish("discovery", packet_hash=digest(encoded(packet)), artifacts={"brief.md": b"real document"},
                       checks=[{"id": "test-fixture", "passed": passed, "basis": "controller observation fixture"}])


def test_two_controllers_cannot_begin_the_same_stage(tmp_path):
    book = create(tmp_path)
    def run(_):
        controller = ProjectBook(book.root)
        try:
            return controller, controller.begin("discovery")
        except Refused:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    winners = [r for r in results if r is not None]
    assert len(winners) == 1
    assert len(Journal(book.root).pending()) == 1
    winner, packet = winners[0]
    # A different process instance knowing the packet still has no lease.
    with pytest.raises(Refused, match="lease|input"):
        finish(ProjectBook(book.root), packet)
    finish(winner, packet)
    assert Journal(book.root).pending() == []
    assert book.status()["stages"][0]["status"] == "ready_for_next"
    assert book.status()["release_approved"] is False


def test_same_controller_old_packet_cannot_complete_a_new_attempt(tmp_path):
    book = create(tmp_path)
    old = book.begin("discovery")
    finish(book, old, passed=False)
    new = book.begin("discovery")
    assert old["execution_id"] != new["execution_id"]
    with pytest.raises(Refused, match="input"):
        finish(book, old)
    finish(book, new)


def test_expiry_never_automatically_takes_over_or_accepts_late_worker(tmp_path, monkeypatch):
    import csef_gate.persistence.leases as module
    clock = [100.0]
    monkeypatch.setattr(module.time, "time", lambda: clock[0])
    book = create(tmp_path)
    packet = book.begin("discovery", lease_ttl=5)
    lease = book._stage_leases["discovery"]
    clock[0] = 106.0
    store = LeaseStore(book.root)
    with pytest.raises(Refused, match="held"):
        store.acquire("discovery", "another controller")
    with pytest.raises(Refused, match="expired"):
        finish(book, packet)
    with pytest.raises(Refused, match="reconcile"):
        store.recover(lease)
    store.recover(lease, reconciled=True)
    new = ProjectBook(book.root)
    new_packet = new.begin("discovery")
    with pytest.raises(Refused, match="stale"):
        store.recover(lease, reconciled=True)
    with pytest.raises(Refused, match="stale"):
        with book.connection() as con:
            assert_current(con, lease)
    finish(new, new_packet)
    history = Journal(book.root).replay("stage:discovery")
    assert [r["body"]["status"] for r in history if r["kind"] == "outcome"] == ["unknown", "ok"]


def test_owner_amendment_fences_running_worker_in_the_same_transaction(tmp_path):
    book = create(tmp_path)
    old = book.begin("discovery")
    lease = book._stage_leases["discovery"]
    book.amend(replace_facts={"REQ-101": "owner revised the goal"}, reason="explicit owner amendment")
    with pytest.raises(Refused):
        finish(book, old)
    with book.connection() as con:
        assert con.execute("SELECT active FROM stage_leases").fetchone()[0] == 1
        assert con.execute("SELECT status FROM stages WHERE name='discovery'").fetchone()[0] == "stale"
    assert Journal(book.root).pending()[0]["outcome"] == "unknown"
    with pytest.raises(Refused):
        LeaseStore(book.root).heartbeat(lease)
    with pytest.raises(Refused, match="held"):
        book.begin("discovery")
    LeaseStore(book.root).recover(lease, reconciled=True)
    finish(book, book.begin("discovery"))


def test_journal_records_one_terminal_outcome_and_never_treats_pass_claim_as_authority(tmp_path):
    book = create(tmp_path)
    journal = Journal(book.root)
    intent = journal.append_intent("run:fixture", "external_effect", {"source": "fixture"})
    assert journal.pending()[0]["outcome"] == "unknown"
    journal.append_outcome(intent, "ok", {"claim": "PASS", "release_approved": True})
    before = journal.replay()
    with pytest.raises(Refused, match="already"):
        journal.append_outcome(intent, "ok", {})
    with pytest.raises(Refused):
        journal.append_outcome("missing", "ok", {})
    with pytest.raises(Refused):
        journal.append_outcome(intent, "pass", {})
    assert journal.replay() == before
    assert book.status()["stages"][0]["status"] == "pending"
    assert book.status()["release_approved"] is False


def test_actual_process_death_leaves_unknown_intent_and_blocks_other_controller(tmp_path):
    book = create(tmp_path)
    code = "from pathlib import Path; from csef_gate.project import ProjectBook; import os,sys; b=ProjectBook(Path(sys.argv[1])); b.begin('discovery'); os._exit(73)"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src")}
    result = subprocess.run([sys.executable, "-c", code, str(book.root)], env=env, capture_output=True, timeout=30)
    assert result.returncode == 73, result.stderr
    assert len(Journal(book.root).pending()) == 1
    with pytest.raises(Refused, match="running"):
        ProjectBook(book.root).begin("discovery")
    with pytest.raises(Refused, match="previous"):
        book.packet("architecture")
    assert book.status()["release_approved"] is False


def test_artifacts_are_bounded_hashed_and_export_only_the_allowlist(tmp_path):
    book = create(tmp_path)
    store = ArtifactStore(book.root)
    data = "سند\nunchanged bytes".encode()
    ref = store.put(data, provenance="owner fixture")
    assert store.put(data) == ref
    assert store.get(ref["sha256"]) == data
    store.put(b"private unselected content")
    dest = tmp_path / "export"
    assert store.export_allowed({"docs/readme.md": ref}, dest)["files"] == 1
    assert [p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()] == ["docs/readme.md"]
    assert (dest / "docs/readme.md").read_bytes() == data
    for bad in (b"x" * 1_000_001, "not bytes"):
        with pytest.raises(Refused):
            store.put(bad)
    with pytest.raises(Refused):
        store.export_allowed({"../outside": ref}, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()
    path = store._path(ref["sha256"])
    path.write_bytes(b"tampered")
    with pytest.raises(Refused):
        store.get(ref["sha256"])
    with pytest.raises(Refused):
        store.put(data)


def test_returned_draft_releases_worker_but_never_advances_stage(tmp_path):
    from csef_gate.assistant import assist_stage
    book = create(tmp_path)
    class Client:
        def call(self, **kwargs):
            return {"summary": "draft", "questions": [], "drafts": [], "issues": [], "proposed_decisions": []}, {"exit_code": 0}
    assert assist_stage(book, "discovery", Client())["status"] == "draft_requires_validation"
    assert Journal(book.root).pending() == []
    assert book.status()["stages"][0]["status"] == "needs_revision"
    with pytest.raises(Refused):
        book.packet("architecture")
    other = ProjectBook(book.root)
    finish(other, other.begin("discovery"))


def test_unknown_provider_result_blocks_an_automatic_second_call(tmp_path):
    from csef_gate.assistant import assist_stage
    book = create(tmp_path)
    class Client:
        calls = 0
        def call(self, **kwargs):
            self.calls += 1
            raise Refused("provider outcome unknown")
    client = Client()
    with pytest.raises(Refused, match="provider"):
        assist_stage(book, "discovery", client)
    with pytest.raises(Refused, match="running"):
        assist_stage(ProjectBook(book.root), "discovery", client)
    assert client.calls == 1
    assert len(Journal(book.root).pending()) == 1
    assert book.status()["calls"][0]["status"] == "failed_or_unknown"


def test_unregistered_partial_or_complete_object_is_not_adopted(tmp_path):
    book = create(tmp_path)
    store = ArtifactStore(book.root)
    content = b"complete but without a committed metadata record"
    path = store._path(digest(content))
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    with pytest.raises(Refused, match="orphan"):
        store.put(content)
    with pytest.raises(Refused):
        store.get(digest(content))
    ref = store.put(b"registered")
    store._path(ref["sha256"]).unlink()
    with pytest.raises(Refused, match="missing"):
        store.put(b"registered")


def test_finish_rollback_preserves_unknown_intent_and_blocks_next_stage(tmp_path, monkeypatch):
    import csef_gate.persistence.leases as leases
    book = create(tmp_path)
    packet = book.begin("discovery")
    def interrupted(*args, **kwargs):
        raise OSError("interrupted before outcome commit")
    with monkeypatch.context() as context:
        context.setattr(leases, "release", interrupted)
        with pytest.raises(OSError):
            finish(book, packet)
    assert book.status()["stages"][0]["status"] == "running"
    assert len(Journal(book.root).pending()) == 1
    with pytest.raises(Refused):
        book.packet("architecture")
    finish(book, packet)
    assert Journal(book.root).pending() == []


def test_runtime_extension_and_active_lease_survive_copy_as_fenced_history(tmp_path):
    from test_migrations import setup_pair
    book, gate, _ = setup_pair(tmp_path)
    packet = book.begin("architecture")
    old = book._stage_leases["architecture"]
    # Both roots start local sequence numbers at 1; IDs, not seq, link events.
    journal = Journal(gate.root)
    intent = journal.append_intent("gate:fixture", "capture", {})
    journal.append_outcome(intent, "ok", {})
    target = tmp_path / "merged"
    migrate(book.root, gate.root, target, offline=True)
    copied = ProjectBook(target)
    with copied.connection() as con:
        with pytest.raises(Refused, match="stale"):
            assert_current(con, old)
    assert Journal(target).replay()[-1]["body"]["status"] == "unknown"
    assert copied.status()["stages"][1]["status"] == "stale"
    # Source execution is unchanged; migration never edits the original lease.
    with book.connection() as con:
        assert_current(con, old)
    from csef_gate.persistence.migrations import rollback_copy
    restored = tmp_path / "restored"
    rollback_copy(target, restored)
    with ProjectBook(restored / "project").connection() as con:
        with pytest.raises(Refused):
            assert_current(con, old)
    assert Journal(restored / "project").pending() == []
    assert any(r["event_id"] == intent for r in Journal(target).replay())
