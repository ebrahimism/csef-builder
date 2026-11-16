"""Bounded stage selection and mechanical document checks, not semantic proof."""
from ..core import Refused, digest, parse_json, plain, relative_name


def pipeline(book):
    with book.connection() as con:
        rows = [dict(r) for r in con.execute("SELECT * FROM stages ORDER BY position")]
    if not 6 <= len(rows) <= 24:
        raise Refused("the general workflow requires six to twenty-four stages")
    return rows


def next_stage(book):
    rows = pipeline(book)
    stage = next((row for row in rows if row["status"] != "ready_for_next"), None)
    if stage is None:
        current = book.current()
        for row in rows:
            if row["version"] != current["version"] or not row["handoff"]:
                raise Refused("completed handoff is not current")
            for item in parse_json(row["handoff"])["artifacts"]:
                path = book.root / relative_name(item["path"])
                plain(path)
                if not path.is_file() or path.stat().st_size > 1_000_000:
                    raise Refused("completed handoff artifact is missing or oversized")
                content = path.read_bytes()
                if len(content) > 1_000_000 or digest(content) != item["sha256"]:
                    raise Refused("completed handoff artifact changed")
    return stage


def document_artifacts(draft, project):
    artifacts = {}
    for item in draft.get("drafts", []):
        name = relative_name(item["path"])
        if name.casefold() in {key.casefold() for key in artifacts}:
            raise Refused("duplicate document path")
        text = item["content"]
        if not isinstance(text, str) or not text.strip() or len(text.encode()) > 1_000_000:
            raise Refused("nonempty bounded stage document required")
        artifacts[name] = text.encode()
    combined = "\n".join(value.decode() for value in artifacts.values())
    checks = [
        {"id": "DOCUMENTS", "passed": bool(artifacts), "basis": "Controller checked paths and nonempty bounded document bytes."},
        {"id": "FACT_REFERENCES", "passed": all(f["id"] in combined for f in project["facts"]),
         "basis": "All owner fact IDs must be referenced; reference presence does not prove semantic compliance."},
        {"id": "OPEN_ISSUES", "passed": draft.get("issues") == [], "basis": "Unresolved reported issues block a handoff."},
    ]
    return artifacts, checks
