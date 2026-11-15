"""Create a deterministic inventory of the CSEF checkout for T001."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import xml.etree.ElementTree as ET


EXCLUDED_DIRECTORIES = {
    ".csef-build", ".git", ".pytest_cache", ".venv", "__pycache__",
    "deliverables", "node_modules", "venv",
}
EXCLUDED_PREFIXES = ("docs/evidence/baseline-vnext/", "docs/progress/")
EXCLUDED_SUFFIXES = (".pyc", ".pyo")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for folder, directories, files in os.walk(root):
        base = Path(folder)
        directories[:] = sorted(name for name in directories if name not in EXCLUDED_DIRECTORIES)
        for name in directories:
            if (base / name).is_symlink():
                raise ValueError(f"symbolic-link directory is not supported: {base / name}")
        for name in sorted(files):
            path = base / name
            relative = path.relative_to(root).as_posix()
            if relative.startswith(EXCLUDED_PREFIXES) or path.suffix in EXCLUDED_SUFFIXES:
                continue
            if path.is_symlink():
                raise ValueError(f"symbolic-link file is not supported: {relative}")
            rows.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    return rows


def suite_observation(report: Path | None) -> dict[str, object] | None:
    if report is None:
        return None
    root = ET.parse(report).getroot()
    cases = list(root.iter("testcase"))
    return {
        "provenance": "JUnit content only; execution command and exit status belong to the controller receipt.",
        "cases": len(cases),
        "failed": len(list(root.iter("failure"))),
        "errors": len(list(root.iter("error"))),
        "skipped": len(list(root.iter("skipped"))),
        "report_sha256": sha256(report),
    }


def build(root: Path, report: Path | None) -> dict[str, object]:
    rows = inventory(root)
    result: dict[str, object] = {
        "schema_version": 1,
        "inventory_scope": {
            "root": ".",
            "excluded_directories": sorted(EXCLUDED_DIRECTORIES),
            "excluded_prefixes": list(EXCLUDED_PREFIXES),
            "excluded_suffixes": list(EXCLUDED_SUFFIXES),
        },
        "environment": {
            "python": sys.version,
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "files": rows,
        "file_count": len(rows),
        "inventory_sha256": hashlib.sha256(
            json.dumps(rows, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "limitations": [
            "This is an integrity inventory, not an attestation of authorship or safety.",
            "Excluded runtime, dependency, Git, and generated-delivery directories are intentionally not recorded.",
            "The suite observation records one local run; it does not establish release approval or host isolation.",
        ],
    }
    observation = suite_observation(report)
    if observation is not None:
        result["suite_observation"] = observation
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--junit-report", type=Path)
    parser.add_argument("--verify", action="store_true", help="Compare the current tree with this historical manifest without rewriting it")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    report = args.junit_report.resolve() if args.junit_report else None
    if report is not None and not report.is_file():
        parser.error(f"JUnit report does not exist: {report}")
    data = build(root, report)
    if args.verify:
        previous = json.loads(output.read_text(encoding="utf-8"))
        matches = previous["files"] == data["files"] and previous["inventory_sha256"] == data["inventory_sha256"]
        print(json.dumps({"matches": matches, "inventory_sha256": data["inventory_sha256"]}))
        return 0 if matches else 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
