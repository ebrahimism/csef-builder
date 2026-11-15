"""Small reusable adapter for schema-bound calls to the installed coding agent."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from .backends import capture, environment, installed_codex, profile_args
from .core import Refused, digest, encoded, read_json


class CodexJSON:
    def __init__(self):
        self.codex = installed_codex()

    def call(self, *, prompt, schema, folder: Path, control: Path, timeout=180, role="worker"):
        folder.mkdir(parents=True, exist_ok=False)
        stage = control.parent / "csef-session-work" / uuid.uuid4().hex
        stage.mkdir(parents=True)
        schema_path, final = folder / "schema.json", folder / "final.json"
        schema_path.write_bytes(encoded(schema))
        (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
        argv = [self.codex, "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check", "--json",
                *profile_args("csef-session", [stage], denies=[control]),
                "-c", 'default_permissions="csef-session"', "-c", 'windows.sandbox="elevated"',
                "-C", str(stage), "--output-schema", str(schema_path), "-o", str(final), "-"]
        # The caller persists/charges an attempt BEFORE invoking this adapter.
        process = capture(argv, cwd=stage, timeout=timeout, env=environment(), stdin=prompt, limit=1_000_000)
        (folder / "events.jsonl").write_text(process["stdout"], encoding="utf-8")
        (folder / "stderr.txt").write_text(process["stderr"], encoding="utf-8")
        usage, models = [], []
        for line in process["stdout"].splitlines():
            try:
                event = json.loads(line)
                if event.get("type") == "turn.completed":
                    usage.append(event.get("usage", {}))
                if isinstance(event.get("model"), str):
                    models.append(event["model"])
            except ValueError:
                pass
        receipt = {"adapter": "codex-exec", "role": role, "prompt_utf8_bytes": len(prompt.encode("utf-8")),
                   "command_sha256": digest(encoded(argv)), "schema_sha256": digest(encoded(schema)),
                   "exit_code": process["exit_code"], "timed_out": process["timed_out"], "overflow": process["overflow"],
                   "elapsed_s": process["elapsed_s"], "usage": usage, "reported_models": models,
                   "cost_usd": None, "cost_note": "Existing CLI account; tokens are usage, not a measured dollar price."}
        (folder / "receipt.json").write_bytes(encoded(receipt))
        if process["exit_code"] != 0 or process["timed_out"] or process["overflow"] or not final.is_file():
            raise Refused(f"{role} call failed; see {folder}")
        if final.stat().st_size > 1_000_000:
            raise Refused("oversized model output")
        return read_json(final), receipt
