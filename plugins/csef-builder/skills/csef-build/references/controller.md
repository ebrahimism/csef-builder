# Controller protocol

The script uses Python 3.11+, the CSEF checkout, and its installed pytest. It
does not need an API key or a running server. The checkout's existing bounded
process runner executes checks. The installed plugin's script and the workspace
launcher use the same code; do not edit the installed cache.

```
python tools/csef_backlog.py status
python tools/csef_backlog.py next
python tools/csef_backlog.py packet T001
python tools/csef_backlog.py start T001
python tools/csef_backlog.py check T001 --target tests/integration
python tools/csef_backlog.py check T001
python tools/csef_backlog.py complete T001 --review docs/progress/T001-review.json
python tools/csef_backlog.py block T001 --reason "Concrete missing prerequisite"
python tools/csef_backlog.py resume T001
python tools/csef_backlog.py history
```

Review JSON, filled with real findings, not copied as a success assertion:

```json
{
  "task_id": "T001",
  "acceptance": "Exact acceptance text from packet",
  "findings": "Explain how every acceptance criterion was checked; note limitations.",
  "evidence": ["docs/evidence/baseline-vnext/manifest.json"],
  "risks": [],
  "independent_review": null
}
```

`evidence` contains existing nonempty files inside the workspace, with no
symlink escapes. Completion records their SHA-256 hashes and the review hash.
For work requiring a second session, `independent_review` is the path to its
nonempty report, and findings explains that report's result. The controller
enforces that path for tasks T002 and T003 and for scopes containing security,
architecture, contracts, migration or goal-change terms. It cannot prove who
wrote the report or whether it is correct: the skill must obtain the session.

A whole-suite receipt is required, even if focused tests already passed.
Any source change after a check invalidates it. Runtime state, test caches,
delivery ZIPs and `docs/progress/` are excluded from that digest; these exclusions
are bookkeeping conveniences, not a hostile-code boundary. Review and evidence
are hashed separately at completion. Source-tree symlinks/junctions are refused.
Changes to the plan require explicit `block` then `resume`, which binds the
revised plan and requires a new check. Historical completion records remain
historical; later legitimate source changes do not reopen all prior tasks.

SQLite serializes mutations and permits one active task. Check execution holds
the write transaction, so concurrent completion cannot race a running check.
A crashed transaction rolls back; use history and re-run the check. Never edit
the database to assert success. A forged local DB remains possible for a local
writer; no release authority is derived from it.
