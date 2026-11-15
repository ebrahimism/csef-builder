# Building CSEF

This repository is a measured prototype, not a finished general-purpose agent.
Communicate with the owner in clear Persian. Act on authorized work; ask only
when an owner decision or genuinely missing requirement blocks progress.

## Source of intent

- `docs/PROJECT-GOALS.json`: owner requirements REQ-101 through REQ-107.
- `docs/MASTER-PLAN.fa.md`: scope, architecture and release criteria.
- `docs/roadmap/backlog.json`: task definitions, dependencies and acceptance.
- `docs/roadmap/MODULES.fa.md`: proposed responsibilities, not scaffolding orders.
- `docs/roadmap/INTEGRATIONS.fa.md`: candidate reuse; verify owning sources first.
- `docs/WORKFLOW.md` and `docs/decisions/`: workflow and recorded decisions.

Use the `csef-build` skill when available. The fallback is
`plugins/csef-builder/skills/csef-build/SKILL.md` in this repository.
Run `python tools/csef_backlog.py next` and `packet TASK` before editing.
Read the relevant source/tests and task-specific documentation, not every plan.
The plan remains immutable task input; runtime progress lives in `.csef-build/`.

## Work discipline

1. Select a dependency-ready task within the owner's authorized batch.
2. Start it in the tracker. State the expected observable change and checks.
3. Reuse working code. Implement the smallest complete acceptance slice.
   Do not create empty files for the proposed module inventory.
4. Preserve goal IDs, accepted decisions, data and existing tests. A failing
   check is evidence to investigate, never permission to weaken acceptance.
5. Run meaningful checks with the tracker; record acceptance evidence and
   unresolved limitations. A test pass alone is not semantic acceptance.
6. Complete only with a current passing receipt and the documented review.
   Block with a concrete reason when necessary; resume from stored state.

Use a separate review session for architecture, contracts, goal changes,
security boundaries, migrations, or repeated failure, subject to the owner's
authorization and available tools. Do not silently create paid model calls.
Routine edits need focused review and automated checks, not a model per edit.
After two failed repair attempts, diagnose and record before more retries.

## Boundaries and truthful reporting

The build tracker and these instructions are engineering aids, not a security
boundary or release authority. Keep the independent Gate authoritative.
Native Windows loopback isolation is unresolved: measure-only stays REVIEW,
never a release checkpoint. Legacy permits cannot authorize the new Gate.
Do not publish, deploy, push, spend money, or change accounts without scope
authorization. Preserve existing unrelated files and settings.
Do not claim cost savings, advanced-project success or safe release without
the corresponding measurements. Report what ran, what failed and what remains.

## Start and verification

Read `docs/START-CODEX.fa.md` for commands and the bounded T001/T002 kickoff.
The canonical build-controller script is packaged in the plugin; the root
`tools/csef_backlog.py` is a thin launcher. Run tests through `check`; it creates
a fresh temporary directory and records command, output and source digest.
