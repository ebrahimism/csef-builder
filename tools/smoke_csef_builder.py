"""Fresh, bounded Codex session: discover installed skill and inspect kickoff only."""
from pathlib import Path
import json
import re
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from csef_gate.backends import capture, environment, installed_codex, profile_args


def assess(folder, result):
    final = json.loads((folder / "final.json").read_text(encoding="utf-8")) if (folder / "final.json").exists() else {}
    skill = Path(final.get("skill_path", "missing"))
    events = (folder / "events.jsonl").read_text(encoding="utf-8")
    match = re.match(r"^(T\d{3})(?:\s|$)", final.get("next_task", ""))
    next_id = match.group(1) if match else None
    passed = (result["exit_code"] == 0 and not result["timed_out"] and not result["overflow"]
              and next_id == "T001" and final.get("batch") == ["T001", "T002"]
              and final.get("release_authority") is False and skill.is_file()
              and "csef-local" in skill.parts and "cache" in skill.parts
              and "SKILL.md" in events and "command_execution" in events)
    summary = {"passed": passed, "folder": str(folder), "result": final, "next_task_id": next_id,
               "exit_code": result["exit_code"], "elapsed_s": result["elapsed_s"],
               "timed_out": result["timed_out"]}
    (ROOT / "docs/progress/plugin-smoke.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if passed else 1


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--assess":
        previous = json.loads((ROOT / "docs/progress/plugin-smoke.json").read_text(encoding="utf-8"))
        folder = Path(sys.argv[2]).resolve()
        if str(folder) != previous["folder"]:
            raise ValueError("re-assessment must use the recorded smoke session")
        return assess(folder, previous | {"overflow": False})
    folder = ROOT / ".csef-build/smoke" / uuid.uuid4().hex
    folder.mkdir(parents=True)
    schema = {"type": "object", "additionalProperties": False, "properties": {
        "skill_path": {"type": "string"}, "next_task": {"type": "string", "pattern": "^T[0-9]{3}$"},
        "batch": {"type": "array", "items": {"type": "string"}},
        "release_authority": {"type": "boolean"}, "reason": {"type": "string"}},
        "required": ["skill_path", "next_task", "batch", "release_authority", "reason"]}
    (folder / "schema.json").write_text(json.dumps(schema), encoding="utf-8")
    prompt = """Use $csef-build for a READ-ONLY installation smoke test in this CSEF checkout.
Read the SKILL.md from the installed csef-builder plugin, not the repository fallback.
Read AGENTS.md, owner goals, backlog definitions and docs/progress/START-PROMPT.txt.
Report the absolute installed skill path you actually read, the next eligible task,
the initial authorized batch, and whether this tracker grants release authority.
Do not start tasks, run the tracker, modify files, contact services or implement work.
Current build progress is fresh: no backlog task has started. Just verify discovery.
"""
    (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
    argv = [installed_codex(), "exec", "--ephemeral", "--skip-git-repo-check", "--json",
            *profile_args("csef-plugin-smoke", [ROOT], scratch=folder),
            "-c", 'default_permissions="csef-plugin-smoke"',
            "-c", 'windows.sandbox="elevated"', "-C", str(ROOT),
            "--output-schema", str(folder / "schema.json"), "-o", str(folder / "final.json"), "-"]
    result = capture(argv, cwd=ROOT, timeout=240, env=environment(), stdin=prompt, limit=1_000_000)
    (folder / "events.jsonl").write_text(result["stdout"], encoding="utf-8")
    (folder / "stderr.txt").write_text(result["stderr"], encoding="utf-8")
    return assess(folder, result)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
