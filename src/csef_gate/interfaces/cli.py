"""CLI adapter for the same application service used by conversation callers."""
from pathlib import Path

from ..core import Refused, read_json
from ..workflow import Workflow


def configure(sub):
    parser = sub.add_parser("workflow", help="continue the six-stage engineering workflow")
    commands = parser.add_subparsers(dest="workflow_command", required=True)
    for name in ("init", "status", "attach", "continue"):
        command = commands.add_parser(name)
        command.add_argument("--root", type=Path, required=True)
        if name == "init":
            command.add_argument("--goal", required=True)
            command.add_argument("--brief", type=Path)
        if name == "attach":
            command.add_argument("--project", type=Path, required=True)
            command.add_argument("--spec", type=Path, required=True)
        if name == "continue":
            command.add_argument("--steps", type=int, default=24)
            command.add_argument("--measure-only", action="store_true")


def execute(args):
    if args.workflow_command == "init":
        brief = read_json(args.brief) if args.brief else {}
        if not isinstance(brief, dict) or set(brief) - {"answers", "facts", "stages"}:
            raise Refused("brief supports answers, facts and stage definitions")
        return Workflow.create(args.root, args.goal, **brief).status()
    workflow = Workflow(args.root)
    if args.workflow_command == "status":
        return workflow.status()
    if args.workflow_command == "attach":
        return workflow.attach_code(args.project, args.spec)
    state = workflow.status()
    if state["status"] in ("awaiting_owner", "complete"):
        return state  # Questions/status work even when no model CLI is installed.
    from ..backends import CodexAgent, CodexSandbox
    from ..model_session import CodexJSON
    client = CodexJSON()
    return workflow.run(max_steps=args.steps, client=client, reviewer=client,
                        agent=CodexAgent(), executor=CodexSandbox(), measure_only=args.measure_only)
