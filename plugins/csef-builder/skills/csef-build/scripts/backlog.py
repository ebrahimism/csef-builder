"""Local CSEF build bookkeeping. Never a Gate or a hostile-code boundary."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import uuid
import xml.etree.ElementTree as ET


class Refused(ValueError):
    pass


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def linked(path):
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)


def inside(root, relative):
    path = root / relative
    if not path.resolve().is_relative_to(root) or Path(relative).is_absolute():
        raise Refused("path must be relative and inside the project")
    current = path
    while current != root:
        if current.exists() and linked(current):
            raise Refused("symlink/junction paths are not supported")
        current = current.parent
    return path


def snapshot(root):
    ignored = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".csef-build",
               "node_modules", "deliverables"}
    h = hashlib.sha256()
    for folder, dirs, files in os.walk(root):
        base = Path(folder)
        dirs[:] = sorted(d for d in dirs if d not in ignored and
                         not (base == root / "docs" and d == "progress"))
        for name in dirs:
            if linked(base / name):
                raise Refused("source directory symlink/junction: " + str(base / name))
        for name in sorted(files):
            path = base / name
            if name.endswith((".pyc", ".pyo")):
                continue
            if linked(path):
                raise Refused("source file symlink: " + str(path))
            h.update(encoded([path.relative_to(root).as_posix(), sha(path)]))
    return h.hexdigest()


def parse_report(path):
    tree = ET.parse(path).getroot()
    cases = list(tree.iter("testcase"))
    return {"cases": len(cases), "failed": len(list(tree.iter("failure"))),
            "errors": len(list(tree.iter("error"))), "skipped": len(list(tree.iter("skipped")))}


def process(argv, root, timeout, scratch):
    # Reuse CSEF's existing bounded process runner; do not fork a second runner.
    sys.path.insert(0, str(root / "src"))
    from csef_gate.backends import capture, environment
    return capture(argv, cwd=root, timeout=timeout, env=environment(scratch), limit=1_000_000)


class Book:
    def __init__(self, root):
        self.root = Path(root).resolve()
        plan_path = self.root / "docs/roadmap/backlog.json"
        goal_path = self.root / "docs/PROJECT-GOALS.json"
        self.plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.goals = json.loads(goal_path.read_text(encoding="utf-8"))
        tasks = self.plan["tasks"]
        self.tasks = {t["id"]: t for t in tasks}
        if not tasks or len(tasks) != len(self.tasks):
            raise Refused("empty/duplicate task definitions")
        goal_ids = {g["id"] for g in self.goals["facts"]}
        visiting, visited = set(), set()

        def visit(key):
            if key in visiting or key not in self.tasks:
                raise Refused("cyclic or unknown dependency: " + key)
            if key in visited:
                return
            visiting.add(key)
            task = self.tasks[key]
            if not task["acceptance"].strip() or not set(task["goals"]) <= goal_ids:
                raise Refused("invalid acceptance or owner goal references: " + key)
            for dep in task["depends_on"]:
                visit(dep)
            visiting.remove(key)
            visited.add(key)

        for key in self.tasks:
            visit(key)
        self.plan_sha = hashlib.sha256(encoded([self.plan, self.goals])).hexdigest()
        self.runtime = inside(self.root, ".csef-build")
        self.runtime.mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.runtime / "progress.sqlite", timeout=2)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks(
              id TEXT PRIMARY KEY, status TEXT NOT NULL, plan_sha TEXT NOT NULL,
              reason TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS checks(
              id TEXT PRIMARY KEY, task TEXT NOT NULL, source_sha TEXT NOT NULL,
              plan_sha TEXT NOT NULL, full_suite INTEGER NOT NULL,
              passed INTEGER NOT NULL, receipt TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(
              seq INTEGER PRIMARY KEY, at REAL NOT NULL, task TEXT,
              action TEXT NOT NULL, data TEXT NOT NULL);
        """)

    def close(self):
        self.db.close()

    def task(self, key):
        if key not in self.tasks:
            raise Refused("unknown task: " + key)
        return self.tasks[key]

    def state(self, key):
        self.task(key)
        row = self.db.execute("SELECT * FROM tasks WHERE id=?", (key,)).fetchone()
        return dict(row) if row else {"id": key, "status": "planned"}

    def event(self, key, action, data):
        self.db.execute("INSERT INTO events(at,task,action,data) VALUES(?,?,?,?)",
                        (time.time(), key, action, encoded(data).decode("utf-8")))

    def ready(self):
        return [t for t in self.tasks.values() if self.state(t["id"])["status"] == "planned"
                and all(self.state(d)["status"] == "done" for d in t["depends_on"])]

    def packet(self, key):
        task = self.task(key)
        return {"task": task, "runtime": self.state(key), "plan_sha": self.plan_sha,
                "owner_goals": [g for g in self.goals["facts"] if g["id"] in task["goals"]],
                "review_required": self.needs_review(key),
                "read": ["AGENTS.md", "docs/MASTER-PLAN.fa.md", "docs/WORKFLOW.md"],
                "warning": "Planned files are responsibilities, not empty-file scaffolding orders."}

    def needs_review(self, key):
        task = self.task(key)
        text = " ".join(str(task[k]) for k in ("title", "scope", "acceptance")).lower()
        return key in {"T002", "T003"} or any(word in text for word in
            ("معماری", "قرارداد", "مهاجرت", "امنیت", "تغییر هدف", "architecture", "migration", "security"))

    def active(self, key):
        state = self.state(key)
        if state["status"] != "active":
            raise Refused("task is not active")
        if state["plan_sha"] != self.plan_sha:
            raise Refused("plan changed; block, review the change, then explicitly resume")

    def start(self, key, resume=False):
        self.task(key)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            status = self.state(key)["status"]
            if status != ("blocked" if resume else "planned"):
                raise Refused("use start for planned tasks; resume for blocked tasks")
            if self.db.execute("SELECT id FROM tasks WHERE status='active'").fetchone():
                raise Refused("another task is already active")
            if not all(self.state(d)["status"] == "done" for d in self.tasks[key]["depends_on"]):
                raise Refused("dependencies are not complete")
            self.db.execute("INSERT OR REPLACE INTO tasks VALUES(?,?,?,?)",
                            (key, "active", self.plan_sha, ""))
            # Every activation needs fresh checks, including same-plan resumes.
            self.db.execute("DELETE FROM checks WHERE task=?", (key,))
            self.event(key, "resume" if resume else "start", {"plan_sha": self.plan_sha})
        return self.packet(key)

    def block(self, key, reason):
        if not reason.strip():
            raise Refused("a concrete blocker reason is required")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if self.state(key)["status"] != "active":
                raise Refused("only an active task can be blocked")
            self.db.execute("UPDATE tasks SET status='blocked',reason=? WHERE id=?", (reason, key))
            self.event(key, "block", {"reason": reason})
        return self.state(key)

    def check(self, key, targets=(), timeout=600, runner=process):
        targets = list(targets) or ["tests"]
        if timeout < 1 or timeout > 1800:
            raise Refused("timeout must be 1..1800 seconds")
        for target in targets:
            if target.startswith("-") or not inside(self.root, target).exists():
                raise Refused("test targets must be existing workspace paths")
        full = len(targets) == 1 and inside(self.root, targets[0]).resolve() == self.root / "tests"
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self.active(key)
            before = snapshot(self.root)
            check_id = uuid.uuid4().hex
            folder = self.runtime / "checks" / check_id
            folder.mkdir(parents=True)
            scratch = folder / "scratch"
            scratch.mkdir()
            report = folder / "junit.xml"
            argv = [sys.executable, "-X", "utf8", "-m", "pytest", "-o", "addopts=", "-q",
                    "--tb=short", "--basetemp=" + str(folder / "temp"),
                    "--junitxml=" + str(report), *targets]
            result = runner(argv, self.root, timeout, scratch)
            after = snapshot(self.root)
            try:
                counts = parse_report(report)
            except (OSError, ET.ParseError):
                counts = {"cases": 0, "failed": 0, "errors": 1, "skipped": 0}
            passed = (result["exit_code"] == 0 and not result["timed_out"] and
                      not result["overflow"] and before == after and counts["cases"] > 0 and
                      not any(counts[k] for k in ("failed", "errors", "skipped")))
            receipt = {"id": check_id, "task_id": key, "passed": passed, "full_suite": full,
                       "plan_sha": self.plan_sha, "source_sha": before, "after_sha": after,
                       "argv": argv, "counts": counts, "process": result}
            (folder / "receipt.json").write_bytes(encoded(receipt))
            self.db.execute("INSERT INTO checks VALUES(?,?,?,?,?,?,?)", (
                check_id, key, before, self.plan_sha, int(full), int(passed),
                str((folder / "receipt.json").relative_to(self.root))))
            self.event(key, "check", {"id": check_id, "passed": passed, "counts": counts})
        return receipt

    def complete(self, key, review_path):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self.active(key)
            review_file = inside(self.root, review_path)
            review = json.loads(review_file.read_text(encoding="utf-8"))
            if (review.get("task_id") != key or review.get("acceptance") != self.task(key)["acceptance"]
                    or not isinstance(review.get("findings"), str) or not review["findings"].strip()
                    or not isinstance(review.get("risks"), list)):
                raise Refused("review must address the exact task and acceptance, with findings and risks")
            paths = review.get("evidence")
            if not isinstance(paths, list) or not paths:
                raise Refused("nonempty acceptance evidence is required")
            if self.needs_review(key):
                independent = review.get("independent_review")
                if not isinstance(independent, str) or not independent.strip():
                    raise Refused("this task requires a separate-session review report")
                paths = [*paths, independent]
            evidence = {}
            for relative in paths:
                path = inside(self.root, relative)
                if not path.is_file() or not path.stat().st_size:
                    raise Refused("missing/empty evidence: " + str(relative))
                evidence[relative] = sha(path)
            current = snapshot(self.root)
            row = self.db.execute("""SELECT * FROM checks WHERE task=? AND passed=1
                AND full_suite=1 AND plan_sha=? AND source_sha=? ORDER BY rowid DESC LIMIT 1""",
                                  (key, self.plan_sha, current)).fetchone()
            if not row:
                raise Refused("no current successful full-suite check; run check after source edits")
            self.db.execute("UPDATE tasks SET status='done' WHERE id=?", (key,))
            self.event(key, "complete", {"check_id": row["id"], "source_sha": current,
                "review_path": review_path, "review_sha": sha(review_file), "evidence": evidence,
                "risks": review["risks"], "authority": "build bookkeeping only; not release approval"})
        return self.state(key)

    def history(self):
        return [dict(row) | {"data": json.loads(row["data"])} for row in
                self.db.execute("SELECT * FROM events ORDER BY seq")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "next", "history"):
        commands.add_parser(name)
    for name in ("packet", "start", "resume", "block", "check", "complete"):
        item = commands.add_parser(name)
        item.add_argument("task")
        if name == "block":
            item.add_argument("--reason", required=True)
        elif name == "check":
            item.add_argument("--target", action="append", default=[])
            item.add_argument("--timeout", type=int, default=600)
        elif name == "complete":
            item.add_argument("--review", required=True)
    args = parser.parse_args()
    book = None
    try:
        book = Book(args.project)
        if args.command == "status":
            result = {"plan_sha": book.plan_sha, "tasks": [book.state(k) for k in book.tasks]}
        elif args.command == "next":
            result = {"active": [book.state(k) for k in book.tasks if book.state(k)["status"] == "active"],
                      "ready": book.ready(), "blocked": [book.state(k) for k in book.tasks
                                                          if book.state(k)["status"] == "blocked"]}
        elif args.command == "history":
            result = book.history()
        elif args.command == "packet":
            result = book.packet(args.task)
        elif args.command in {"start", "resume"}:
            result = book.start(args.task, resume=args.command == "resume")
        elif args.command == "block":
            result = book.block(args.task, args.reason)
        elif args.command == "check":
            result = book.check(args.task, args.target, args.timeout)
        else:
            result = book.complete(args.task, args.review)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if args.command == "check" and not result["passed"] else 0
    except (ValueError, OSError, KeyError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        if book:
            book.close()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
