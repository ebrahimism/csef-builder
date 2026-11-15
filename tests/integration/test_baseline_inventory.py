"""A historical baseline must remain valid when later tasks change the source."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "baseline_inventory.py"
EVIDENCE = ROOT / "docs" / "evidence" / "baseline-vnext" / "manifest.json"


def load_module():
    spec = importlib.util.spec_from_file_location("baseline_inventory", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inventory_detects_edits_and_ignores_runtime_without_mutating_input(tmp_path):
    module = load_module()
    source = tmp_path / "app.py"
    source.write_bytes(b"value = 1\n")
    initial = module.build(tmp_path, None)
    assert module.build(tmp_path, None) == initial
    runtime = tmp_path / ".csef-build"
    runtime.mkdir()
    (runtime / "state.sqlite").write_text("runtime changed")
    assert module.build(tmp_path, None) == initial
    source.write_text("value = 2\n")
    assert module.build(tmp_path, None)["inventory_sha256"] != initial["inventory_sha256"]
    assert source.read_text() == "value = 2\n"
    assert initial["files"][0]["sha256"] == hashlib.sha256(b"value = 1\n").hexdigest()


def test_historical_manifest_is_internally_consistent_without_freezing_future_work():
    expected = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    rows = expected["files"]
    canonical = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    assert expected["schema_version"] == 1
    assert expected["inventory_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert expected["file_count"] == len(rows) > 0
    assert len({r["path"] for r in rows}) == len(rows)
    assert all(not Path(r["path"]).is_absolute() and ".." not in Path(r["path"]).parts for r in rows)
    assert "docs/PROJECT-GOALS.json" in {r["path"] for r in rows}
    assert expected["limitations"]


@pytest.mark.parametrize("node,field", [("failure", "failed"), ("error", "errors"), ("skipped", "skipped")])
def test_junit_observation_preserves_failures_and_does_not_invent_execution_status(tmp_path, node, field):
    module = load_module()
    report = tmp_path / "junit.xml"
    report.write_text(f"<testsuite><testcase><{node}/></testcase></testsuite>")
    observed = module.suite_observation(report)
    assert observed["cases"] == 1
    assert observed[field] == 1
    assert "exit_code" not in observed and "command" not in observed
    assert observed["report_sha256"] == hashlib.sha256(report.read_bytes()).hexdigest()
