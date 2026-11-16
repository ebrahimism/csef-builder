"""Verified snapshot bytes and final transaction-bound handoff validation."""
from pathlib import Path

from ..core import Refused, digest, encoded, file_bytes


def source_digest(sources):
    return digest(encoded({name: digest(data) for name, data in sources.items()}))


def verified_bundle(gate, run_id):
    with gate.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        ev, report, spec = gate._verified_in(con, run_id)
        sources = {name: file_bytes(Path(ev["snapshot"]), name) for name in spec["source_files"]}
        if source_digest(sources) != ev["source_hash"]:
            raise Refused("verification snapshot changed while reading")
        return sources, report, ev["report_hash"]


def finalize_validator(gate, run_id, sources, report, report_hash):
    # Only the controller creates this closure. Neither a model report nor a
    # caller-created JSON permit replaces the fresh DB resolution below.
    expected_source = source_digest(sources)
    def validate(con):
        ev, current, spec = gate._verified_in(con, run_id)
        if (ev["id"] != report["evaluation_id"] or ev["report_hash"] != report_hash
                or expected_source != ev["source_hash"] or current != report
                or set(sources) != set(spec["source_files"])):
            raise Refused("handoff no longer matches its verified evaluation")
    return validate


def prior_sources(book, packet, names):
    for handoff in reversed(packet["handoffs"]):
        if not any(check.get("id") == "INDEPENDENT_GATE" and check.get("passed") is True for check in handoff["checks"]):
            continue  # A model document named verification.json is not a code handoff.
        entries = {item["path"].split("/", 3)[-1]: item for item in handoff["artifacts"]}
        if "verification.json" not in entries:
            continue
        result = {}
        for name in names:
            item = entries.get("source/" + name)
            if item is None:
                raise Refused("previous code handoff is incomplete")
            data = file_bytes(book.root, item["path"])
            if digest(data) != item["sha256"]:
                raise Refused("previous code artifact changed")
            result[name] = data
        return result
    return None
