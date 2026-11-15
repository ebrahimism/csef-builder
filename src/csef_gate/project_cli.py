from pathlib import Path
from .core import encoded, read_json, Refused
from .project import ProjectBook


def configure(sub):
    parser = sub.add_parser("project", help="persistent goals, questions and staged handoff packets")
    commands = parser.add_subparsers(dest="project_command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--root", type=Path, required=True)
    init.add_argument("--goal", required=True)
    init.add_argument("--brief", type=Path, help="optional owner answers and stable facts JSON")
    for name in ("status", "questions", "packet", "answer", "review", "assist", "route"):
        p = commands.add_parser(name)
        p.add_argument("--root", type=Path, required=True)
        if name == "packet":
            p.add_argument("--stage", required=True)
            p.add_argument("--inline", action="store_true", help="portable context with current source and linked evidence")
        if name == "review":
            p.add_argument("--stage", required=True)
            p.add_argument("--proposal", type=Path, required=True)
        if name == "assist":
            p.add_argument("--stage", required=True)
        if name == "route":
            p.add_argument("--stage", required=True)
            p.add_argument("--signal", action="append", default=[])
            p.add_argument("--always", action="store_true")
        if name == "answer":
            p.add_argument("--id", required=True)
            p.add_argument("--text", required=True)
    return parser


def execute(args):
    if args.project_command == "init":
        brief = read_json(args.brief) if args.brief else {}
        if set(brief) - {"answers", "facts", "stages"}:
            raise Refused("brief supports answers, facts and optional stage definitions")
        book = ProjectBook.create(args.root, args.goal, **brief)
        return book.status()
    book = ProjectBook(args.root)
    if args.project_command == "status":
        return book.status()
    if args.project_command == "questions":
        return {"questions": book.questions()}
    if args.project_command == "packet":
        return book.context(args.stage) if args.inline else book.packet(args.stage)
    if args.project_command == "review":
        from .model_session import CodexJSON
        from .review import review_proposal
        return review_proposal(book, args.stage, read_json(args.proposal), CodexJSON())
    if args.project_command == "assist":
        from .model_session import CodexJSON
        from .assistant import assist_stage
        return assist_stage(book, args.stage, CodexJSON())
    if args.project_command == "route":
        from .review import route_review
        book.packet(args.stage)
        return route_review(args.stage, args.signal, always=args.always)
    book.amend(answers={args.id: args.text}, reason="explicit owner answer")
    return book.status()
