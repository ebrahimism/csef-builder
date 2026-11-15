"""Reproducible evidence collector. Mutations run only in temporary copies."""
import ast
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verification_step5" / "evidence"
OUT.mkdir(exist_ok=True)
ledger = []


def run(name, command, cwd=ROOT, env=None):
    started = datetime.now(timezone.utc).isoformat()
    try:
        p = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=90)
        record = dict(command=command, cwd=str(cwd), exit_code=p.returncode,
                      stdout=p.stdout, stderr=p.stderr, started_utc=started)
    except subprocess.TimeoutExpired as e:
        record = dict(command=command, cwd=str(cwd), exit_code=None, timeout_seconds=90,
                      stdout=str(e.stdout), stderr=str(e.stderr), started_utc=started)
    (OUT / (name + ".json")).write_text(json.dumps(record, indent=2), encoding="utf-8")
    ledger.append(dict(claim=name, evidence_type="command output / test result",
                       artifact_path=str(OUT / (name + ".json")), status="EXECUTED",
                       command=command, exit_code=record["exit_code"]))
    return record


def main():
    baseline = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob("test_*_contract.py"))
    run("baseline", [sys.executable, "-m", "pytest", *baseline,
                     "--junitxml=verification_step5/evidence/baseline.xml"])
    run("negative_characterization", [sys.executable, "-m", "pytest", "tests/audit",
                     "--junitxml=verification_step5/evidence/negative.xml"])

    # Exact assertion inventory, including exception assertions and fixture code.
    limitations = {
        "task": "No integrated gateway/guard ordering, all transition pairs, persisted logs, cost guard or real ambiguity detection.",
        "tool": "No real effect, sandbox, full capability-policy join, journal ordering, closed custom input schema or output validation.",
        "policy": "No durable/distributed accounting, settlement replay, path resolution, concurrent approval consumption, capability join or project cap.",
        "evidence": "No authenticated writer, stored content/hash recomputation, exit-code evaluation, clean checkout, invocation lookup or per-item environment binding.",
        "checkpoint": "No signed verifier authority, verified commit binding, durable chain/invalidation, stale ancestor closure, Git/SQLite crash consistency or reproduction.",
        "failure": "No complete error/status cross product, retry budget/backoff, diagnosis requirement, task-state propagation or durable unknown-effect reconciliation.",
    }
    rows = ["# Per-test assertion scope\n", "EXECUTED: baseline.json and baseline.xml record this run.\n",
            "Each row proves only the listed assertion/exception for the concrete fixture in the linked function. Calls without assertions exercise a path; they establish no additional postcondition. No universal proof is claimed.\n",
            "| Test / source line | Exact checked predicates (fixture-local proof) | Exercised calls | Unverified |",
            "|---|---|---|---|"]
    inventory = []
    for rel in baseline:
        source = (ROOT / rel).read_text(encoding="utf-8")
        tree = ast.parse(source)
        category = Path(rel).stem.split("_")[1]
        for f in tree.body:
            if not isinstance(f, ast.FunctionDef) or not f.name.startswith("test_"):
                continue
            predicates = [ast.unparse(n.test) for n in ast.walk(f) if isinstance(n, ast.Assert)]
            exceptions = [ast.unparse(n) for n in ast.walk(f) if isinstance(n, ast.Call) and
                          isinstance(n.func, ast.Attribute) and n.func.attr == "raises"]
            calls = sorted({ast.unparse(n.func) for n in ast.walk(f) if isinstance(n, ast.Call)})
            checks = "; ".join(predicates + exceptions).replace("|", "\\|")
            rows.append(f"| {rel}:{f.lineno} `{f.name}` | `{checks}` | {', '.join(calls)} | {limitations[category]} |")
            inventory.append(dict(test=f.name, file=rel, line=f.lineno,
                                  exact_fixture_and_body=ast.get_source_segment(source, f),
                                  predicates=predicates, exceptions=exceptions,
                                  exercised_calls=calls, unverified=limitations[category]))
    (OUT / "test-scope.md").write_text("\n".join(rows), encoding="utf-8")
    (OUT / "test-scope.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")

    vectors = []
    # Exhaustive bounded property: all 121 decision sequences of length 0..4.
    for length in range(5):
        for seq in itertools.product(("allow", "ask", "deny"), repeat=length):
            expected = "deny" if not seq or "deny" in seq else "ask" if "ask" in seq else "allow"
            vectors.append(dict(id=f"POL-{len(vectors):03}", status="normative",
                basis="30-policy section 2; empty case I6", request=dict(op="resolve", decisions=seq), expected=expected))
    for error in ("bad_input", "transient", "policy_denied", "environment", "product_bug",
                  "budget_exhausted", "sandbox_violation", "unknown"):
        vectors.append(dict(id="CLASS-"+error, status="normative", basis="60-failure section 1",
            request=dict(op="classify", error=error, outcome="failed"), expected=error))
    vectors.append(dict(id="CONFLICT-001", status="proposed", basis="ADR-S5-003: denial vs unknown replay",
        request=dict(op="recover", error="policy_denied", outcome="unknown", idempotency="read_only"), expected="escalate"))
    corpus = ROOT / "verification_step5" / "corpus.json"
    corpus.write_text(json.dumps(vectors, indent=2), encoding="utf-8")
    # Import once in isolated subprocess batches, rather than 260 interpreter starts.
    run("differential", [sys.executable, "verification_step5/differential.py"])

    mutations = [
        ("deny_precedence", "policy.py", "if Decision.DENY in decisions:", "if False:"),
        ("baseline_guard", "checkpoint.py", "if bundle.baseline_hash != task.acceptance.baseline_hash:", "if False:"),
        ("environment_guard", "evidence.py", "if bundle.env_fingerprint != inputs.env_fingerprint:", "if False:"),
        ("approval_replay", "policy.py", "if used >= auth.max_uses:", "if False:"),
        ("rollback_noop", "policy.py", "self._reserved -= reservation.amount_usd", "self._reserved -= Decimal('0')"),
    ]
    mutation_results = []
    for name, module, old, new in mutations:
        with tempfile.TemporaryDirectory(prefix="csef-step5-") as temp:
            target = Path(temp)
            shutil.copytree(ROOT / "src", target / "src", ignore=shutil.ignore_patterns("__pycache__"))
            (target / "tests").mkdir()
            for rel in baseline + ["tests/support.py"]:
                shutil.copy2(ROOT / rel, target / rel)
            shutil.copy2(ROOT / "pyproject.toml", target / "pyproject.toml")
            path = target / "src" / "csef_contracts" / module
            content = path.read_text(encoding="utf-8")
            assert old in content
            # Last occurrence targets rollback, leaving commit untouched.
            pos = content.rfind(old) if name == "rollback_noop" else content.index(old)
            path.write_text(content[:pos] + new + content[pos+len(old):], encoding="utf-8")
            r = run("mutant_"+name, [sys.executable, "-m", "pytest", *baseline], cwd=target)
            mutation_results.append(dict(name=name, module=module, old=old, new=new,
                outcome="killed" if r["exit_code"] == 1 else "survived" if r["exit_code"] == 0 else "invalid",
                evidence="mutant_"+name+".json"))
    (OUT / "mutation-summary.json").write_text(json.dumps(mutation_results, indent=2), encoding="utf-8")
    hashes = {}
    for folder in ("src", "tests", "docs", "verification_step5/reference"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT / "manifest.json").write_text(json.dumps(dict(python=sys.version, platform=platform.platform(),
        files=hashes, note="Hashes bind inspected inputs, not author independence or runtime isolation."), indent=2), encoding="utf-8")
    (OUT / "ledger.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    print(json.dumps(dict(commands=len(ledger), inventoried_tests=len(inventory), mutations=mutation_results), indent=2))


if __name__ == "__main__":
    main()
