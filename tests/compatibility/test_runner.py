"""Check the seed verifier's failure accounting independently of production code."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

RUNNER = Path(__file__).resolve().parents[2] / "compatibility" / "run.py"


@pytest.mark.parametrize("program,case_status,expected,exit_code,status", [
    ('print("1")', "normative", 1, 0, "pass"),
    ('print("2")', "normative", 1, 1, "fail"),
    ('print("1")', "proposed", 1, 2, "pending"),
    ('print("not JSON")', "normative", 1, 1, "fail"),
    ('raise SystemExit(3)', "normative", 1, 1, "fail"),
])
def test_runner_records_gate_status(tmp_path, program, case_status, expected, exit_code, status):
    vectors, report = tmp_path / "vectors.json", tmp_path / "report.json"
    vectors.write_text(json.dumps([dict(id="case", request={}, status=case_status,
                                       expected=expected, basis="runner unit test")]))
    result = subprocess.run([sys.executable, str(RUNNER), "--vectors", str(vectors),
                             "--report", str(report), "--", sys.executable, "-c", program],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == exit_code, result.stderr
    assert json.loads(report.read_text())["results"][0]["status"] == status


def test_empty_suite_cannot_certify(tmp_path):
    vectors = tmp_path / "empty.json"
    vectors.write_text("[]")
    result = subprocess.run([sys.executable, str(RUNNER), "--vectors", str(vectors),
                             "--report", str(tmp_path / "report.json"), "--",
                             sys.executable, "-c", 'print("1")'], capture_output=True, timeout=20)
    assert result.returncode != 0
