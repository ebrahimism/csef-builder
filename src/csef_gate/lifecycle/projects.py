"""Explicit owner statements and proposed facts, backed by existing ProjectBook.

Only the trusted conversation/controller calls record_owner_statement. The
model-facing proposal path always stores status=proposed. Labels in model JSON
cannot create the separate owner_recorded row status. This is not OS isolation.
"""
from __future__ import annotations
import re

from ..core import Refused, digest, encoded, now, parse_json
from ..contracts import OwnerFact, ProjectRevision, checked
from ..persistence.sqlite import DATABASE


def text_value(value):
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > 100_000:
        raise Refused("nonempty bounded source text required")
    return value


def owner_version(value):
    if type(value) is not int or value < 1:
        raise Refused("explicit positive integer owner revision required")


class ProjectService:
    def __init__(self, book):
        self.book = book
        if book.db.name != DATABASE:
            raise Refused("migrate legacy data before using provenance services")

    def _current(self, con, expected_version=None):
        row = con.execute("SELECT * FROM revisions ORDER BY version DESC LIMIT 1").fetchone()
        body = parse_json(row["body"])
        if not isinstance(body, dict) or set(body) != {"goal", "answers", "facts"} or digest(encoded(body)) != row["sha256"]:
            raise Refused("project revision integrity mismatch")
        checked(ProjectRevision, {"version": row["version"], "sha256": row["sha256"], **body})
        if expected_version is not None and (type(expected_version) is not int or expected_version != row["version"]):
            raise Refused("stale owner revision")
        return {"version": row["version"], "sha256": row["sha256"], **body}

    @staticmethod
    def _change_spec(change):
        if not isinstance(change, dict) or set(change) - {"replacements", "additions", "goal", "answers"}:
            raise Refused("unsupported explicit owner change")
        result = {"replacements": {} if change.get("replacements") is None else change["replacements"],
                  "additions": [] if change.get("additions") is None else change["additions"], "goal": change.get("goal")}
        if not isinstance(result["replacements"], dict) or not isinstance(result["additions"], list):
            raise Refused("invalid owner change fields")
        if change.get("answers") is not None:
            if not isinstance(change["answers"], dict):
                raise Refused("invalid owner answer fields")
            # Preserve existing v1 hashes for non-answer owner statements.
            if change["answers"]:
                result["answers"] = change["answers"]
        return result

    def record_owner_statement(self, text, *, expected_version, approves=None, change=None):
        owner_version(expected_version)
        text_value(text)
        if approves is not None and (type(approves) is not int or approves < 1):
            raise Refused("invalid proposal reference")
        if approves is not None and change is not None:
            raise Refused("bind either a proposal or a direct change")
        with self.book.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            current = self._current(con, expected_version)
            target_sha = digest(encoded(self._change_spec(change))) if change is not None else None
            if approves is not None:
                proposal = con.execute("SELECT proposal FROM changes WHERE id=? AND status='proposed'", (approves,)).fetchone()
                if proposal is None:
                    raise Refused("proposal is not pending")
                target_sha = digest(proposal[0].encode())
            body = {"type": "owner_statement", "schema_version": 1, "text": text,
                    "base_version": current["version"], "base_sha256": current["sha256"], "approves": approves,
                    "target_sha256": target_sha}
            return con.execute("INSERT INTO changes(proposal,status,created) VALUES(?,'owner_recorded',?)",
                               (encoded(body).decode(), now())).lastrowid

    def propose(self, text, *, kind, source_ref, fact_id=None):
        text_value(text); text_value(source_ref)
        prefixes = {"requirement": "REQ", "constraint": "CON", "decision": "ADR", "assumption": "ASM"}
        if kind not in prefixes:
            raise Refused("unsupported proposal kind")
        with self.book.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            current = self._current(con)
            if fact_id is None:
                prefix = prefixes[kind]
                ids = [f["id"] for f in current["facts"]]
                for row in con.execute("SELECT proposal FROM changes"):
                    data = parse_json(row[0])
                    if isinstance(data, dict) and isinstance(data.get("fact_id"), str):
                        ids.append(data["fact_id"])
                numbers = [int(value.split("-")[1]) for value in ids if re.fullmatch(prefix + r"-[0-9]{3}", value)]
                number = max(numbers, default=0) + 1
                if number > 999:
                    raise Refused("fact ID range exhausted")
                fact_id = f"{prefix}-{number:03d}"
            checked(OwnerFact, {"id": fact_id, "text": text, "kind": "constraint" if kind == "assumption" else kind})
            known = next((f for f in current["facts"] if f["id"] == fact_id), None)
            if known and known["kind"] != kind:
                raise Refused("a proposal cannot silently change an accepted fact kind")
            body = {"type": "fact_proposal", "schema_version": 1, "fact_id": fact_id, "kind": kind,
                    "text": text, "source": "assumption" if kind == "assumption" else "model_proposal",
                    "source_ref": source_ref, "base_version": current["version"], "base_sha256": current["sha256"]}
            return con.execute("INSERT INTO changes(proposal,status,created) VALUES(?,'proposed',?)",
                               (encoded(body).decode(), now())).lastrowid

    def _statement(self, con, statement_id, current, proposal_id, target_sha):
        if type(statement_id) is not int:
            raise Refused("owner statement reference required")
        row = con.execute("SELECT * FROM changes WHERE id=? AND status='owner_recorded'", (statement_id,)).fetchone()
        item = parse_json(row["proposal"]) if row else {}
        if (not isinstance(item, dict) or set(item) != {"type", "schema_version", "text", "base_version", "base_sha256", "approves", "target_sha256"}
                or item["type"] != "owner_statement" or type(item["schema_version"]) is not int or item["schema_version"] != 1
                or type(item["base_version"]) is not int
                or item["base_version"] != current["version"] or item["base_sha256"] != current["sha256"]
                or item["approves"] != proposal_id or item["target_sha256"] != target_sha):
            raise Refused("no current, unconsumed owner statement for this change")
        text_value(item["text"])
        return item

    def apply_owner_change(self, statement_id, *, expected_version, replacements=None, additions=None, goal=None, answers=None):
        owner_version(expected_version)
        if not replacements and not additions and goal is None and not answers:
            raise Refused("explicit owner change required")
        with self.book.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            current = self._current(con, expected_version)
            change = self._change_spec({"replacements": replacements, "additions": additions, "goal": goal, "answers": answers})
            statement = self._statement(con, statement_id, current, None, digest(encoded(change)))
            result = self.book._amend_in(con, replace_facts=replacements, add_facts=additions, goal=goal, answers=answers,
                        reason=statement["text"], source={"kind": "owner_statement", "ref": statement_id})
            con.execute("UPDATE changes SET status='owner_consumed' WHERE id=?", (statement_id,))
            return result

    def accept_proposal(self, proposal_id, statement_id, *, expected_version):
        owner_version(expected_version)
        if type(proposal_id) is not int:
            raise Refused("proposal reference required")
        with self.book.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            current = self._current(con, expected_version)
            row = con.execute("SELECT * FROM changes WHERE id=? AND status='proposed'", (proposal_id,)).fetchone()
            statement = self._statement(con, statement_id, current, proposal_id, digest(row["proposal"].encode()) if row else None)
            item = parse_json(row["proposal"]) if row else {}
            if (not isinstance(item, dict) or set(item) != {"type", "schema_version", "fact_id", "kind", "text", "source", "source_ref", "base_version", "base_sha256"}
                    or item["type"] != "fact_proposal" or type(item["schema_version"]) is not int or item["schema_version"] != 1
                    or type(item["base_version"]) is not int
                    or item["kind"] == "assumption" or item["source"] != "model_proposal"
                    or item["base_version"] != current["version"] or item["base_sha256"] != current["sha256"]):
                raise Refused("no current admissible fact proposal")
            text_value(item["text"]); text_value(item["source_ref"])
            fact = checked(OwnerFact, {"id": item["fact_id"], "kind": item["kind"], "text": item["text"]}).model_dump()
            known = next((f for f in current["facts"] if f["id"] == fact["id"]), None)
            if known and known["kind"] != fact["kind"]:
                raise Refused("accepted fact kind is immutable")
            result = self.book._amend_in(con, replace_facts={fact["id"]: fact["text"]} if known else None,
                    add_facts=None if known else [fact], reason=statement["text"],
                    source={"kind": "owner_accepted_proposal", "ref": statement_id, "proposal_id": proposal_id})
            con.execute("UPDATE changes SET status='accepted' WHERE id=?", (proposal_id,))
            con.execute("UPDATE changes SET status='owner_consumed' WHERE id=?", (statement_id,))
            return result

    def _timeline(self, con=None):
        if con is None:
            with self.book.connection() as snapshot:
                snapshot.execute("BEGIN")
                return self._timeline(con=snapshot)
        revisions = [dict(row) for row in con.execute("SELECT * FROM revisions ORDER BY version")]
        records = [parse_json(r[0]) for r in con.execute("SELECT proposal FROM changes WHERE status='recorded'")]
        references = {r["id"]: dict(r) for r in con.execute("SELECT id,proposal,status FROM changes WHERE status IN ('owner_consumed','accepted')")}
        by_version = {}
        for revision in revisions:
            body = parse_json(revision["body"])
            if not isinstance(body, dict) or set(body) != {"goal", "answers", "facts"} or digest(encoded(body)) != revision["sha256"]:
                raise Refused("historical owner revision integrity mismatch")
            checked(ProjectRevision, {"version": revision["version"], "sha256": revision["sha256"], **body})
            revision["parsed_body"] = body
            by_version[revision["version"]] = revision
        audits = {}
        for item in records:
            if not isinstance(item, dict) or item.get("type") != "owner_revision":
                continue
            if (type(item.get("schema_version")) is not int or item["schema_version"] != 1
                    or type(item.get("from_version")) is not int or type(item.get("to_version")) is not int
                    or item["to_version"] != item["from_version"] + 1 or item["to_version"] in audits):
                raise Refused("invalid owner provenance chain")
            old, new = by_version.get(item["from_version"]), by_version.get(item["to_version"])
            if not old or not new or item.get("before_sha256") != old["sha256"] or item.get("after_sha256") != new["sha256"]:
                raise Refused("owner provenance does not bind the recorded revisions")
            before = {f["id"]: f for f in old["parsed_body"]["facts"]}
            delta = [{"id": f["id"], "before": before.get(f["id"]), "after": f}
                     for f in new["parsed_body"]["facts"] if before.get(f["id"]) != f]
            if (item.get("fact_changes") != delta or not isinstance(item.get("source"), dict)
                    or item["source"].get("kind") not in ("owner_controller", "owner_statement", "owner_accepted_proposal")
                    or not isinstance(item.get("stale_stages"), list)):
                raise Refused("invalid owner change provenance")
            answer_delta = {k: {"before": old["parsed_body"]["answers"].get(k), "after": value}
                            for k, value in new["parsed_body"]["answers"].items()
                            if old["parsed_body"]["answers"].get(k) != value}
            goal_changed = old["parsed_body"]["goal"] != new["parsed_body"]["goal"]
            if type(item.get("goal_changed")) is not bool or item["goal_changed"] != goal_changed or item.get("answer_changes") != answer_delta:
                raise Refused("owner change effects do not match stored revisions")
            source = item["source"]
            if source["kind"] == "owner_controller":
                if source.get("ref") is not None:
                    raise Refused("invalid controller source reference")
            else:
                ref = source.get("ref")
                referenced = references.get(ref) if type(ref) is int and ref > 0 else None
                statement = parse_json(referenced["proposal"]) if referenced else {}
                if (not referenced or referenced["status"] != "owner_consumed" or not isinstance(statement, dict)
                        or statement.get("type") != "owner_statement" or statement.get("base_version") != old["version"]
                        or statement.get("base_sha256") != old["sha256"]):
                    raise Refused("owner source reference is missing or stale")
                if source["kind"] == "owner_accepted_proposal":
                    proposal_id = source.get("proposal_id")
                    proposal = references.get(proposal_id) if type(proposal_id) is int and proposal_id > 0 else None
                    if (not proposal or proposal["status"] != "accepted" or statement.get("approves") != proposal_id
                            or statement.get("target_sha256") != digest(proposal["proposal"].encode())):
                        raise Refused("accepted proposal provenance no longer matches its source")
                elif statement.get("approves") is not None:
                    raise Refused("direct owner change has an unrelated proposal reference")
            audits[item["to_version"]] = item
        return revisions, audits

    def revision_history(self):
        """Expose source and conservative impacts without asking the UI to read SQL."""
        revisions, audits = self._timeline()
        return [{"version": r["version"], "sha256": r["sha256"],
                 "provenance": audits.get(r["version"], {"source": {"kind": "legacy_unattributed", "ref": None}})}
                for r in revisions]

    def history(self, fact_id):
        revisions, audits = self._timeline()
        result, previous = [], None
        for revision in revisions:
            fact = next((f for f in revision["parsed_body"]["facts"] if f["id"] == fact_id), None)
            if fact != previous and fact is not None:
                audit = audits.get(revision["version"])
                result.append({"version": revision["version"], "fact": fact,
                               "source": audit["source"] if audit else {"kind": "legacy_unattributed", "ref": None},
                               "stale_stages": audit["stale_stages"] if audit else [],
                               "status": "superseded"})
                previous = fact
        if result:
            result[-1]["status"] = "accepted"
        return result
