"""One bounded workflow for intake, document roles, coding and verified handoff.

This prototype uses one frozen executable oracle. It does not authorize release.
Providers are injected by the trusted controller, never selected by model JSON.
"""
from ..assistant import assist_stage
from ..core import Gate, Refused, digest, encoded, now, parse_json
from ..lifecycle.questions import Questions
from ..project import ProjectBook
from ..review import review_proposal, route_review
from .handoffs import finalize_validator, prior_sources, verified_bundle
from .stages import document_artifacts, next_stage, pipeline


class Workflow:
    def __init__(self, root):
        self.book = ProjectBook(root)
        pipeline(self.book)

    @classmethod
    def create(cls, root, goal, *, answers=None, facts=None, stages=None):
        if stages is not None and not 6 <= len(stages) <= 24:
            raise Refused("workflow requires six to twenty-four stages")
        ProjectBook.create(root, goal, answers, facts, stages)
        return cls(root)

    def answer(self, question_id, text, *, expected_version, fact_updates=None):
        return Questions(self.book).answer(question_id, text, expected_version=expected_version, fact_updates=fact_updates)

    def attach_code(self, project, specification):
        Gate.initialize(self.book.root, project, specification, attach=True)
        return self.status()

    def status(self):
        result = self.book.status()
        stage = next_stage(self.book)
        result.update(status="awaiting_owner" if result["questions"] else "complete" if stage is None else "ready",
                      next_stage=stage["name"] if stage else None, release_approved=False)
        return result

    def step(self, *, client=None, agent=None, executor=None, reviewer=None, measure_only=False):
        pending = self.book.questions()
        if pending:
            return {"status": "awaiting_owner", "questions": pending, "model_called": False, "release_approved": False}
        stage = next_stage(self.book)
        if stage is None:
            return {"status": "complete", "release_approved": False}
        if stage["position"] < 3:
            return self._document(stage, client, reviewer)
        if agent is None or executor is None:
            raise Refused("coding agent and execution provider are required")
        return self._code(stage, agent, executor, measure_only)

    def _document(self, stage, client, reviewer):
        name = stage["name"]
        # Positions also cover renamed architecture/contract stages.
        needs_review = stage["position"] in (1, 2) or route_review(name)["call_model"]
        if needs_review and reviewer is None:
            return {"status": "review_required", "stage": name, "model_called": False, "release_approved": False}
        if client is None:
            raise Refused("document model provider is required")
        before = self.book.current()
        result = assist_stage(self.book, name, client, instruction="Produce nonempty stage documents in drafts. Reference every accepted fact ID and explain compliance or an unresolved issue. Cover this role's problem, architecture or executable contract as appropriate; a list of IDs alone is insufficient. Report missing owner decisions as questions. Proposed decisions remain proposals.")
        if result["status"] != "draft_requires_validation":
            return result
        packet = self.book.begin(name)
        packet_hash = digest(encoded(packet))
        if (before["version"], before["sha256"]) != (packet["project"]["version"], packet["project"]["sha256"]):
            self.book.suspend(name, packet_hash=packet_hash)
            raise Refused("document was generated for an older owner revision")
        draft = result["draft"]
        artifacts, checks = document_artifacts(draft, packet["project"])
        if not artifacts:
            self.book.suspend(name, packet_hash=packet_hash)
            return {"status": "needs_revision", "stage": name, "checks": checks, "release_approved": False}
        review = None
        if needs_review and all(c["passed"] for c in checks):
            review = review_proposal(self.book, name, draft, reviewer)["review"]
            if review["verdict"] == "needs_owner":
                questions = review.get("owner_questions")
                if not isinstance(questions, list) or not 1 <= len(questions) <= 3:
                    self.book.suspend(name, packet_hash=packet_hash)
                    return {"status": "needs_revision", "stage": name, "review": review, "release_approved": False}
                for text in questions:
                    Questions(self.book).ask(text, why_needed="review found an owner decision needed",
                        decision_affected=name, stage=name, source_ref="stage_review:" + packet["execution_id"],
                        expected_version=packet["project"]["version"], fact_ids=[f["id"] for f in packet["project"]["facts"]])
                pending = self.book.questions()
                self.book.suspend(name, packet_hash=packet_hash, awaiting_owner=bool(pending))
                return {"status": "awaiting_owner" if pending else "needs_revision", "stage": name,
                        "questions": pending, "review": review, "release_approved": False}
        handoff = self.book.finish(name, packet_hash=packet_hash, artifacts=artifacts, checks=checks, reviewer=review)
        passed = all(c["passed"] for c in checks) and (review is None or review["verdict"] == "ok")
        return {"status": "ready_for_next" if passed else "needs_revision", "stage": name, "handoff": handoff, "release_approved": False}

    def _run_for(self, gate, packet):
        with self.book.connection() as con:
            rows = con.execute("SELECT proposal FROM changes WHERE status='recorded' ORDER BY id DESC").fetchall()
        for row in rows:
            data = parse_json(row[0])
            if (isinstance(data, dict) and data.get("type") == "workflow_run" and data.get("stage") == packet["stage"]
                    and data.get("owner_version") == packet["project"]["version"] and data.get("owner_sha256") == packet["project"]["sha256"]):
                gate.candidate(data["run_id"])
                return data["run_id"]
        run_id = gate.prepare()
        spec, _ = gate.spec()
        previous = prior_sources(self.book, packet, spec["source_files"])
        if previous is not None:
            gate.apply_proposal(run_id, {"summary": "Carry forward the exact verified previous snapshot",
                "files": [{"path": name, "content": data.decode()} for name, data in previous.items() if name in spec["editable_files"]]})
        with self.book.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            from ..persistence.leases import assert_current
            assert_current(con, self.book._stage_leases[packet["stage"]])
            data = {"type": "workflow_run", "stage": packet["stage"], "run_id": run_id,
                    "owner_version": packet["project"]["version"], "owner_sha256": packet["project"]["sha256"]}
            con.execute("INSERT INTO changes(proposal,status,created) VALUES(?,'recorded',?)", (encoded(data).decode(), now()))
        return run_id

    def _code(self, stage, agent, executor, measure_only):
        gate = Gate(self.book.root)
        gate.spec()  # Missing/altered oracle is refused before acquiring a lease.
        packet = self.book.begin(stage["name"], lease_ttl=3600)
        packet_hash = digest(encoded(packet))
        run_id = self._run_for(gate, packet)
        spec, _ = gate.spec()
        while True:
            report = gate.evaluate(run_id, executor, measure_only=measure_only)
            if report["status"] != "fail":
                break
            with gate.connect() as con:
                attempts = con.execute("SELECT attempts FROM runs WHERE id=?", (run_id,)).fetchone()[0]
            if attempts >= spec["max_attempts"]:
                break
            call_id = self.book.reserve_call("developer:" + stage["name"])
            try:
                receipt = gate.agent_attempt(run_id, agent, {"project_context": self.book.context(stage["name"]), "verification": report})
                self.book.complete_call(call_id, receipt)
            except Exception:
                self.book.complete_call(call_id, {"exit_code": -1, "outcome": "failed_or_unknown"})
                raise  # An unknown worker retains the lease for explicit recovery.
        if report["status"] == "pass":
            sources, report, report_hash = verified_bundle(gate, run_id)
            artifacts = {"source/" + name: data for name, data in sources.items()}
            artifacts["verification.json"] = encoded(report)
            artifacts["delivery.txt"] = ("Run Python " + spec["entrypoint"] + " with the documented arguments.\n"
                "One frozen oracle; no release checkpoint or deployment.\n").encode()
            validate = finalize_validator(gate, run_id, sources, report, report_hash)
        else:
            artifacts, validate = {"verification.json": encoded(report)}, None
        checks = [{"id": "INDEPENDENT_GATE", "passed": report["status"] == "pass", "basis": "Gate evaluation " + report["evaluation_id"] + "; REVIEW never advances dependent stages."}]
        handoff = self.book.finish(stage["name"], packet_hash=packet_hash, artifacts=artifacts, checks=checks, _validate=validate)
        return {"status": "ready_for_next" if report["status"] == "pass" else report["status"], "stage": stage["name"],
                "run_id": run_id, "report": report, "handoff": handoff, "release_approved": False}

    def run(self, *, max_steps=24, **providers):
        if type(max_steps) is not int or not 1 <= max_steps <= 24:
            raise Refused("invalid workflow step budget")
        results = []
        for _ in range(max_steps):
            result = self.step(**providers)
            results.append(result)
            if result["status"] != "ready_for_next":
                return {**result, "steps": results}
        return {"status": "complete" if next_stage(self.book) is None else "paused", "steps": results, "release_approved": False}
