import pytest
from csef_gate.core import Refused, digest, encoded
from csef_gate.project import ProjectBook, STAGES


ANSWERS = {"users": "owner", "workflow": "input to result", "success": "preserve data", "constraints": "offline and low cost"}
FACTS = [{"id": "REQ-001", "kind": "requirement", "text": "Never delete existing data"}]


def book(tmp_path):
    return ProjectBook.create(tmp_path / "project", "Useful offline app", ANSWERS, FACTS)


def finish(project, stage, passed=True):
    packet = project.begin(stage)
    return project.finish(stage, packet_hash=digest(encoded(packet)), artifacts={"handoff.md": stage.encode()}, checks=[{"id": "observed", "passed": passed, "basis": "controller observation"}])


def test_questions_are_bounded_and_only_unknowns_are_asked(tmp_path):
    project = ProjectBook.create(tmp_path / "project", "my goal")
    assert len(project.questions()) == 3
    with pytest.raises(Refused, match="answers"):
        project.begin("discovery")
    project.amend(answers=ANSWERS, reason="owner supplied answers")
    assert project.questions() == []


def test_stage_waits_for_current_predecessor_and_failed_handoff_blocks(tmp_path):
    project = book(tmp_path)
    with pytest.raises(Refused, match="previous"):
        project.begin("architecture")
    finish(project, "discovery", passed=False)
    with pytest.raises(Refused, match="previous"):
        project.begin("architecture")
    finish(project, "discovery")
    assert project.begin("architecture")["handoffs"][0]["stage"] == "discovery"


def test_model_suggestion_cannot_change_owner_goal_or_decision(tmp_path):
    project = book(tmp_path)
    before = project.current()
    project.suggest_change({"replace": "REQ-001", "text": "Delete all data"})
    assert project.current() == before
    assert project.status()["pending_changes"] == 1


def test_owner_change_invalidates_old_handoffs_and_stale_reply(tmp_path):
    project = book(tmp_path)
    finish(project, "discovery")
    packet = project.begin("architecture")
    project.amend(replace_facts={"REQ-001": "Preserve data and encrypt backup"}, reason="owner changed requirements")
    with pytest.raises(Refused):
        project.finish("architecture", packet_hash=digest(encoded(packet)), artifacts={"design.md": b"old"}, checks=[{"id": "x", "passed": True, "basis": "old revision"}])
    with pytest.raises(Refused):
        project.begin("contracts")
    assert project.current()["version"] == 2


def test_changed_document_is_detected_before_next_model_receives_it(tmp_path):
    project = book(tmp_path)
    handoff = finish(project, "discovery")
    (project.root / handoff["artifacts"][0]["path"]).write_bytes(b"changed")
    with pytest.raises(Refused, match="artifact changed"):
        project.packet("architecture")


def test_six_handoffs_survive_restart_without_claiming_release(tmp_path):
    project = book(tmp_path)
    for name, _, _ in STAGES:
        project = ProjectBook(project.root)
        finish(project, name)
    state = project.status()
    assert all(s["status"] == "ready_for_next" for s in state["stages"])
    assert state["project"]["facts"] == FACTS
    assert state["release_approved"] is False


def test_unknown_model_call_consumes_persistent_budget(tmp_path):
    project = book(tmp_path)
    with project.connection() as con:
        con.execute("UPDATE settings SET max_calls=1")
    project.reserve_call("reviewer")
    with pytest.raises(Refused, match="budget"):
        ProjectBook(project.root).reserve_call("coder")


def test_review_finding_blocks_handoff_even_if_mechanical_checks_pass(tmp_path):
    project = book(tmp_path)
    packet = project.begin("discovery")
    project.finish("discovery", packet_hash=digest(encoded(packet)), artifacts={"brief.md": b"draft"}, checks=[{"id": "schema", "passed": True, "basis": "valid"}], reviewer={"verdict": "needs_revision", "findings": ["goal contradicted"]})
    with pytest.raises(Refused, match="previous"):
        project.begin("architecture")


def test_pipeline_can_have_seven_roles_without_losing_dependencies(tmp_path):
    stages = [*STAGES, ("operations", "عملیات و تکامل", "operator")]
    project = ProjectBook.create(tmp_path / "project", "goal", ANSWERS, FACTS, stages=stages)
    for name, _, _ in stages:
        finish(project, name)
    assert len(project.status()["stages"]) == 7
    assert project.packet("operations")["role"] == "operator"


def test_portable_context_keeps_goal_and_only_latest_code(tmp_path):
    project = book(tmp_path)
    for stage, text in (("discovery", b"old source"), ("architecture", b"new source")):
        packet = project.begin(stage)
        project.finish(stage, packet_hash=digest(encoded(packet)), artifacts={"app.py": text, "handoff.md": stage.encode()}, checks=[{"id": "checked", "passed": True, "basis": "fixture"}])
    context = project.context("contracts")
    code = [d for d in context["documents"] if d["logical_file"] == "app.py"]
    assert len(code) == 1 and code[0]["content"] == "new source"
    assert context["project"]["facts"] == FACTS
    assert len(context["artifact_index"]) == 4 and len(context["documents"]) == 3


def test_context_budget_never_silently_drops_owner_facts(tmp_path):
    project = ProjectBook.create(tmp_path / "project", "goal", ANSWERS, [{"id": "REQ-001", "kind": "requirement", "text": "x" * 4000}])
    with pytest.raises(Refused, match="owner facts"):
        project.context("discovery", max_bytes=2000)


def test_review_routing_keeps_checks_and_calls_model_at_explicit_risks():
    from csef_gate.review import route_review
    assert not route_review("vertical")["call_model"]
    assert route_review("vertical")["mechanical_checks_required"]
    assert route_review("evolution", ["data_migration"])["call_model"]
    assert route_review("architecture")["call_model"]
    assert route_review("vertical", always=True)["call_model"]
    with pytest.raises(Refused):
        route_review("delivery", ["misspelled_risk"])


def test_second_session_review_never_changes_owner_facts_or_approves_release(tmp_path):
    from csef_gate.review import review_proposal
    project = book(tmp_path)
    before = project.current()
    class Client:
        def call(self, **kwargs):
            assert "REQ-001" in kwargs["prompt"]
            return {"verdict": "needs_owner", "findings": [{"fact_id": "REQ-001", "evidence": "proposal deletes data", "reason": "conflict", "suggested_check": "preserve old rows"}], "owner_questions": []}, {"exit_code": 0, "usage": []}
    result = review_proposal(project, "discovery", {"delete": "all"}, Client())
    assert result["release_approved"] is False and result["review"]["verdict"] == "needs_owner"
    assert project.current() == before
    assert project.status()["calls"][0]["status"] == "completed"


def test_adaptive_question_blocks_next_call_until_owner_answers(tmp_path):
    from csef_gate.assistant import assist_stage
    project = book(tmp_path)
    class Client:
        count = 0
        def call(self, **kwargs):
            self.count += 1
            return {"summary": "need clarification", "questions": [{"question": "Must two offline sites sync instantly?", "why_needed": "requirements conflict", "decision_affected": "data architecture"}], "proposed_decisions": [], "drafts": [], "issues": ["offline/instant-sync contradiction"]}, {"exit_code": 0}
    client = Client()
    result = assist_stage(project, "discovery", client)
    assert result["status"] == "awaiting_owner"
    assert assist_stage(project, "discovery", client)["model_called"] is False
    assert client.count == 1
    qid = result["questions"][0]["id"]
    project.amend(answers={qid: "Sync may wait until connected"}, reason="owner clarified")
    assert not project.questions()
    assert project.current()["answers"][qid]["answer"] == "Sync may wait until connected"
    assert project.current()["facts"] == FACTS
