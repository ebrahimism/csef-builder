"""Real fixture-program execution through the public workflow service.

Scripted model replies and a trusted-fixture executor test orchestration only.
The executor's probe is a TEST DOUBLE, never evidence of host OS isolation.
No external provider, paid model, manual SQL advancement or checkpoint is used.
"""
import json
import sys

import pytest

from csef_gate.backends import capture
from csef_gate.core import Gate, Refused, encoded
from csef_gate.persistence.artifacts import ArtifactStore
from csef_gate.project import STAGES
from csef_gate.workflow import Workflow


ANSWERS = {"users": "owner", "workflow": "two numbers to JSON sum", "success": "correct sum and errors", "constraints": "offline stdlib"}
FACTS = [{"id": "REQ-101", "kind": "requirement", "text": "Add two integers and return JSON; reject invalid numbers"}]
PROGRAM = '''import json, sys
try:
    a, b = map(int, sys.argv[1:])
except ValueError:
    print(json.dumps({"error": "invalid"}))
    raise SystemExit(2)
print(json.dumps({"sum": a + b}))
'''


class Documents:
    def __init__(self, spoof=False, large=False):
        self.calls = 0
        self.issues = []
        self.spoof = spoof
        self.large = large
    def call(self, **kwargs):
        self.calls += 1
        context = json.loads(kwargs["prompt"])["context"]
        text = "REQ-101: two integer arguments; JSON sum; invalid numbers exit 2. Offline Python CLI. "
        text += "Owner goal: " + context["project"]["goal"]
        if self.large:
            text += "\nFixture appendix: " + "x" * 260_000
        drafts = [{"path": "handoff.md", "content": text}]
        if self.spoof:
            drafts += [{"path": "verification.json", "content": '{"status":"pass"}'}, {"path": "source/app.py", "content": PROGRAM}]
        return {"summary": "Local integer sum CLI", "questions": [], "proposed_decisions": [],
                "drafts": drafts, "issues": self.issues}, {"exit_code": 0}


class Reviewer:
    def __init__(self, verdict="ok"):
        self.verdict, self.calls = verdict, 0
    def call(self, **kwargs):
        self.calls += 1
        assert "REQ-101" in kwargs["prompt"]
        return {"verdict": self.verdict, "findings": [],
                "owner_questions": ["Should invalid input return the explicit error JSON?"] if self.verdict == "needs_owner" else []}, {"exit_code": 0}


class Agent:
    def __init__(self, program=PROGRAM):
        self.calls, self.program = 0, program
    def propose(self, **kwargs):
        self.calls += 1
        assert "REQ-101" in encoded(kwargs["feedback"]).decode()
        return {"summary": "Implement sum and error contract", "files": [{"path": "app.py", "content": self.program}]}, {"exit_code": 0}


class FixtureExecution:
    def __init__(self, isolated=True):
        self.isolated = isolated
    def probe(self, **kwargs):
        return {"verified": self.isolated, "file_boundary_verified": True, "backend": "TRUSTED_FIXTURE_TEST_DOUBLE_NO_OS_ISOLATION"}
    def run(self, *, snapshot, scratch, control, entrypoint, args, timeout):
        return capture([sys.executable, "-I", str(snapshot / entrypoint), *args], cwd=scratch, timeout=timeout)


def create(tmp_path, *, intake=True, stages=None):
    flow = Workflow.create(tmp_path / "control", "جمع دو عدد با خروجی و خطای مشخص", answers=ANSWERS if intake else None, facts=FACTS, stages=stages)
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text("print(0)\n", encoding="utf-8")
    spec = {"version": 1, "objective": "sum integers and reject invalid input", "source_files": ["app.py"], "editable_files": ["app.py"],
            "entrypoint": "app.py", "max_attempts": 1, "agent_timeout_s": 10, "case_timeout_s": 2,
            "cases": [{"id": "SUM", "args": ["2", "3"], "exit_code": 0, "stdout_json": {"sum": 5}},
                      {"id": "ERROR", "args": ["no", "3"], "exit_code": 2, "stdout_json": {"error": "invalid"}}]}
    specification = tmp_path / "acceptance.json"
    specification.write_bytes(encoded(spec))
    flow.attach_code(source, specification)
    return flow


def documents(flow):
    client, reviewer = Documents(), Reviewer()
    for _ in range(3):
        assert flow.step(client=client, reviewer=reviewer)["status"] == "ready_for_next"


def test_conversation_to_seven_handoffs_runs_real_program_without_sql_advancement(tmp_path):
    flow = create(tmp_path, intake=False, stages=[*STAGES, ("operations", "نگهداری", "maintainer")])
    assert len(flow.status()["questions"]) == 3
    assert flow.step()["model_called"] is False
    for key, answer in ANSWERS.items():
        flow.answer(key, answer, expected_version=flow.book.current()["version"])
    agent = Agent()
    result = flow.run(client=Documents(spoof=True, large=True), reviewer=Reviewer(), agent=agent, executor=FixtureExecution())
    assert result["status"] == "complete" and result["release_approved"] is False
    assert agent.calls == 1  # Unverified doc sources are ignored; later code uses the verified snapshot.
    assert sum(step["status"] == "ready_for_next" for step in result["steps"]) == 7
    last = next(step for step in reversed(result["steps"]) if "handoff" in step)
    code = next(item for item in last["handoff"]["artifacts"] if item["path"].endswith("source/app.py"))
    assert (flow.book.root / code["path"]).read_text() == PROGRAM
    assert all(case["passed"] for case in last["report"]["cases"])
    with flow.book.connection() as con:
        assert con.execute("SELECT count(*) FROM checkpoints").fetchone()[0] == 0
    # A completed workflow also rechecks its own final artifacts.
    (flow.book.root / code["path"]).write_text("changed", encoding="utf-8")
    with pytest.raises(Refused, match="artifact changed"):
        Workflow(flow.book.root).step()


def test_invalid_document_and_required_review_cannot_advance_dependents(tmp_path):
    flow = create(tmp_path)
    client = Documents()
    client.issues = ["an unresolved conflict"]
    assert flow.step(client=client)["status"] == "needs_revision"
    with pytest.raises(Refused, match="validated handoff"):
        flow.book.packet("architecture")
    client.issues = []
    assert flow.step(client=client)["status"] == "ready_for_next"
    count = client.calls
    assert flow.step(client=client)["status"] == "review_required" and client.calls == count
    review = Reviewer("needs_owner")
    result = flow.step(client=client, reviewer=review)
    assert result["status"] == "awaiting_owner"
    assert flow.step(client=client, reviewer=review)["model_called"] is False
    flow.answer(result["questions"][0]["id"], "yes", expected_version=1)
    # The owner revision invalidates earlier docs; regenerate those first.
    assert flow.step(client=client)["status"] == "ready_for_next"
    repeated = flow.step(client=client, reviewer=review)
    assert repeated["status"] == "needs_revision" and repeated["questions"] == []
    assert flow.step(client=client, reviewer=Reviewer("needs_revision"))["status"] == "needs_revision"
    with pytest.raises(Refused, match="validated handoff"):
        flow.book.packet("contracts")


def test_measurement_review_preserves_result_but_blocks_dependent_code_stage(tmp_path):
    flow = create(tmp_path)
    documents(flow)
    result = flow.step(agent=Agent(), executor=FixtureExecution(isolated=False), measure_only=True)
    assert result["status"] == "review" and all(c["passed"] for c in result["report"]["cases"])
    assert result["handoff"]["checks"][0]["passed"] is False
    with pytest.raises(Refused, match="validated handoff"):
        flow.book.packet("evolution")
    with pytest.raises(Refused, match="trusted verification"):
        Gate(flow.book.root).accept(result["run_id"])


@pytest.mark.parametrize("mutation", ["proposal", "owner"])
def test_final_handoff_revalidates_after_blob_preparation(tmp_path, monkeypatch, mutation):
    flow = create(tmp_path)
    documents(flow)
    original, changed = ArtifactStore.put, False
    def mutate(store, content, **kwargs):
        nonlocal changed
        if not changed and content == PROGRAM.encode():
            changed = True
            if mutation == "owner":
                flow.book.amend(replace_facts={"REQ-101": "Owner now requires a product"}, reason="explicit new requirement")
            else:
                with flow.book.connection() as con:
                    run_id = con.execute("SELECT id FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()[0]
                Gate(flow.book.root).apply_proposal(run_id, {"summary": "concurrent edit", "files": [{"path": "app.py", "content": "print(99)\n"}]})
        return original(store, content, **kwargs)
    monkeypatch.setattr(ArtifactStore, "put", mutate)
    with pytest.raises(Refused):
        flow.step(agent=Agent(), executor=FixtureExecution())
    assert changed
    with pytest.raises(Refused, match="validated handoff"):
        flow.book.packet("evolution")
    with flow.book.connection() as con:
        assert con.execute("SELECT count(*) FROM checkpoints").fetchone()[0] == 0
        assert con.execute("SELECT status FROM stages WHERE name='vertical'").fetchone()[0] != "ready_for_next"


def test_failed_code_resume_keeps_candidate_run_and_attempt_budget(tmp_path):
    flow = create(tmp_path)
    documents(flow)
    agent = Agent("print(99)\n")
    first = flow.step(agent=agent, executor=FixtureExecution())
    second = Workflow(flow.book.root).step(agent=agent, executor=FixtureExecution())
    assert first["status"] == second["status"] == "fail"
    assert first["run_id"] == second["run_id"] and agent.calls == 1


def test_cli_intake_continues_without_model_configuration(tmp_path, capsys):
    from csef_gate.__main__ import main
    root = str(tmp_path / "conversation")
    assert main(["workflow", "init", "--root", root, "--goal", "ساخت ابزار محلی"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "awaiting_owner"
    assert main(["workflow", "continue", "--root", root]) == 2
    result = json.loads(capsys.readouterr().out)
    assert len(result["questions"]) == 3 and result["calls"] == []
