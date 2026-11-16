"""Stable questions, linked answer revisions and mechanical duplicate suppression."""
from __future__ import annotations

import re

from ..core import Refused, digest, encoded, now, parse_json
from ..project import QUESTIONS
from .projects import ProjectService, owner_version, text_value


def context_sha(project, fact_ids):
    if not isinstance(fact_ids, list) or any(not isinstance(x, str) for x in fact_ids) or len(set(fact_ids)) != len(fact_ids):
        raise Refused("question fact references must be unique IDs")
    facts = {f["id"]: f for f in project["facts"]}
    if not set(fact_ids) <= facts.keys():
        raise Refused("question refers to an unknown requirement or decision")
    intake = {key: project["answers"].get(key) for key in QUESTIONS}
    intake = {key: value.get("answer") if isinstance(value, dict) else value for key, value in intake.items()}
    value = {"goal": project["goal"], "intake": intake, "facts": [facts[key] for key in sorted(fact_ids)]}
    return digest(encoded(value))


def question_number(question_id):
    if not isinstance(question_id, str) or not re.fullmatch(r"Q-[1-9][0-9]{0,18}", question_id):
        raise Refused("unknown question ID")
    return int(question_id[2:])


def normalized(text):
    return " ".join(text_value(text).split()).casefold()


class Questions(ProjectService):
    def ask(self, question, *, why_needed, decision_affected, stage, source_ref, expected_version, fact_ids=None, key=None):
        owner_version(expected_version)
        for value in (question, why_needed, decision_affected, source_ref):
            text_value(value)
        related = [] if fact_ids is None else fact_ids
        prompt = normalized(question)
        if key is None:
            key = digest(prompt.encode())
        elif not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", key):
            raise Refused("invalid stable question key")
        with self.book.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            current = self._current(con, expected_version)
            signature = context_sha(current, related)
            if not con.execute("SELECT 1 FROM stages WHERE name=?", (stage,)).fetchone():
                raise Refused("unknown question stage")
            for row in con.execute("SELECT * FROM changes WHERE status IN ('proposed','answered') ORDER BY id"):
                item = parse_json(row["proposal"])
                if not isinstance(item, dict) or item.get("type") != "owner_question" or item.get("stage") != stage:
                    continue
                item_key = item.get("question_key", digest(normalized(item["question"]).encode()))
                if item_key != key or sorted(item.get("fact_ids", [])) != sorted(related):
                    continue
                if normalized(item["question"]) != prompt:
                    raise Refused("question key was reused for a different prompt")
                qid = f'Q-{row["id"]}'
                if self.is_current(qid, current, con=con, question=item):
                    return {"id": qid, "status": row["status"], "reused": True}
            body = {"type": "owner_question", "schema_version": 1, "question": question, "why_needed": why_needed,
                    "decision_affected": decision_affected, "stage": stage, "fact_ids": sorted(related),
                    "question_key": key, "context_sha256": signature, "source_ref": source_ref,
                    "base_version": current["version"], "base_sha256": current["sha256"]}
            row = con.execute("INSERT INTO changes(proposal,status,created) VALUES(?,'proposed',?)", (encoded(body).decode(), now()))
            return {"id": f"Q-{row.lastrowid}", "status": "proposed", "reused": False}

    def _question(self, con, question_id):
        if not isinstance(question_id, str):
            raise Refused("unknown question ID")
        if question_id in QUESTIONS:
            return {"question": QUESTIONS[question_id], "fact_ids": [], "stage": "discovery"}
        row = con.execute("SELECT proposal FROM changes WHERE id=? AND status IN ('proposed','answered')", (question_number(question_id),)).fetchone()
        data = parse_json(row[0]) if row else {}
        if not isinstance(data, dict) or data.get("type") != "owner_question":
            raise Refused("unknown question")
        return data

    def answer(self, question_id, text, *, expected_version, fact_updates=None):
        owner_version(expected_version); text_value(text)
        with self.book.connection() as con:
            con.execute("BEGIN")
            current = self._current(con, expected_version)
            question = self._question(con, question_id)
            related = question.get("fact_ids", [])
            if not self.is_current(question_id, current, con=con, question=question):
                raise Refused("question context is stale; refresh the question before answering")
            if fact_updates is not None and (not isinstance(fact_updates, dict) or not set(fact_updates) <= set(related)):
                raise Refused("answer may update only its explicitly linked facts")
        changes = {"answers": {question_id: text}, "replacements": fact_updates}
        statement = self.record_owner_statement(text, expected_version=expected_version, change=changes)
        return self.apply_owner_change(statement, expected_version=expected_version, answers={question_id: text}, replacements=fact_updates)

    def is_current(self, question_id, project, *, con, question=None):
        if question_id in QUESTIONS:
            return True
        question = self._question(con, question_id) if question is None else question
        history = self.answer_history(question_id, con=con)
        anchor = history[-1]["context_sha256"] if history else question.get("context_sha256")
        return anchor == context_sha(project, question.get("fact_ids", []))

    def answer_history(self, question_id, *, con=None):
        if con is None:
            with self.book.connection() as snapshot:
                snapshot.execute("BEGIN")
                return self.answer_history(question_id, con=snapshot)
        revisions, audits = self._timeline(con=con)
        question = self._question(con, question_id)
        observations = [parse_json(r[0]) for r in con.execute("SELECT proposal FROM changes WHERE status='recorded' ORDER BY id")]
        by_version = {r["version"]: r for r in revisions}
        related = question.get("fact_ids", [])
        result, seen = [], set()
        for item in observations:
            if not isinstance(item, dict) or item.get("type") != "answer_revision" or item.get("question_id") != question_id:
                continue
            revision = by_version.get(item.get("project_version"))
            audit = audits.get(item.get("project_version"))
            if (not revision or not audit or type(item.get("schema_version")) is not int or item["schema_version"] != 1
                    or type(item.get("project_version")) is not int
                    or item["project_version"] in seen
                    or item.get("project_sha256") != revision["sha256"] or item.get("fact_ids") != related
                    or item.get("value") != revision["parsed_body"]["answers"].get(question_id)
                    or item.get("context_sha256") != context_sha(revision["parsed_body"], related)
                    or item.get("source") != audit["source"]):
                raise Refused("answer history integrity mismatch")
            seen.add(item["project_version"])
            result.append({"version": item["project_version"], "value": item["value"], "fact_ids": related,
                           "context_sha256": item["context_sha256"], "source": item["source"]})
        # Older stores did not have answer observation records. Recover the
        # actual stored changes without inventing a source or rewriting them.
        covered = {r["version"] for r in result}
        previous = None
        for revision in revisions:
            value = revision["parsed_body"]["answers"].get(question_id)
            if value is not None and value != previous and revision["version"] not in covered:
                result.append({"version": revision["version"], "value": value, "fact_ids": related,
                               "context_sha256": context_sha(revision["parsed_body"], related),
                               "source": audits.get(revision["version"], {}).get("source", {"kind": "legacy_unattributed", "ref": None})})
            previous = value
        result.sort(key=lambda row: row["version"])
        for index, item in enumerate(result):
            item["status"] = "accepted" if index == len(result) - 1 else "superseded"
        return result
