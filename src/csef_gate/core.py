"""Trusted control plane. Never imports or executes candidate code in this process."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


class Refused(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def parse_json(text: str):
    def bad_constant(value):
        raise Refused(f"nonfinite JSON value: {value}")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Refused(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(text, parse_constant=bad_constant, object_pairs_hook=unique)


def read_json(path: Path):
    return parse_json(path.read_text(encoding="utf-8"))


def relative_name(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value:
        raise Refused("expected a portable relative file path")
    parts = value.split("/")
    if any(p in ("", ".", "..") or p.endswith((" ", ".")) for p in parts):
        raise Refused("noncanonical file path")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if any(p.split(".")[0].upper() in reserved or p.startswith(".") for p in parts):
        raise Refused("reserved file path")
    if any(re.search(r'[<>"|?*\x00-\x1f]', p) for p in parts):
        raise Refused("invalid path character")
    if PurePosixPath(value).is_absolute():
        raise Refused("absolute path")
    return value


def plain(path: Path):
    """Reject symlinks and Windows junctions/reparse points, including parents."""
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            s = part.lstat()
            if stat.S_ISLNK(s.st_mode) or getattr(s, "st_file_attributes", 0) & 0x400:
                raise Refused(f"reparse point is not allowed: {part}")


def file_bytes(root: Path, name: str) -> bytes:
    path = root / relative_name(name)
    plain(path)
    if not path.is_file():
        raise Refused(f"missing source file: {name}")
    data = path.read_bytes()
    if len(data) > 256_000:
        raise Refused(f"file too large: {name}")
    return data


def manifest(root: Path, names: list[str]) -> tuple[str, dict]:
    values = {name: digest(file_bytes(root, name)) for name in sorted(names)}
    return digest(encoded(values)), values


def validate_spec(spec: dict):
    required = {"version", "objective", "source_files", "editable_files", "entrypoint", "cases", "max_attempts", "agent_timeout_s", "case_timeout_s"}
    if not isinstance(spec, dict) or set(spec) != required or type(spec["version"]) is not int or spec["version"] != 1:
        raise Refused("unsupported or incomplete specification")
    if not isinstance(spec["objective"], str) or not spec["objective"].strip():
        raise Refused("objective required")
    for key in ("source_files", "editable_files"):
        names = spec[key]
        if not isinstance(names, list) or not 1 <= len(names) <= 40:
            raise Refused(f"invalid {key}")
        for name in names:
            relative_name(name)
        if len({n.casefold() for n in names}) != len(names):
            raise Refused("duplicate/case-colliding file names")
    if not set(spec["editable_files"]) <= set(spec["source_files"]):
        raise Refused("editable files must be in the frozen source inventory")
    if spec["entrypoint"] not in spec["source_files"] or not spec["entrypoint"].endswith(".py"):
        raise Refused("v1 requires an inventoried Python CLI entrypoint")
    for key, low, high in (("max_attempts", 1, 5), ("agent_timeout_s", 10, 600), ("case_timeout_s", 1, 60)):
        if type(spec[key]) is not int or not low <= spec[key] <= high:
            raise Refused(f"invalid {key}")
    cases = spec["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= 100:
        raise Refused("a nonempty acceptance suite is mandatory")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"id", "args", "exit_code", "stdout_json"}:
            raise Refused("unsupported acceptance criterion; never skipped")
        if not isinstance(case["id"], str) or not re.fullmatch(r"[A-Z][A-Z0-9_-]{0,63}", case["id"]) or case["id"] in ids:
            raise Refused("invalid or duplicate criterion id")
        ids.add(case["id"])
        if not isinstance(case["args"], list) or not all(isinstance(x, str) and len(x) <= 4096 and "\x00" not in x for x in case["args"]):
            raise Refused("argv must contain bounded literal strings")
        if type(case["exit_code"]) is not int or not 0 <= case["exit_code"] <= 255:
            raise Refused("invalid expected exit code")
    encoded(spec)


def same_json(actual, expected) -> bool:
    """Do not treat true as 1 or numeric strings as numbers."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(same_json(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(same_json(a, b) for a, b in zip(actual, expected))
    return actual == expected


def owner_revision(con):
    """A shared store binds verification to the exact owner revision."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='revisions'").fetchone():
        return None, None
    row = con.execute("SELECT * FROM revisions ORDER BY version DESC LIMIT 1").fetchone()
    if row is None:
        return None, None
    body = parse_json(row["body"])
    if not isinstance(body, dict) or set(body) != {"goal", "answers", "facts"} or digest(encoded(body)) != row["sha256"]:
        raise Refused("owner revision integrity mismatch")
    from .contracts import ProjectRevision, checked
    checked(ProjectRevision, {"version": row["version"], "sha256": row["sha256"], **body})
    return row["version"], row["sha256"]


class Gate:
    def __init__(self, control: Path):
        self.root = control.absolute()
        plain(self.root)
        from .persistence.sqlite import database_for
        self.db = database_for(self.root, "gate")

    @classmethod
    def initialize(cls, control: Path, project: Path, spec_path: Path, *, attach=False):
        control, project = control.absolute(), project.absolute()
        plain(control)
        plain(project)
        control, project = control.resolve(), project.resolve()
        plain(control)
        plain(project)
        if control == project or control in project.parents or project in control.parents:
            raise Refused("control store and project must be disjoint trees")
        if control.exists() and not attach:
            raise Refused("control directory must be new")
        from .persistence.sqlite import DATABASE, connection, database_for, initialize
        if attach:
            db = database_for(control, "project")
            if db.name != DATABASE:
                raise Refused("attach requires a versioned unified store")
        raw = spec_path.read_bytes()
        if len(raw) > 512_000:
            raise Refused("specification too large")
        spec = read_json(spec_path)
        validate_spec(spec)
        source_hash, files = manifest(project, spec["source_files"])
        control.mkdir(parents=True, exist_ok=attach)
        if not attach:
            initialize(control / DATABASE)
        with connection(control / DATABASE) as con:
            con.execute("BEGIN IMMEDIATE")
            if con.execute("SELECT 1 FROM config").fetchone():
                raise Refused("Gate is already initialized")
            if any((control / name).exists() for name in ("spec.json", "baseline", "runs")):
                raise Refused("Gate files already exist; preserve them")
            (control / "spec.json").write_bytes(raw)
            base = control / "baseline"
            for name in files:
                out = base / name
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(file_bytes(project, name))
            con.execute("INSERT INTO config VALUES(?,?,?)", (digest(raw), source_hash, str(project)))
        return cls(control)

    @contextmanager
    def connect(self):
        from .persistence.sqlite import connection
        with connection(self.db) as con:
            yield con

    def spec(self):
        plain(self.root)
        with self.connect() as con:
            cfg = con.execute("SELECT * FROM config").fetchone()
        path = self.root / "spec.json"
        plain(path)
        if digest(path.read_bytes()) != cfg["spec_hash"]:
            raise Refused("acceptance baseline was modified")
        spec = read_json(path)
        validate_spec(spec)
        if manifest(self.root / "baseline", spec["source_files"])[0] != cfg["baseline_hash"]:
            raise Refused("source baseline was modified")
        return spec, cfg["spec_hash"]

    def candidate(self, run_id):
        if not re.fullmatch(r"run-[0-9a-f]{32}", run_id):
            raise Refused("invalid run id")
        with self.connect() as con:
            if con.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone() is None:
                raise Refused("unknown run")
        return self.root / "runs" / run_id / "candidate"

    def prepare(self):
        spec, _ = self.spec()
        run_id = "run-" + uuid.uuid4().hex
        root = self.root / "runs" / run_id
        root.mkdir(parents=True)
        for name in spec["source_files"]:
            out = root / "candidate" / name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(file_bytes(self.root / "baseline", name))
        with self.connect() as con:
            con.execute("INSERT INTO runs(id,status,created) VALUES(?,?,?)", (run_id, "prepared", now()))
        return run_id

    def apply_proposal(self, run_id, proposal: dict):
        spec, _ = self.spec()
        from .contracts import ChangeProposal, checked
        parsed = checked(ChangeProposal, proposal)
        if parsed.base_revision is not None and manifest(self.candidate(run_id), spec["source_files"])[0] != parsed.base_revision:
            raise Refused("proposal base revision is stale")
        files = proposal["files"]
        if not isinstance(files, list) or not 1 <= len(files) <= len(spec["editable_files"]):
            raise Refused("proposal must contain allowed files")
        seen, validated = set(), []
        for item in files:
            if not isinstance(item, dict) or set(item) != {"path", "content"}:
                raise Refused("invalid proposed file")
            name = relative_name(item["path"])
            if name not in spec["editable_files"] or name.casefold() in seen:
                raise Refused("proposal changes a protected or duplicate path")
            seen.add(name.casefold())
            if not isinstance(item["content"], str) or len(item["content"].encode("utf-8")) > 256_000:
                raise Refused("invalid or oversized source content")
            validated.append((name, item["content"].encode("utf-8")))
        target = self.candidate(run_id)
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
            if row[0] == "accepted":
                raise Refused("accepted runs are immutable; prepare a new run")
            # Invalidate prior authority BEFORE any filesystem changes, including crashes.
            con.execute("UPDATE evaluations SET status='stale' WHERE run_id=? AND status='pass'", (run_id,))
            con.execute("UPDATE runs SET status='editing' WHERE id=?", (run_id,))
        for name, data in validated:
            path = target / name
            plain(path)
            tmp = path.with_name(path.name + ".pending")
            plain(tmp)
            tmp.write_bytes(data)
            os.replace(tmp, path)
        with self.connect() as con:
            con.execute("UPDATE runs SET status='prepared' WHERE id=?", (run_id,))

    def evaluate(self, run_id, executor, *, measure_only=False):
        spec, spec_hash = self.spec()
        candidate = self.candidate(run_id)
        source_hash, files = manifest(candidate, spec["source_files"])
        evaluation_id = "eval-" + uuid.uuid4().hex
        folder = self.root / "runs" / run_id / evaluation_id
        snapshot, scratch = folder / "snapshot", folder / "scratch"
        scratch.mkdir(parents=True)
        for name in files:
            out = snapshot / name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(file_bytes(candidate, name))
        report_path = folder / "report.json"
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
            if row[0] == "accepted":
                raise Refused("accepted run cannot be reevaluated")
            project_version, project_sha = owner_revision(con)
            con.execute("UPDATE evaluations SET status='stale' WHERE run_id=? AND status='pass'", (run_id,))
            con.execute("UPDATE runs SET status='verifying' WHERE id=?", (run_id,))
            con.execute("INSERT INTO evaluations VALUES(?,?,?,?,?,?,?,?,?)", (evaluation_id, run_id, source_hash, spec_hash, "running", str(snapshot), str(report_path), None, now()))
        results, boundary, error = [], None, None
        try:
            # The backend must prove denied reads, writes and networking for this root.
            boundary = executor.probe(snapshot=snapshot, scratch=scratch, control=self.root)
            if boundary.get("verified") is not True and not (measure_only and boundary.get("file_boundary_verified") is True):
                raise Refused("execution boundary probe did not pass")
            for case in spec["cases"]:
                self.spec()
                if manifest(snapshot, spec["source_files"])[0] != source_hash:
                    raise Refused("evaluation snapshot changed")
                args = [a.replace("{scratch}", str(scratch)) for a in case["args"]]
                process = executor.run(snapshot=snapshot, scratch=scratch, control=self.root, entrypoint=spec["entrypoint"], args=args, timeout=spec["case_timeout_s"])
                item = {"id": case["id"], **process, "expected_exit": case["exit_code"], "expected_json": case["stdout_json"]}
                try:
                    actual = parse_json(process["stdout"])
                    item["actual_json"] = actual
                    item["passed"] = process["exit_code"] == case["exit_code"] and same_json(actual, case["stdout_json"]) and not process.get("timed_out", False) and not process.get("overflow", False)
                except (Refused, ValueError, TypeError):
                    item["passed"] = False
                results.append(item)
            self.spec()
            if manifest(snapshot, spec["source_files"])[0] != source_hash or manifest(candidate, spec["source_files"])[0] != source_hash:
                raise Refused("source changed during verification")
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        passed = len(results) == len(spec["cases"]) and all(r["passed"] for r in results)
        status = "blocked" if error else ("review" if measure_only else "pass") if passed else "fail"
        report = {"schema_version": 1, "evaluation_id": evaluation_id, "run_id": run_id, "status": status, "measurement_only": measure_only, "source_sha256": source_hash, "spec_sha256": spec_hash, "project_sha256": project_sha, "project_version": project_version, "source_manifest": files, "boundary": boundary, "error": error, "cases": results, "finished_at": now()}
        from .contracts import VerificationRecord, checked
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            if owner_revision(con) != (project_version, project_sha):
                status = report["status"] = "blocked"
                report["error"] = "owner revision changed during verification"
            checked(VerificationRecord, report)
            raw = encoded(report)
            report_path.write_bytes(raw)
            con.execute("UPDATE evaluations SET status=?,report_hash=? WHERE id=?", (status, digest(raw), evaluation_id))
            con.execute("UPDATE runs SET status=? WHERE id=?", ("verified" if status == "pass" else status, run_id))
        return report

    def accept(self, run_id):
        """No caller-supplied verdict, permit or report can authorize acceptance."""
        spec, spec_hash = self.spec()
        candidate = self.candidate(run_id)
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            run = con.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if run["status"] != "verified":
                raise Refused("no completed trusted verification for this run")
            ev = con.execute("SELECT * FROM evaluations WHERE run_id=? ORDER BY rowid DESC LIMIT 1", (run_id,)).fetchone()
            if ev is None or ev["status"] != "pass" or ev["spec_hash"] != spec_hash:
                raise Refused("no current passing evaluation")
            report_path, snapshot = Path(ev["report"]), Path(ev["snapshot"])
            plain(report_path)
            if digest(report_path.read_bytes()) != ev["report_hash"]:
                raise Refused("verification report was modified")
            report = read_json(report_path)
            from .contracts import VerificationRecord, checked
            checked(VerificationRecord, report)
            if (report.get("project_version"), report.get("project_sha256")) != owner_revision(con):
                raise Refused("verified owner revision changed")
            if (report["evaluation_id"] != ev["id"] or report["run_id"] != run_id or report["status"] != "pass"
                    or report["source_sha256"] != ev["source_hash"] or report["spec_sha256"] != spec_hash
                    or report.get("boundary", {}).get("verified") is not True
                    or [r["id"] for r in report["cases"]] != [c["id"] for c in spec["cases"]]
                    or not all(r.get("passed") is True for r in report["cases"])):
                raise Refused("incomplete verification authority")
            if manifest(candidate, spec["source_files"])[0] != ev["source_hash"] or manifest(snapshot, spec["source_files"])[0] != ev["source_hash"]:
                raise Refused("verified source has changed")
            checkpoint = {"id": "ck-" + uuid.uuid4().hex, "run_id": run_id, "evaluation_id": ev["id"], "source_sha256": ev["source_hash"], "spec_sha256": spec_hash, "snapshot": str(snapshot), "report_sha256": ev["report_hash"], "created_at": now()}
            con.execute("INSERT INTO checkpoints VALUES(?,?,?,?,?,?,?,?)", tuple(checkpoint.values()))
            con.execute("UPDATE runs SET status='accepted' WHERE id=?", (run_id,))
        return checkpoint

    def agent_attempt(self, run_id, agent, feedback=None):
        spec, _ = self.spec()
        candidate = self.candidate(run_id)
        attempt_id = "attempt-" + uuid.uuid4().hex
        folder = candidate.parent / attempt_id
        folder.mkdir()
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            run = con.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if run["status"] == "accepted" or run["attempts"] >= spec["max_attempts"]:
                raise Refused("run accepted or model-attempt budget exhausted")
            con.execute("UPDATE runs SET attempts=attempts+1 WHERE id=?", (run_id,))
            # Durable intent precedes external model call. A crash still consumes an attempt.
            con.execute("INSERT INTO attempts VALUES(?,?,?,?,?)", (attempt_id, run_id, "started", str(folder), now()))
        try:
            sources = {name: file_bytes(candidate, name).decode("utf-8") for name in spec["source_files"]}
            proposal, receipt = agent.propose(spec=spec, sources=sources, feedback=feedback, folder=folder, workspace=candidate, control=self.root)
            (folder / "receipt.json").write_bytes(encoded(receipt))
            (folder / "proposal.json").write_bytes(encoded(proposal))
            self.apply_proposal(run_id, proposal)
        except Exception:
            with self.connect() as con:
                con.execute("UPDATE attempts SET status='failed_or_unknown' WHERE id=?", (attempt_id,))
            raise
        with self.connect() as con:
            con.execute("UPDATE attempts SET status='applied' WHERE id=?", (attempt_id,))
        return receipt

    def run(self, executor, agent, run_id=None, progress=None, *, measure_only=False):
        run_id = run_id or self.prepare()
        spec, _ = self.spec()
        while True:
            report = self.evaluate(run_id, executor, measure_only=measure_only)
            if progress:
                progress(report)
            if report["status"] == "pass":
                return {"status": "accepted", "run_id": run_id, "checkpoint": self.accept(run_id), "report": report}
            if report["status"] == "review":
                return {"status": "review", "run_id": run_id, "report": report}
            if report["status"] == "blocked":
                return {"status": "blocked", "run_id": run_id, "report": report}
            with self.connect() as con:
                attempts = con.execute("SELECT attempts FROM runs WHERE id=?", (run_id,)).fetchone()[0]
            if attempts >= spec["max_attempts"]:
                return {"status": "fail", "run_id": run_id, "report": report}
            feedback = [{"id": r["id"], "actual": r.get("actual_json"), "expected": r["expected_json"], "exit_code": r["exit_code"]} for r in report["cases"] if not r["passed"]]
            self.agent_attempt(run_id, agent, feedback)
