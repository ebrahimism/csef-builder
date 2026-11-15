---
name: csef-build
description: Build or continue CSEF itself from its engineering roadmap. Use for CSEF backlog execution, resuming checked tasks, preserving owner requirements and architecture, recording real test evidence, and evaluating proposed integrations. This skill builds the CSEF product; it does not operate arbitrary end-user projects or authorize releases.
---

# CSEF build workflow

Use the owner's selected CSEF workspace; do not infer it from the installed
plugin cache. Resolve its absolute path and read its AGENTS.md first.
All commands below run in that workspace; add `--project ABSOLUTE_PATH` before
the subcommand when invoking this skill's bundled `scripts/backlog.py` directly.
The workspace launcher is `python tools/csef_backlog.py`.

## Establish the next bounded action

1. Read `docs/PROJECT-GOALS.json` and run `status`, then `next`.
2. Honor the owner's batch limit. Initial kickoff is T001 followed by T002;
   do not infer authorization to execute all 38 tasks from that kickoff.
3. Run `packet T001` (substitute the selected ID). Read its acceptance, owner
   goal text, dependencies and relevant sources/tests. Consult the master plan
   and integration/module maps only for the selected responsibility.
4. If an active task exists, continue it. For a blocked task, inspect `history`
   before `resume ID`. Repeatedly calling the model is not recovery.
5. Run `start ID`. Preserve accepted decisions and the canonical task definition.
   Resolve routine implementation choices; ask only for owner decisions that
   cannot be obtained from current sources.

## Implement and check

Deliver the smallest functioning slice satisfying the task. Prefer existing
code or a proven dependency to building a parallel framework. The proposed
75 responsibilities are a map, not 75 empty files to create.
Verify changeable upstream claims against official current sources; record
the upstream version/commit and adopt/reject rationale for reuse trials.

Use `check ID --target tests/RELEVANT_PATH` during focused development, then
`check ID` for the full repository suite before completion. The controller
executes pytest itself, rejects empty/skipped/failed reports, and binds its
receipt to the task, plan and source snapshot. It does not interpret semantic
acceptance. Never rewrite tests or goals merely to obtain a passing receipt.

For architecture, contract, security, migration, goal-change or repeated-failure
work, obtain an independent review session if authorized; use the same model
in a separate session when no different model is configured. If unavailable,
record review pending and block completion. Do not buy or enable services.
Routine work requires a focused acceptance review without an extra model call.
Record total review effort; no unmeasured claim of cheaper or better output.

## Record and hand off

Read [the controller protocol](references/controller.md) for the review format.
Write acceptance evidence before the final check. Keep review notes and concise
handoffs in `docs/progress/`. Run `complete ID --review PATH` only when every
criterion is addressed and a current full-suite receipt exists.
Use `block ID --reason TEXT` for a real blocker, not an invented success.
After completion, report the changed behavior, verification, limitations,
next eligible task and whether it is within the authorized batch.

Do not publish, deploy, push, change accounts, weaken execution permissions, or
mint a Gate checkpoint through this tracker. This is local build bookkeeping,
not CSEF's production orchestrator or an independent release evaluator.
