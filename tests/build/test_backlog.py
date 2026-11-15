"""Behavioral checks for build bookkeeping; these are not Gate security tests."""
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "plugins/csef-builder/skills/csef-build/scripts/backlog.py"
spec = importlib.util.spec_from_file_location("build_backlog", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def book(tmp_path):
    (tmp_path / "docs/roadmap").mkdir(parents=True)
    (tmp_path / "docs/progress").mkdir()
    (tmp_path / "tests").mkdir()
    tasks = [{"id": key, "title": "baseline", "phase": "F0", "scope": "local work",
              "acceptance": "Preserve data and verify behavior", "goals": ["REQ-1"],
              "depends_on": deps, "status": "planned", "files": [], "tests": []}
             for key, deps in [("T001", []), ("T002", ["T001"]), ("T003", [])]]
    (tmp_path / "docs/roadmap/backlog.json").write_text(json.dumps({"tasks": tasks}))
    (tmp_path / "docs/PROJECT-GOALS.json").write_text(json.dumps({"facts": [{"id": "REQ-1"}]}))
    (tmp_path / "app.py").write_text("value = 1\n")
    value = module.Book(tmp_path)
    yield value
    value.close()


def runner(report='<testsuites><testsuite><testcase name="behavior"/></testsuite></testsuites>',
           code=0, mutate=None, timed_out=False):
    def execute(argv, root, timeout, scratch):
        report_path = Path(next(a.split("=", 1)[1] for a in argv if a.startswith("--junitxml=")))
        report_path.write_text(report)
        if mutate:
            mutate(root)
        return {"exit_code": code, "timed_out": timed_out, "overflow": False,
                "stdout": "measured", "stderr": "", "elapsed_s": 0.01}
    return execute


def review(book, key="T001", independent=False):
    path = book.root / "docs/progress/review.json"
    evidence = book.root / "docs/progress/acceptance.txt"
    evidence.write_text("Observed preservation and correct behavior")
    data = {"task_id": key, "acceptance": book.task(key)["acceptance"],
            "findings": "All stated criteria checked against the evidence.",
            "evidence": ["docs/progress/acceptance.txt"], "risks": [],
            "independent_review": "docs/progress/acceptance.txt" if independent else None}
    path.write_text(json.dumps(data))
    return "docs/progress/review.json"


def test_dependencies_and_single_active(book):
    assert [t["id"] for t in book.ready()] == ["T001", "T003"]
    with pytest.raises(module.Refused, match="dependencies"):
        book.start("T002")
    book.start("T001")
    with pytest.raises(module.Refused, match="already active"):
        book.start("T003")


def test_cannot_complete_by_claim_or_focused_check(book):
    book.start("T001")
    note = review(book)
    with pytest.raises(module.Refused, match="full-suite"):
        book.complete("T001", note)
    (book.root / "tests/unit").mkdir()
    assert book.check("T001", ["tests/unit"], runner=runner())["passed"]
    with pytest.raises(module.Refused, match="full-suite"):
        book.complete("T001", note)


@pytest.mark.parametrize("report,code,timed_out", [
    ("<testsuites/>", 0, False),
    ('<testsuite><testcase><failure/></testcase></testsuite>', 0, False),
    ('<testsuite><testcase><skipped/></testcase></testsuite>', 0, False),
    ('<testsuite><testcase/></testsuite>', 1, False),
    ('<testsuite><testcase/></testsuite>', 0, True),
    ('malformed', 0, False),
])
def test_empty_failed_skipped_or_incomplete_check_is_not_pass(book, report, code, timed_out):
    book.start("T001")
    result = book.check("T001", runner=runner(report, code, timed_out=timed_out))
    assert not result["passed"]
    with pytest.raises(module.Refused, match="full-suite"):
        book.complete("T001", review(book))


def test_source_changed_during_check_is_not_pass(book):
    book.start("T001")
    result = book.check("T001", runner=runner(mutate=lambda root: (root / "app.py").write_text("value=2")))
    assert not result["passed"]


def test_source_changed_after_check_refuses_completion(book):
    book.start("T001")
    assert book.check("T001", runner=runner())["passed"]
    (book.root / "app.py").write_text("value=2")
    with pytest.raises(module.Refused, match="full-suite"):
        book.complete("T001", review(book))


def test_real_receipt_evidence_and_restart(book):
    book.start("T001")
    assert book.check("T001", runner=runner())["passed"]
    assert book.complete("T001", review(book))["status"] == "done"
    other = module.Book(book.root)
    try:
        assert other.state("T001")["status"] == "done"
        assert "T002" in [t["id"] for t in other.ready()]
        event = other.history()[-1]
        assert event["data"]["evidence"]["docs/progress/acceptance.txt"]
        assert event["data"]["authority"].endswith("not release approval")
    finally:
        other.close()


def test_resume_invalidates_old_checks(book):
    book.start("T001")
    book.check("T001", runner=runner())
    book.block("T001", "Need clarification")
    book.start("T001", resume=True)
    with pytest.raises(module.Refused, match="full-suite"):
        book.complete("T001", review(book))


def test_plan_change_needs_explicit_resume(book):
    book.start("T001")
    path = book.root / "docs/roadmap/backlog.json"
    data = json.loads(path.read_text())
    data["tasks"][0]["acceptance"] += "; additional owner criterion"
    path.write_text(json.dumps(data))
    changed = module.Book(book.root)
    try:
        with pytest.raises(module.Refused, match="plan changed"):
            changed.check("T001", runner=runner())
        changed.block("T001", "Owner revised criterion")
        changed.start("T001", resume=True)
        assert changed.check("T001", runner=runner())["passed"]
    finally:
        changed.close()


def test_exact_acceptance_and_external_evidence_refused(book, tmp_path):
    book.start("T001")
    book.check("T001", runner=runner())
    note = review(book)
    path = book.root / note
    data = json.loads(path.read_text())
    data["acceptance"] = "weakened"
    path.write_text(json.dumps(data))
    with pytest.raises(module.Refused, match="exact task"):
        book.complete("T001", note)
    data["acceptance"] = book.task("T001")["acceptance"]
    data["evidence"] = ["../outside.txt"]
    path.write_text(json.dumps(data))
    with pytest.raises(module.Refused, match="inside the project"):
        book.complete("T001", note)


def test_independent_review_required_on_integration_task(book):
    book.start("T003")
    book.check("T003", runner=runner())
    with pytest.raises(module.Refused, match="separate-session"):
        book.complete("T003", review(book, "T003"))
    assert book.complete("T003", review(book, "T003", independent=True))["status"] == "done"


def test_cycle_and_unknown_goal_refused(book):
    path = book.root / "docs/roadmap/backlog.json"
    data = json.loads(path.read_text())
    data["tasks"][0]["depends_on"] = ["T002"]
    path.write_text(json.dumps(data))
    with pytest.raises(module.Refused, match="cyclic"):
        module.Book(book.root)


def test_check_target_cannot_escape_or_add_options(book):
    book.start("T001")
    for target in ("../outside", "--override-ini=addopts="):
        with pytest.raises(module.Refused):
            book.check("T001", [target], runner=runner())
