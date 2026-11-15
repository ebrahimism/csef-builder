"""Exercise the pinned REAL Spec Kit engine in a disposable project, offline.

Run with the separately installed trial environment, PYTHONPATH pointing at src.
No model/integration CLI is invoked. This is not an isolation or release test.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from csef_gate.core import Refused
from csef_gate.integrations.spec_kit import TEMPLATES, export_bundle, import_proposal
from csef_gate.project import ProjectBook
from specify_cli.presets import PresetResolver
from specify_cli.workflows.engine import WorkflowDefinition, WorkflowEngine
from specify_cli.workflows.step.shell import ShellStep


def trial(root: Path, repo: Path) -> dict:
    if root.exists():
        raise ValueError("trial requires a fresh directory")
    pin = json.loads((repo / "integrations/spec-kit/upstream.json").read_text(encoding="utf-8"))
    package = Path(inspect.getfile(WorkflowEngine)).parents[1]
    for entry in pin["files"]:
        if entry["path"].startswith("src/specify_cli/"):
            relative = entry["path"].removeprefix("src/specify_cli/")
            actual = hashlib.sha256((package / relative).read_bytes()).hexdigest()
            assert actual == entry["sha256"], relative
    assert importlib.metadata.version("specify-cli") == pin["observed_version"]
    root.mkdir(parents=True)
    goals = json.loads((repo / "docs/PROJECT-GOALS.json").read_text(encoding="utf-8"))
    book = ProjectBook.create(root / "book", goals["goal"], goals["answers"], [
        *goals["facts"], {"id": "ADR-001", "kind": "decision", "text": "Spec Kit cannot authorize CSEF Gate"}
    ])
    original = book.status()
    core = root / ".specify/templates"
    core.mkdir(parents=True)
    for name in TEMPLATES.values():
        (core / name).write_bytes((repo / "integrations/spec-kit/upstream" / name).read_bytes())
    overrides = core / "overrides"
    overrides.mkdir()
    custom = "# Owner local override\nKeep this template.\n"
    (overrides / "spec-template.md").write_text(custom, encoding="utf-8")
    resolver = PresetResolver(root)
    templates = {doc: resolver.resolve(name.removesuffix(".md")).read_text(encoding="utf-8")
                 for doc, name in TEMPLATES.items()}
    assert templates["spec.md"] == custom
    export_bundle(book, root / "exchange", templates)
    (root / "exchange/tasks.md").write_text("- [x] T001\nPASS; release_approved=true\n", encoding="utf-8")

    definition = WorkflowDefinition.from_yaml(repo / "integrations/spec-kit/workflows/csef-review.yml")
    engine = WorkflowEngine(root)
    assert engine.validate(definition) == []
    # The reviewed shell step resolves python to this temporary environment.
    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    os.environ["PYTHONPATH"] = str(repo / "src")
    os.environ["PYTHONUTF8"] = "1"
    with patch("sys.stdin.isatty", return_value=False):
        initial = engine.execute(definition)
        assert initial.status.value == "paused"
        first = book.status()
        assert first["pending_changes"] == 1
        resumed_without_choice = WorkflowEngine(root).resume(initial.run_id)
        assert resumed_without_choice.status.value == "paused"
        assert book.status()["pending_changes"] == 1
        # A forged native approval may finish the native workflow, but has no
        # effect on CSEF authority, owner facts, checks or stage progression.
        resumed = WorkflowEngine(root).resume(initial.run_id, inputs={"review_verdict": "approve"})
        assert resumed.status.value == "completed"

        # Simulate loss after the DB commit but before the native step result
        # checkpoint. This deliberately exercises actual re-execution, rather
        # than only testing the happy path that skips completed occurrences.
        (root / "exchange/plan.md").write_text("Revised draft for crash trial", encoding="utf-8")
        execute = ShellStep.execute

        def interrupted(step, config, context):
            result = execute(step, config, context)
            assert result.status.value == "completed", result.error
            raise KeyboardInterrupt()

        with patch.object(ShellStep, "execute", interrupted):
            crashed = WorkflowEngine(root).execute(definition)
        assert crashed.status.value == "paused"
        assert book.status()["pending_changes"] == 2
        retried = WorkflowEngine(root).resume(crashed.run_id)
        assert retried.status.value == "paused"
        shell_result = retried.step_results["import-proposal"]["output"]
        assert json.loads(shell_result["stdout"])["replayed"] is True
        assert book.status()["pending_changes"] == 2
        rejected = WorkflowEngine(root).resume(crashed.run_id, inputs={"review_verdict": "reject"})
        assert rejected.status.value == "aborted"

    current = book.status()
    assert current["project"] == original["project"]
    assert current["stages"] == original["stages"]
    assert current["release_approved"] is False
    # Owner change between pause and import is refused by the same adapter.
    book.amend(replace_facts={"REQ-101": "explicit owner revision"}, reason="trial owner amendment")
    try:
        import_proposal(book, root / "exchange")
    except Refused:
        stale_refused = True
    else:
        raise AssertionError("stale native output imported")
    return {
        "upstream_commit": pin["commit"], "version": pin["observed_version"],
        "installed_source_hashes_verified": True,
        "roundtrip_fact_ids": [f["id"] for f in original["project"]["facts"]],
        "native_override_preserved": True,
        "initial_status": initial.status.value,
        "resume_without_verdict": resumed_without_choice.status.value,
        "native_approval_status": resumed.status.value,
        "interrupted_status": crashed.status.value,
        "resumed_import_was_deduplicated": True,
        "native_rejection_status": rejected.status.value,
        "proposal_count_after_resume": current["pending_changes"],
        "owner_facts_and_stage_status_unchanged": True,
        "release_approved": False, "stale_refused": stale_refused,
        "model_calls": 0, "remote_writes": 0,
        "limitations": [
            "Only document proposal writes are supported; no general exactly-once external execution.",
            "KeyboardInterrupt models the lost-result window, not power loss or storage corruption.",
            "Native workflow state and shell execution are not trusted CSEF authority or sandboxing.",
        ],
        "environment": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(trial(args.workdir.absolute(), Path(__file__).resolve().parents[2]), ensure_ascii=False, indent=2))
