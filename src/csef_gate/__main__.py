from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .backends import CodexAgent, CodexSandbox
from .core import Gate, Refused, read_json


def main(argv=None):
    p = argparse.ArgumentParser(description="CSEF: existing agent + independent black-box acceptance gate")
    sub = p.add_subparsers(dest="command", required=True)
    from .project_cli import configure
    configure(sub)
    init = sub.add_parser("init")
    init.add_argument("--control", type=Path, required=True)
    init.add_argument("--project", type=Path, required=True)
    init.add_argument("--spec", type=Path, required=True)
    for name in ("prepare", "evaluate", "accept", "run", "propose", "apply"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--control", type=Path, required=True)
        if name not in ("prepare", "run"):
            cmd.add_argument("--run-id", required=True)
        elif name == "run":
            cmd.add_argument("--run-id", help="resume an unaccepted run; attempt budget is persistent")
        if name in ("evaluate", "run"):
            cmd.add_argument("--measure-only", action="store_true", help="reviewed local pilot only: measure behavior, never issue acceptance/checkpoint")
        if name == "apply":
            cmd.add_argument("--proposal", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.command == "project":
            from .project_cli import execute
            result = execute(args)
        elif args.command == "init":
            gate = Gate.initialize(args.control, args.project, args.spec)
            result = {"status": "initialized", "control": str(gate.root)}
        else:
            gate = Gate(args.control)
            if args.command == "prepare":
                result = {"run_id": gate.prepare()}
            elif args.command == "apply":
                gate.apply_proposal(args.run_id, read_json(args.proposal))
                result = {"status": "prepared", "run_id": args.run_id}
            elif args.command == "evaluate":
                result = gate.evaluate(args.run_id, CodexSandbox(), measure_only=args.measure_only)
            elif args.command == "accept":
                result = {"status": "accepted", "checkpoint": gate.accept(args.run_id)}
            elif args.command == "propose":
                result = gate.agent_attempt(args.run_id, CodexAgent())
            else:
                def progress(report):
                    print(json.dumps({"run_id": report["run_id"], "evaluation_id": report["evaluation_id"], "status": report["status"], "passed": sum(c["passed"] for c in report["cases"]), "total": len(report["cases"]), "error": report["error"]}), file=sys.stderr, flush=True)
                result = gate.run(CodexSandbox(), CodexAgent(), args.run_id, progress, measure_only=args.measure_only)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 2 if result.get("status") in ("review", "awaiting_owner", "draft_requires_validation") else 1 if result.get("status") in ("fail", "blocked") else 0
    except (Refused, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
