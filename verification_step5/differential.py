"""Same immutable request values to two subprocesses; docs supply expected values."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def batch(module_path, requests):
    code = ("import importlib.util,json,sys; "
            "s=importlib.util.spec_from_file_location('candidate',sys.argv[1]); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
            "print(json.dumps([m.evaluate(r) for r in json.load(sys.stdin)]))")
    p = subprocess.run([sys.executable, "-I", "-c", code, str(module_path)],
                       input=json.dumps(requests), text=True, capture_output=True, timeout=30)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return json.loads(p.stdout)


def main():
    cases = json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))
    reqs = [c["request"] for c in cases]
    first, second = batch(HERE / "primary.py", reqs), batch(HERE / "reference/model.py", reqs)
    assert len(first) == len(second) == len(cases)
    results = []
    for case, a, b in zip(cases, first, second):
        results.append(dict(**case, primary=a, reference=b, divergent=a != b,
            primary_conforms=a == case["expected"], reference_conforms=b == case["expected"]))
    summary = dict(cases=len(results), divergences=sum(r["divergent"] for r in results),
        primary_normative_failures=sum(not r["primary_conforms"] for r in results if r["status"] == "normative"),
        reference_normative_failures=sum(not r["reference_conforms"] for r in results if r["status"] == "normative"),
        pending=sum(r["status"] == "proposed" for r in results))
    (HERE / "evidence/differential-results.json").write_text(json.dumps(dict(summary=summary, results=results), indent=2), encoding="utf-8")
    print(json.dumps(summary))
    return 1 if summary["primary_normative_failures"] or summary["reference_normative_failures"] else 2 if summary["pending"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
