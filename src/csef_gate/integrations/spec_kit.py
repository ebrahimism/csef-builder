"""Lossless Spec Kit document exchange, with proposal-only, retry-safe import.

This adapter never runs workflow text, finishes stages or calls the Gate.
The existing ProjectBook stores proposals; no second authority DB is introduced.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..core import Refused, digest, encoded, file_bytes, parse_json, plain
from ..project import ProjectBook


UPSTREAM_COMMIT = "2ee2b1e8005905db05f5717300a469b3068b908f"
DOCUMENTS = ("spec.md", "plan.md", "tasks.md")
TEMPLATES = dict(zip(DOCUMENTS, ("spec-template.md", "plan-template.md", "tasks-template.md")))


def _origin(book: ProjectBook) -> str:
    # ProjectBook has no durable project UUID yet. Limit this spike to the
    # exporting book's location; copying/moving a book requires a fresh export.
    return digest(str(book.root.resolve()).casefold().encode("utf-8"))


def export_bundle(book: ProjectBook, destination: Path, templates: dict[str, str]) -> dict:
    """Export into a NEW directory, preserving supplied template/override text.

    Callers resolve their template selection before calling; this function
    neither installs a preset nor replaces project-local Spec Kit overrides.
    """
    destination = Path(destination).absolute()
    plain(destination)
    if destination.exists():
        raise Refused("export requires a new directory; existing files are preserved")
    if set(templates) != set(DOCUMENTS) or any(not isinstance(t, str) or not t.strip() for t in templates.values()):
        raise Refused("three nonempty resolved templates required")
    snapshot = book.current()
    envelope = {"format": "csef-spec-kit-v1", "upstream_commit": UPSTREAM_COMMIT,
                "origin": _origin(book), "project": snapshot}
    references = "\n\n## CSEF owner facts (reference only)\n\n" + "\n".join(
        f"- {f['id']} ({f['kind']}): {json.dumps(f['text'], ensure_ascii=False)}"
        for f in snapshot["facts"]
    )
    documents = {
        "spec.md": templates["spec.md"] + references,
        "plan.md": templates["plan.md"] + references,
        "tasks.md": templates["tasks.md"] + references + (
            "\n\nCSEF acceptance requires controller-captured checks for applicable tasks.\n"
            "Checkboxes, workflow verdicts and model reports are proposals, never Gate evidence.\n"
        ),
    }
    data = {name: text.encode("utf-8") for name, text in documents.items()}
    data["csef.json"] = encoded(envelope)
    if any(len(value) > 256_000 for value in data.values()):
        raise Refused("exchange document exceeds size limit")
    destination.mkdir(parents=True)
    # Envelope last: an interrupted partial export fails import, not acceptance.
    for name, content in data.items():
        (destination / name).write_bytes(content)
    return envelope


def read_bundle(directory: Path) -> dict:
    """Read only the fixed document set; all Markdown remains inert task data."""
    directory = Path(directory).absolute()
    plain(directory)
    envelope = parse_json(file_bytes(directory, "csef.json").decode("utf-8"))
    if (not isinstance(envelope, dict)
            or set(envelope) != {"format", "upstream_commit", "origin", "project"}
            or envelope["format"] != "csef-spec-kit-v1"
            or envelope["upstream_commit"] != UPSTREAM_COMMIT):
        raise Refused("unsupported exchange envelope")
    documents = {name: file_bytes(directory, name).decode("utf-8") for name in DOCUMENTS}
    if any(not text.strip() for text in documents.values()):
        raise Refused("empty exchange document")
    return {**envelope, "documents": documents}


def import_proposal(book: ProjectBook, directory: Path) -> dict:
    """Persist a draft once per exact input, including across process restarts.

    A transaction checks the CURRENT owner revision and deduplicates the full
    proposal, so replay after a lost native workflow checkpoint has no second
    write. Proposals cannot amend owner facts or advance a stage. Other external
    effects are outside this spike; unknown outcomes must not be blindly retried.
    """
    bundle = read_bundle(directory)
    proposal = {"type": "spec_kit_documents", "bundle": bundle}
    body = encoded(proposal).decode("utf-8")
    with book.connection() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM revisions ORDER BY version DESC LIMIT 1").fetchone()
        current = parse_json(row["body"])
        if digest(encoded(current)) != row["sha256"]:
            raise Refused("project revision integrity mismatch")
        expected = {"version": row["version"], "sha256": row["sha256"], **current}
        if bundle["origin"] != _origin(book) or encoded(bundle["project"]) != encoded(expected):
            raise Refused("foreign, changed or stale owner revision; export again after an explicit owner amendment")
        existing = con.execute("SELECT id FROM changes WHERE proposal=?", (body,)).fetchone()
        if existing:
            key, replayed = existing["id"], True
        else:
            from ..core import now
            key = con.execute("INSERT INTO changes(proposal,status,created) VALUES(?,?,?)",
                              (body, "proposed", now())).lastrowid
            replayed = False
    return {"proposal_id": key, "replayed": replayed, "status": "proposed",
            "bundle_sha256": digest(encoded(bundle)), "release_approved": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("export", "import"))
    parser.add_argument("--book", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--templates", type=Path, help="Explicitly selected directory containing the three templates")
    args = parser.parse_args(argv)
    try:
        book = ProjectBook(args.book)
        if args.operation == "export":
            if args.templates is None:
                parser.error("export requires --templates")
            templates = {doc: file_bytes(args.templates.absolute(), name).decode("utf-8")
                         for doc, name in TEMPLATES.items()}
            result = export_bundle(book, args.bundle, templates)
        else:
            result = import_proposal(book, args.bundle)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (Refused, ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc), "release_approved": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
