"""Provenance and owner acceptance exercise real stored revisions, not labels."""
from concurrent.futures import ThreadPoolExecutor
import json
import importlib.util
from pathlib import Path

import pytest

from csef_gate.core import Refused, encoded
from csef_gate.project import ProjectBook
from csef_gate.lifecycle.projects import ProjectService
from csef_gate.lifecycle.requirements import Requirements
from csef_gate.lifecycle.decisions import Decisions


ANSWERS = {"users": "owner", "workflow": "input/result", "success": "preserve", "constraints": "offline"}


def migration_fixtures():
    path = Path(__file__).resolve().parents[1] / "persistence/test_migrations.py"
    spec = importlib.util.spec_from_file_location("lifecycle_migration_fixtures", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def setup(tmp_path):
    book = ProjectBook.create(tmp_path / "book", "هدف اولیه", ANSWERS,
                [{"id": "REQ-101", "kind": "requirement", "text": "حفظ داده‌های قدیمی"}])
    return book, ProjectService(book)


def accept(service, proposal, version=1):
    statement = service.record_owner_statement("این پیشنهاد مشخص پذیرفته است", expected_version=version, approves=proposal)
    return service.accept_proposal(proposal, statement, expected_version=version)


def test_model_and_assumption_never_change_accepted_goal_or_facts(tmp_path):
    book, service = setup(tmp_path)
    before = book.current()
    req = Requirements(book)
    proposal = req.propose_requirement("حذف همه داده‌ها", source_ref="model-call:1", fact_id="REQ-101")
    assumption = req.record_assumption("شبکه همیشه وصل است", source_ref="model-call:1")
    Decisions(book).propose_decision("استفاده از پایگاه دیگر", source_ref="model-call:2")
    assert book.current() == before
    with pytest.raises(Refused):
        service.accept_proposal(proposal, 999, expected_version=1)
    with pytest.raises(Refused, match="admissible"):
        accept(service, assumption)
    assert book.current() == before
    assert book.status()["release_approved"] is False


def test_owner_acceptance_links_exact_proposal_statement_revision_and_history(tmp_path):
    book, service = setup(tmp_path)
    proposal = Requirements(book).propose_requirement("حفظ داده و خروجی پشتیبان", source_ref="call:2", fact_id="REQ-101")
    result = accept(service, proposal)
    assert result["version"] == 2 and result["facts"][0]["text"] == "حفظ داده و خروجی پشتیبان"
    history = ProjectService(ProjectBook(book.root)).history("REQ-101")
    assert [r["status"] for r in history] == ["superseded", "accepted"]
    assert history[0]["fact"]["text"] == "حفظ داده‌های قدیمی"
    assert history[0]["source"]["kind"] == "legacy_unattributed"
    assert history[1]["source"]["proposal_id"] == proposal
    with book.connection() as con:
        audit = json.loads(con.execute("SELECT proposal FROM changes WHERE status='recorded'").fetchone()[0])
        source = audit["source"]
        statement = json.loads(con.execute("SELECT proposal FROM changes WHERE id=?", (source["ref"],)).fetchone()[0])
        assert statement["text"] == "این پیشنهاد مشخص پذیرفته است"
        assert audit["from_version"] == 1 and audit["to_version"] == 2
        assert audit["fact_changes"][0]["id"] == "REQ-101"
    assert book.current()["goal"] == "هدف اولیه"


def test_owner_can_add_decision_with_stable_id_and_explicit_source(tmp_path):
    book, service = setup(tmp_path)
    proposal = Decisions(book).propose_decision("معماری ثبت‌شده", source_ref="architecture:1")
    result = accept(service, proposal)
    assert result["facts"][-1] == {"id": "ADR-001", "kind": "decision", "text": "معماری ثبت‌شده"}
    assert service.history("ADR-001")[0]["source"]["kind"] == "owner_accepted_proposal"


def test_forged_owner_labels_in_model_json_cannot_authorize_change(tmp_path):
    book, service = setup(tmp_path)
    proposal = Requirements(book).propose_requirement("unsafe", source_ref="call:1", fact_id="REQ-101")
    real = service.record_owner_statement("specific approval", expected_version=1, approves=proposal)
    with book.connection() as con:
        payload = json.loads(con.execute("SELECT proposal FROM changes WHERE id=?", (real,)).fetchone()[0])
    fake = book.suggest_change({**payload, "actor": "owner", "approved": True})
    before = book.current()
    with pytest.raises(Refused):
        service.accept_proposal(proposal, fake, expected_version=1)
    assert book.current() == before


def test_owner_statement_cannot_be_replayed_for_other_target_or_modified_proposal(tmp_path):
    book, service = setup(tmp_path)
    first = Requirements(book).propose_requirement("first", source_ref="call:1")
    second = Requirements(book).propose_requirement("second", source_ref="call:1")
    statement = service.record_owner_statement("approve first only", expected_version=1, approves=first)
    with pytest.raises(Refused):
        service.accept_proposal(second, statement, expected_version=1)
    with book.connection() as con:
        data = json.loads(con.execute("SELECT proposal FROM changes WHERE id=?", (first,)).fetchone()[0])
        data["text"] = "changed after owner statement"
        con.execute("UPDATE changes SET proposal=? WHERE id=?", (encoded(data).decode(), first))
    with pytest.raises(Refused):
        service.accept_proposal(first, statement, expected_version=1)
    assert book.current()["version"] == 1


def test_direct_owner_goal_change_is_bound_to_the_exact_change(tmp_path):
    book, service = setup(tmp_path)
    change = {"goal": "هدف اصلاح‌شده"}
    statement = service.record_owner_statement("هدف را مطابق این تغییر اصلاح کن", expected_version=1, change=change)
    with pytest.raises(Refused):
        service.apply_owner_change(statement, expected_version=1, goal="هدف دیگر")
    result = service.apply_owner_change(statement, expected_version=1, goal=change["goal"])
    assert result["goal"] == change["goal"] and result["version"] == 2
    with pytest.raises(Refused):
        service.apply_owner_change(statement, expected_version=2, goal=change["goal"])
    with book.connection() as con:
        assert json.loads(con.execute("SELECT body FROM revisions WHERE version=1").fetchone()[0])["goal"] == "هدف اولیه"


def test_stale_proposal_and_owner_revision_refuse_without_partial_changes(tmp_path):
    book, service = setup(tmp_path)
    proposal = Requirements(book).propose_requirement("stale", source_ref="call:1", fact_id="REQ-101")
    statement = service.record_owner_statement("approve", expected_version=1, approves=proposal)
    book.amend(replace_facts={"REQ-101": "explicit newer owner fact"}, reason="new owner input")
    before = book.current()
    for version in (1, 2, True):
        with pytest.raises(Refused):
            service.accept_proposal(proposal, statement, expected_version=version)
    assert book.current() == before


def test_concurrent_acceptance_consumes_one_statement_and_one_revision(tmp_path):
    book, service = setup(tmp_path)
    proposal = Requirements(book).propose_requirement("accepted once", source_ref="call:1", fact_id="REQ-101")
    statement = service.record_owner_statement("approve once", expected_version=1, approves=proposal)
    def apply(_):
        try:
            return ProjectService(ProjectBook(book.root)).accept_proposal(proposal, statement, expected_version=1)
        except Refused:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(apply, range(2)))
    assert sum(r is not None for r in results) == 1
    assert book.current()["version"] == 2


def test_all_owner_changes_record_impacts_and_revoke_outstanding_shared_gate_pass(tmp_path):
    fixtures = migration_fixtures()
    from csef_gate.core import Gate
    from csef_gate.persistence.migrations import migrate
    book, gate, run = fixtures.setup_pair(tmp_path)
    target = tmp_path / "merged"
    migrate(book.root, gate.root, target, offline=True)
    book, gate = ProjectBook(target), Gate(target)
    gate.evaluate(run, fixtures.UnitExecutor())
    book.amend(replace_facts={"REQ-101": "explicit amendment"}, reason="owner message")
    with pytest.raises(Refused):
        gate.accept(run)
    assert book.status()["stages"][0]["status"] == "stale"
    with book.connection() as con:
        audit = json.loads(con.execute("SELECT proposal FROM changes WHERE status='recorded' ORDER BY id DESC LIMIT 1").fetchone()[0])
    assert audit["source"]["kind"] == "owner_controller"
    assert "discovery" in audit["stale_stages"]


@pytest.mark.parametrize("same_body", [False, True])
def test_owner_change_during_verification_blocks_an_otherwise_passing_result(tmp_path, same_body):
    from csef_gate.core import Gate
    from csef_gate.persistence.migrations import migrate
    fixtures = migration_fixtures()
    book, gate, run = fixtures.setup_pair(tmp_path)
    target = tmp_path / "merged"
    migrate(book.root, gate.root, target, offline=True)
    book, gate = ProjectBook(target), Gate(target)
    class ChangingOwner(fixtures.UnitExecutor):
        def run(self, **kwargs):
            value = book.current()["facts"][0]["text"] if same_body else "changed while evaluation runs"
            book.amend(replace_facts={"REQ-101": value}, reason="owner changed or reaffirmed scope")
            return super().run(**kwargs)
    result = gate.evaluate(run, ChangingOwner())
    assert result["status"] == "blocked" and result["cases"][0]["passed"] is True
    assert "owner revision" in result["error"]
    with pytest.raises(Refused):
        gate.accept(run)
    fresh = gate.evaluate(run, fixtures.UnitExecutor())
    assert fresh["project_sha256"] == book.current()["sha256"]
    assert fresh["project_version"] == book.current()["version"]
    assert gate.accept(run)["evaluation_id"] == fresh["evaluation_id"]


def test_historical_accepted_checkpoint_keeps_its_original_observation(tmp_path):
    from csef_gate.core import Gate
    from csef_gate.persistence.migrations import migrate
    fixtures = migration_fixtures()
    book, gate, run = fixtures.setup_pair(tmp_path)
    target = tmp_path / "merged"
    migrate(book.root, gate.root, target, offline=True)
    book, gate = ProjectBook(target), Gate(target)
    report = gate.evaluate(run, fixtures.UnitExecutor())
    checkpoint = gate.accept(run)
    book.amend(replace_facts={"REQ-101": "new owner scope after historical acceptance"}, reason="owner amendment")
    with gate.connect() as con:
        assert con.execute("SELECT status FROM runs WHERE id=?", (run,)).fetchone()[0] == "accepted"
        assert con.execute("SELECT status FROM evaluations WHERE id=?", (report["evaluation_id"],)).fetchone()[0] == "pass"
        assert con.execute("SELECT id FROM checkpoints").fetchone()[0] == checkpoint["id"]


@pytest.mark.parametrize("version", [None, True, 1.0, "1"])
def test_owner_paths_never_accept_missing_or_coerced_revision(tmp_path, version):
    book, service = setup(tmp_path)
    proposal = Requirements(book).propose_requirement("draft", source_ref="call:1")
    for action in (
        lambda: service.record_owner_statement("owner", expected_version=version, approves=proposal),
        lambda: service.accept_proposal(proposal, 1, expected_version=version),
        lambda: service.apply_owner_change(1, expected_version=version, goal="different"),
    ):
        with pytest.raises(Refused, match="integer"):
            action()
    assert book.current()["version"] == 1


@pytest.mark.parametrize("target", ["revision", "provenance", "goal_effect", "answer_effect", "source_ref"])
def test_history_refuses_tampered_old_revision_or_unbound_provenance(tmp_path, target):
    book, service = setup(tmp_path)
    proposal = Requirements(book).propose_requirement("new fact", source_ref="call:1", fact_id="REQ-101")
    accept(service, proposal)
    assert service.revision_history()[-1]["provenance"]["source"]["kind"] == "owner_accepted_proposal"
    with book.connection() as con:
        if target == "revision":
            old = json.loads(con.execute("SELECT body FROM revisions WHERE version=1").fetchone()[0])
            old["facts"][0]["text"] = "forged historical statement"
            con.execute("UPDATE revisions SET body=? WHERE version=1", (encoded(old).decode(),))
        else:
            row = con.execute("SELECT id,proposal FROM changes WHERE status='recorded'").fetchone()
            data = json.loads(row["proposal"])
            if target == "provenance":
                data["before_sha256"] = "0" * 64
            elif target == "goal_effect":
                data["goal_changed"] = True
            elif target == "answer_effect":
                data["answer_changes"] = {"success": {"before": "old", "after": "invented"}}
            else:
                data["source"]["ref"] = 99999
            con.execute("UPDATE changes SET proposal=? WHERE id=?", (encoded(data).decode(), row["id"]))
    with pytest.raises(Refused):
        service.history("REQ-101")
