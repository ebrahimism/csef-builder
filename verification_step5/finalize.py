"""Validate report consistency and preserve final artifact hashes; no test execution."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verification_step5/evidence"
logs = json.loads((OUT / "ledger.json").read_text(encoding="utf-8"))
assert len(logs) == 8
for row in logs:
    record = json.loads(Path(row["artifact_path"]).read_text(encoding="utf-8"))
    assert row["exit_code"] == record["exit_code"]
    assert row["command"] == record["command"]
scope = json.loads((OUT / "test-scope.json").read_text(encoding="utf-8"))
assert len(scope) == 48
results = json.loads((OUT / "differential-results.json").read_text(encoding="utf-8"))
assert results["summary"]["cases"] == len(results["results"]) == 130
assert results["summary"]["divergences"] == 2
mutants = json.loads((OUT / "mutation-summary.json").read_text(encoding="utf-8"))
assert [m["outcome"] for m in mutants].count("killed") == 4
assert [m["outcome"] for m in mutants].count("survived") == 1
tree = ast.parse((ROOT / "verification_step5/reference/model.py").read_text(encoding="utf-8"))
imports = [n.module if isinstance(n, ast.ImportFrom) else a.name
           for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
           for a in (n.names if isinstance(n, ast.Import) else [None])]
assert set(imports) == {"json", "sys"}
report = dict(command="python verification_step5/finalize.py", exit_code=0,
              checks="ledger/log consistency; 48 inventory rows; 130 cases; mutation summary; reference static imports",
              reference_imports=imports, note="Static imports do not prove clean-room provenance or confinement.")
(OUT / "final-validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
manifest_path = OUT / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
manifest["files"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
    for folder in ("src", "tests", "docs", "verification_step5")
    for p in (ROOT / folder).rglob("*")
    if p.is_file() and "__pycache__" not in p.parts and "evidence" not in p.parts}
manifest["evidence_files"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
    for p in OUT.iterdir() if p.is_file() and p.name != "manifest.json"}
manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps(report))
