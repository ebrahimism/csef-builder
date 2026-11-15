"""Implementation-neutral JSON subprocess runner. No production imports.

Exit 0 = all normative cases pass AND no open oracle decisions.
Exit 1 = mismatch/protocol failure. Exit 2 = pending oracle decisions only.
Each adapter receives one JSON request on stdin, emits one JSON value, then exits.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vectors", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("adapter command required after --")
    raw = args.vectors.read_bytes()
    cases = json.loads(raw)
    if not isinstance(cases, list) or not cases:
        parser.error("vectors must be a nonempty list")
    ids = set()
    for case in cases:
        if (not isinstance(case, dict) or
            not {"id", "request", "status", "basis", "expected"} <= case.keys() or
            case["status"] not in ("normative", "proposed") or
            not isinstance(case["id"], str) or case["id"] in ids):
            parser.error("invalid or duplicate vector")
        ids.add(case["id"])
    results = []
    for case in cases:
        try:
            run = subprocess.run(command, input=json.dumps(case["request"]),
                                 text=True, capture_output=True, timeout=10, check=False)
            if run.returncode:
                raise RuntimeError(f"exit={run.returncode}; stderr={run.stderr[:2000]}")
            actual = json.loads(run.stdout)
            status = ("pending" if case["status"] == "proposed" else
                      "pass" if actual == case["expected"] else "fail")
            results.append(dict(id=case["id"], status=status, actual=actual,
                                expected=case.get("expected"), basis=case["basis"]))
        except (ValueError, OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            results.append(dict(id=case["id"], status="fail", error=str(exc)))
    report = dict(vector_sha256=hashlib.sha256(raw).hexdigest(), command=command, results=results)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    counts = {s: sum(r["status"] == s for r in results) for s in ("pass", "fail", "pending")}
    print(json.dumps(counts))
    return 1 if counts["fail"] else 2 if counts["pending"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
