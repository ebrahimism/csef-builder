"""Question identity, answer provenance, edits and provider-call suppression."""
from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from csef_gate.core import Refused, encoded
from csef_gate.project import ProjectBook
from csef_gate.assistant import assist_stage
from csef_gate.lifecycle.questions import Questions


ANSWERS = {"users": "owner", "workflow": "input/result", "success": "preserve", "constraints": "offline"}
FACTS = [{"id": "REQ-101", "kind": "requirement", "text": "Keep prior data"},
         {"id": "ADR-001", "kind": "decision", "text": "Use a local database"}]


def setup(tmp_path):
    book = ProjectBook.create(tmp_path / "book", "Preserve data", ANSWERS, FACTS)
    return book, Questions(book)


def ask(service, *, version=1, question="How long must data be kept?", **kwargs):
    return service.ask(question, why_needed="retention affects storage", decision_affected="data lifecycle",
                       stage="discovery", source_ref="interview:1", expected_version=version,
                       fact_ids=["REQ-101"], **kwargs)


def test_answer_edit_preserves_old_values_and_updates_only_linked_requirement(tmp_path):
    book, service = setup(tmp_path)
    q = ask(service)["id"]
    assert book.questions()[0]["fact_ids"] == ["REQ-101"]
    service.answer(q, "30 days", expected_version=1, fact_updates={"REQ-101": "Keep data for 30 days"})
    Questions(ProjectBook(book.root)).answer(q, "90 days", expected_version=2, fact_updates={"REQ-101": "Keep data for 90 days"})
    history = service.answer_history(q)
    assert [r["value"]["answer"] for r in history] == ["30 days", "90 days"]
    assert [r["status"] for r in history] == ["superseded", "accepted"]
    assert all(r["fact_ids"] == ["REQ-101"] and r["source"]["kind"] == "owner_statement" for r in history)
    assert book.current()["facts"][0]["text"] == "Keep data for 90 days"
    assert book.current()["facts"][1] == FACTS[1]
    assert not book.questions()
    assert service.history("REQ-101")[-1]["fact"]["text"] == "Keep data for 90 days"


def test_answered_question_reused_with_same_context_and_refreshed_for_changed_requirement(tmp_path):
    book, service = setup(tmp_path)
    first = ask(service)
    service.answer(first["id"], "30 days", expected_version=1, fact_updates={"REQ-101": "Keep data for 30 days"})
    reused = ask(service, version=2, question="  HOW   LONG must data be kept? ")
    assert reused["id"] == first["id"] and reused["status"] == "answered"
    assert reused["reused"] is True and not book.questions()
    # An unrelated decision change does not make the known answer unknown.
    book.amend(replace_facts={"ADR-001": "Use another local engine"}, reason="owner revised architecture")
    assert ask(service, version=3)["id"] == first["id"]
    book.amend(replace_facts={"REQ-101": "Retention now depends on a new regulator"}, reason="owner revised requirement")
    fresh = ask(service, version=4)
    assert fresh["id"] != first["id"] and fresh["reused"] is False
    assert book.questions()[0]["id"] == fresh["id"]


def test_pending_question_stops_repeated_provider_calls_and_known_repeat_is_not_pending(tmp_path):
    book, service = setup(tmp_path)
    class Client:
        count = 0
        def call(self, **kwargs):
            self.count += 1
            return {"summary": "retention question", "questions": [{"question": "How long must data be kept?", "why_needed": "storage", "decision_affected": "retention", "fact_ids": ["REQ-101"]}],
                    "proposed_decisions": [], "drafts": [], "issues": []}, {"exit_code": 0}
    client = Client()
    result = assist_stage(book, "discovery", client)
    assert result["status"] == "awaiting_owner"
    for _ in range(3):
        assert assist_stage(ProjectBook(book.root), "discovery", client)["model_called"] is False
    assert client.count == 1
    qid = result["questions"][0]["id"]
    service.answer(qid, "30 days", expected_version=1)
    repeated = assist_stage(ProjectBook(book.root), "discovery", client)
    assert client.count == 2
    assert repeated["status"] == "draft_requires_validation" and repeated["questions"] == []
    assert len(service.answer_history(qid)) == 1


def test_concurrent_asks_create_one_pending_question(tmp_path):
    book, _ = setup(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(lambda _: ask(Questions(ProjectBook(book.root))), range(2)))
    assert result[0]["id"] == result[1]["id"]
    assert sum(not r["reused"] for r in result) == 1
    assert len(book.questions()) == 1


def test_intake_answers_can_be_edited_with_history_and_no_repeat(tmp_path):
    book, service = setup(tmp_path)
    service.answer("constraints", "offline and no cloud storage", expected_version=1)
    service.answer("constraints", "offline and encrypted local storage", expected_version=2)
    history = service.answer_history("constraints")
    assert [r["value"] for r in history] == ["offline", "offline and no cloud storage", "offline and encrypted local storage"]
    assert history[0]["source"]["kind"] == "legacy_unattributed"
    assert history[-1]["source"]["kind"] == "owner_statement"
    assert not book.questions()


def test_answer_does_not_infer_fact_changes_and_refuses_unrelated_fact_edits(tmp_path):
    book, service = setup(tmp_path)
    q = ask(service)["id"]
    with pytest.raises(Refused, match="linked"):
        service.answer(q, "update", expected_version=1, fact_updates={"ADR-001": "unrelated change"})
    assert book.current()["version"] == 1
    service.answer(q, "30 days", expected_version=1)
    assert book.current()["facts"] == FACTS
    assert service.answer_history(q)[-1]["fact_ids"] == ["REQ-101"]


@pytest.mark.parametrize("failure", ["unknown_fact", "stale_version", "ambiguous_key"])
def test_invalid_question_scope_or_stale_input_is_refused(tmp_path, failure):
    book, service = setup(tmp_path)
    if failure == "unknown_fact":
        with pytest.raises(Refused, match="unknown"):
            service.ask("Question?", why_needed="why", decision_affected="storage", stage="discovery", source_ref="call:1", expected_version=1, fact_ids=["REQ-999"])
    elif failure == "stale_version":
        q = ask(service)["id"]
        book.amend(answers={"success": "new explicit success criterion"}, reason="owner edit")
        with pytest.raises(Refused, match="stale"):
            service.answer(q, "answer", expected_version=1)
        assert book.current()["version"] == 2
    else:
        ask(service, key="retention")
        with pytest.raises(Refused, match="different"):
            ask(service, key="retention", question="Should all data be deleted?")


@pytest.mark.parametrize("field,value", [("value", "forged"), ("project_version", 2.0), ("context_sha256", "0" * 64)])
def test_answer_history_refuses_tampered_observation(tmp_path, field, value):
    book, service = setup(tmp_path)
    q = ask(service)["id"]
    service.answer(q, "30 days", expected_version=1)
    with book.connection() as con:
        for row in con.execute("SELECT id,proposal FROM changes WHERE status='recorded'").fetchall():
            data = json.loads(row["proposal"])
            if data.get("type") == "answer_revision":
                data[field] = value
                con.execute("UPDATE changes SET proposal=? WHERE id=?", (encoded(data).decode(), row["id"]))
    with pytest.raises(Refused, match="history"):
        service.answer_history(q)


@pytest.mark.parametrize("drift", ["requirement", "goal"])
def test_pending_question_context_drift_does_not_block_or_accept_stale_answer(tmp_path, drift):
    book, service = setup(tmp_path)
    old = ask(service)["id"]
    if drift == "requirement":
        book.amend(replace_facts={"REQ-101": "New retention requirement"}, reason="owner revised requirement")
    else:
        statement = service.record_owner_statement("new goal", expected_version=1, change={"goal": "Retain only explicit consent data"})
        service.apply_owner_change(statement, expected_version=1, goal="Retain only explicit consent data")
    assert not book.questions()
    for answer in (lambda: service.answer(old, "stale answer", expected_version=2),
                   lambda: book.amend(answers={old: "stale answer"}, reason="old prompt response")):
        with pytest.raises(Refused, match="context is stale"):
            answer()
    assert book.current()["version"] == 2 and old not in book.current()["answers"]
    fresh = ask(service, version=2)["id"]
    assert fresh != old and [q["id"] for q in book.questions()] == [fresh]
    service.answer(fresh, "new context answer", expected_version=2)
    assert not book.questions() and service.answer_history(old) == []


def test_changed_goal_invalidates_answer_anchor_even_with_same_facts(tmp_path):
    book, service = setup(tmp_path)
    old = ask(service)["id"]
    service.answer(old, "30 days", expected_version=1)
    statement = service.record_owner_statement("new goal", expected_version=2, change={"goal": "Keep only anonymized data"})
    service.apply_owner_change(statement, expected_version=2, goal="Keep only anonymized data")
    assert ask(service, version=3)["id"] != old
    with pytest.raises(Refused, match="context is stale"):
        service.answer(old, "90 days", expected_version=3)


def test_duplicate_answer_observation_is_refused(tmp_path):
    book, service = setup(tmp_path)
    q = ask(service)["id"]
    service.answer(q, "30 days", expected_version=1)
    with book.connection() as con:
        rows = con.execute("SELECT proposal,created FROM changes WHERE status='recorded'").fetchall()
        row = next(r for r in rows if json.loads(r["proposal"]).get("type") == "answer_revision")
        con.execute("INSERT INTO changes(proposal,status,created) VALUES(?,'recorded',?)", tuple(row))
    with pytest.raises(Refused, match="history"):
        service.answer_history(q)


def test_structured_known_intake_answer_is_not_repeated(tmp_path):
    book = ProjectBook.create(tmp_path / "book", "Preserve data",
                              {**ANSWERS, "users": {"question": "Who?", "answer": "owner"}}, FACTS)
    assert not book.questions()


def test_answer_history_uses_one_snapshot_during_concurrent_owner_update(tmp_path, monkeypatch):
    book, service = setup(tmp_path)
    q = ask(service)["id"]
    service.answer(q, "30 days", expected_version=1)
    # WAL lets the real writer commit while this history reader retains its
    # earlier snapshot. Production also supports the default rollback journal.
    with book.connection() as con:
        con.execute("PRAGMA journal_mode=WAL")
    original = service._timeline
    def race(*, con=None):
        result = original(con=con)
        Questions(ProjectBook(book.root)).answer(q, "90 days", expected_version=2)
        return result
    monkeypatch.setattr(service, "_timeline", race)
    assert [r["value"]["answer"] for r in service.answer_history(q)] == ["30 days"]
    monkeypatch.setattr(service, "_timeline", original)
    assert [r["value"]["answer"] for r in service.answer_history(q)] == ["30 days", "90 days"]


def test_intake_context_changes_but_unrelated_question_answer_does_not(tmp_path):
    book, service = setup(tmp_path)
    q = ask(service)["id"]
    other = ask(service, question="Must retention support export?")["id"]
    service.answer(other, "yes", expected_version=1)
    assert [item["id"] for item in book.questions()] == [q]
    service.answer("constraints", "online storage permitted", expected_version=2)
    assert not book.questions()
    assert ask(service, version=3)["id"] not in (q, other)


def test_intake_string_and_answer_representation_have_same_context(tmp_path):
    from csef_gate.lifecycle.questions import context_sha
    project = {"goal": "goal", "facts": FACTS, "answers": ANSWERS}
    structured = {**project, "answers": {**ANSWERS, "constraints": {"question": "Limits?", "answer": "offline"}}}
    assert context_sha(project, ["REQ-101"]) == context_sha(structured, ["REQ-101"])


def test_cli_edits_linked_answer_and_refuses_stale_version(tmp_path, capsys):
    from csef_gate.__main__ import main
    book, service = setup(tmp_path)
    q = ask(service)["id"]
    args = ["project", "answer", "--root", str(book.root), "--id", q]
    assert main([*args, "--text", "30 days", "--version", "1", "--fact", "REQ-101", "Keep data for 30 days"]) == 0
    assert json.loads(capsys.readouterr().out)["project"]["facts"][0]["text"] == "Keep data for 30 days"
    assert main([*args, "--text", "stale answer", "--version", "1"]) == 2
    assert "stale" in capsys.readouterr().err
    assert main([*args, "--text", "90 days", "--version", "2", "--fact", "REQ-101", "Keep data for 90 days"]) == 0
    capsys.readouterr()
    assert [r["value"]["answer"] for r in service.answer_history(q)] == ["30 days", "90 days"]
