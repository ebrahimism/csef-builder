"""Control-plane regressions. Fake execution is never a production backend."""
import json
from pathlib import Path

import pytest

from csef_gate.core import Gate, Refused, encoded, relative_name, same_json
from csef_gate.backends import capture, environment


def setup_gate(tmp_path, cases=None):
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("print(1)\n")
    spec = {"version": 1, "objective": "print one", "source_files": ["app.py"], "editable_files": ["app.py"], "entrypoint": "app.py", "max_attempts": 2, "agent_timeout_s": 10, "case_timeout_s": 1,
            "cases": cases if cases is not None else [{"id": "ONE", "args": [], "exit_code": 0, "stdout_json": 1}]}
    spec_path = tmp_path / "acceptance.json"
    spec_path.write_bytes(encoded(spec))
    gate = Gate.initialize(tmp_path / "control", project, spec_path)
    return gate, gate.prepare()


class FakeExecutor:
    def __init__(self, stdout="1", verified=True, exit_code=0):
        self.stdout, self.verified, self.exit_code = stdout, verified, exit_code
        self.calls = 0

    def probe(self, **kwargs):
        return {"verified": self.verified, "backend": "UNIT_TEST_FAKE"}

    def run(self, **kwargs):
        self.calls += 1
        return {"exit_code": self.exit_code, "stdout": self.stdout, "stderr": "", "timed_out": False, "overflow": False}


def test_acceptance_requires_trusted_execution_not_a_caller_pass(tmp_path):
    gate, run = setup_gate(tmp_path)
    (gate.candidate(run).parent / "forged-report.json").write_text('{"status":"pass"}')
    with pytest.raises(Refused, match="no completed"):
        gate.accept(run)
    gate.evaluate(run, FakeExecutor())
    checkpoint = gate.accept(run)
    assert checkpoint["evaluation_id"] and Path(checkpoint["snapshot"]).is_dir()
    with pytest.raises(Refused):
        gate.accept(run)


@pytest.mark.parametrize("target", ["candidate", "snapshot", "report", "spec"])
def test_verified_bytes_cannot_change_before_acceptance(tmp_path, target):
    gate, run = setup_gate(tmp_path)
    report = gate.evaluate(run, FakeExecutor())
    with gate.connect() as con:
        row = con.execute("SELECT * FROM evaluations WHERE id=?", (report["evaluation_id"],)).fetchone()
    path = {"candidate": gate.candidate(run) / "app.py", "snapshot": Path(row["snapshot"]) / "app.py", "report": Path(row["report"]), "spec": gate.root / "spec.json"}[target]
    path.write_text("tampered")
    with pytest.raises(Refused):
        gate.accept(run)


def test_denied_boundary_stops_before_candidate_execution(tmp_path):
    gate, run = setup_gate(tmp_path)
    backend = FakeExecutor(verified=False)
    report = gate.evaluate(run, backend)
    assert report["status"] == "blocked" and backend.calls == 0
    with pytest.raises(Refused):
        gate.accept(run)


def test_measurement_cannot_authorize_acceptance_even_with_all_tests_passing(tmp_path):
    gate, run = setup_gate(tmp_path)
    class LocalPilot(FakeExecutor):
        def probe(self, **kwargs):
            return {"verified": False, "file_boundary_verified": True, "network_isolation_verified": False}
    report = gate.evaluate(run, LocalPilot(), measure_only=True)
    assert report["status"] == "review" and report["cases"][0]["passed"]
    with pytest.raises(Refused):
        gate.accept(run)


def test_interrupted_evaluation_leaves_no_reusable_authority(tmp_path):
    gate, run = setup_gate(tmp_path)
    class Interrupted(FakeExecutor):
        def run(self, **kwargs):
            raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        gate.evaluate(run, Interrupted())
    with pytest.raises(Refused):
        Gate(gate.root).accept(run)
    assert Gate(gate.root).evaluate(run, FakeExecutor())["status"] == "pass"


def test_duplicate_json_keys_cannot_hide_an_incorrect_value(tmp_path):
    gate, run = setup_gate(tmp_path, cases=[{"id": "ONE", "args": [], "exit_code": 0, "stdout_json": {"id": 1}}])
    assert gate.evaluate(run, FakeExecutor(stdout='{"id":999,"id":1}'))["status"] == "fail"


@pytest.mark.parametrize("stdout,exit_code", [("true", 0), ('"1"', 0), ("PASS", 0), ("1", 1), ("NaN", 0)])
def test_output_is_strictly_evaluated_by_parent(tmp_path, stdout, exit_code):
    gate, run = setup_gate(tmp_path)
    assert gate.evaluate(run, FakeExecutor(stdout=stdout, exit_code=exit_code))["status"] == "fail"
    with pytest.raises(Refused):
        gate.accept(run)


def test_empty_suite_cannot_certify(tmp_path):
    with pytest.raises(Refused, match="nonempty"):
        setup_gate(tmp_path, cases=[])


def test_unsupported_criterion_is_refused_instead_of_skipped(tmp_path):
    with pytest.raises(Refused, match="unsupported acceptance"):
        setup_gate(tmp_path, cases=[{"id": "MANUAL", "type": "review"}])


@pytest.mark.parametrize("name", ["../gate.sqlite3", "/abs.py", "C:/x.py", "app.py:stream", "a\\b.py", "x/../app.py", "./app.py", "NUL.py", ".codex/config.toml", "app.py.", "A//b.py"])
def test_portable_path_rejects_escape_alias_and_control_paths(name):
    with pytest.raises(Refused):
        relative_name(name)


def test_proposal_is_validated_before_any_write_and_invalidates_old_pass(tmp_path):
    gate, run = setup_gate(tmp_path)
    gate.evaluate(run, FakeExecutor())
    before = (gate.candidate(run) / "app.py").read_bytes()
    with pytest.raises(Refused):
        gate.apply_proposal(run, {"summary": "bad", "files": [{"path": "app.py", "content": "changed"}, {"path": "../spec.json", "content": "{}"}]})
    assert (gate.candidate(run) / "app.py").read_bytes() == before
    gate.apply_proposal(run, {"summary": "fix", "files": [{"path": "app.py", "content": "print(2)\n"}]})
    with pytest.raises(Refused):
        gate.accept(run)


def test_resume_uses_persistent_attempt_budget_and_does_not_retry_unknown_call(tmp_path):
    gate, run = setup_gate(tmp_path)
    class BrokenAgent:
        def propose(self, **kwargs):
            raise Refused("provider interrupted")
    for _ in range(2):
        with pytest.raises(Refused, match="provider interrupted"):
            Gate(gate.root).agent_attempt(run, BrokenAgent())
    with pytest.raises(Refused, match="budget exhausted"):
        Gate(gate.root).agent_attempt(run, BrokenAgent())
    with gate.connect() as con:
        assert con.execute("SELECT attempts FROM runs WHERE id=?", (run,)).fetchone()[0] == 2


def test_existing_agent_loop_changes_source_then_independent_gate_accepts(tmp_path):
    gate, run = setup_gate(tmp_path)
    class ContentExecutor(FakeExecutor):
        def run(self, *, snapshot, **kwargs):
            return {"exit_code": 0, "stdout": "1" if (snapshot / "app.py").read_text() == "print(2)\n" else "0", "stderr": ""}
    class Agent:
        def propose(self, **kwargs):
            assert kwargs["feedback"][0]["id"] == "ONE"
            return {"summary": "repair", "files": [{"path": "app.py", "content": "print(2)\n"}]}, {"adapter": "UNIT_TEST_FAKE"}
    result = gate.run(ContentExecutor(), Agent(), run)
    assert result["status"] == "accepted"
    assert (tmp_path / "project" / "app.py").read_text() == "print(1)\n"
    assert same_json(result["report"]["cases"][0]["actual_json"], 1)


def test_environment_does_not_leak_provider_or_application_credentials(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sentinel")
    monkeypatch.setenv("DJANGO_SECRET_KEY", "sentinel")
    monkeypatch.setenv("PYTHONPATH", "injected")
    assert not {"OPENAI_API_KEY", "DJANGO_SECRET_KEY", "PYTHONPATH"} & environment().keys()


def test_command_deadline_and_output_limit_are_fail_closed():
    import sys
    deadline = capture([sys.executable, "-I", "-S", "-c", "import time;time.sleep(10)"], cwd=Path.cwd(), timeout=0.2, env=environment())
    assert deadline["timed_out"] and deadline["exit_code"] != 0
    bounded = capture([sys.executable, "-I", "-S", "-c", "print('x'*50000)"], cwd=Path.cwd(), timeout=5, env=environment(), limit=1000)
    assert bounded["overflow"] and len(bounded["stdout"].encode()) <= 1000
