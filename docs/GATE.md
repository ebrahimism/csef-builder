# Independent acceptance gate — pilot v1

## Trust and scope

The existing Codex CLI proposes replacement file contents. The trusted CSEF controller
owns the frozen specification, execution observations and acceptance decision. It never
imports candidate code, candidate tests or the legacy `csef_contracts` package.

This is process/authority separation, not clean-room author independence: the same
assistant authored the pilot and sample criteria. The trusted owner/admin, controller,
Python installation, Codex CLI and OS remain in the trusted computing base. SQLite is
protected by OS access rules, not cryptographic signatures against a malicious owner.

The first backend supports a stdlib Python CLI script with JSON stdout. Package
installation, arbitrary build systems, web UX and deployment are outside this pilot.

## Separate trees

1. Original project: never modified by the workflow.
2. Control store: source/spec baseline, attempts, receipts, authoritative snapshots,
   reports, SQLite journal and checkpoint records.
3. Execution/agent staging: copies outside the denied control tree. Child commands can
   read source; only execution scratch is writable.

The installed elevated Windows backend requires root read. The backend denies the
control store and selected credential paths, but is not a general host-read jail.
It is not a substitute for the dedicated VM required by legacy D1.

## Execution and limits

Specifications are closed JSON objects. Every case has literal argv, expected exit code
and expected JSON stdout. Empty, duplicate and unsupported criteria are refused.
JSON booleans do not equal integers; duplicate keys and nonfinite values are rejected.
All cases execute in separate child processes, sequentially, with fresh scratch per
evaluation. This permits observing SQLite persistence without retaining old test data.

Only trusted code selects the Python interpreter, `-I -S -X utf8`, entrypoint and Codex sandbox
command. No shell command from the model is executed. Proposals are completely validated
before any file writes, including scope, portable paths, reparse points and size limits.

Before evaluation, a trusted probe checks source reads, scratch writes, denied control
reads/writes, denied source writes and denied TCP access to a positively reachable local
listener. The current host passes file checks but permits loopback. Strict evaluation
therefore returns BLOCKED before candidate execution. Probe success would still be
observational evidence, not proof against every sandbox escape or network transport.

`--measure-only` is an explicit lane for reviewed local sample code. It still requires
file checks, records the network shortfall, and can measure behavior. Its best possible
result is REVIEW, even on a host where every probe passes. It never authorizes acceptance.
Do not use it for hostile code, sensitive projects or production.

Provider/application secrets and PYTHONPATH are not inherited. Output is bounded;
commands/model calls have deadlines and their Windows process trees are terminated on
timeout or output overflow. The installed Codex login is reused, without exposing or
copying credentials. Token usage is recorded when reported; USD cost is not inferred.
This prototype does not enforce a dollar budget or prove prompt-injection resistance.
The source specification in the repository is public; this pilot does not claim hidden
test secrecy. The authoritative frozen copy is in the denied control store.

## Durable authority

The controller records an attempt and consumes its persistent budget before calling
Codex. A crash or unknown provider outcome is not a free retry. Model final output and
events are artifacts, never authority. The adapter uses a read-only profile and schema
output; it does not impose a model override or install another coding engine.

Each evaluation records durable running intent, snapshots exact source bytes, observes
real process output and writes a complete version-bound report. Only the controller
stores that report's hash and completion status in SQLite.

`accept` takes only a run ID. In one SQLite transaction it checks the latest strict PASS,
full criterion list, current spec hash, report bytes, candidate bytes, authoritative
snapshot bytes and boundary result, then creates one single-use checkpoint. It accepts
no caller-issued permit or PASS. Checkpoints identify verified artifacts; they do not
merge code, deploy or protect files against the trusted owner.

New proposals invalidate old passing evaluations before writes. Interrupted evaluation
has no authority and must be repeated. Resume uses the same attempt budget. Fresh local
scratch makes sample reevaluation safe; exactly-once external API effects, distributed
orchestration and host power-loss guarantees are not implemented. Use one controller
at a time for this pilot.

## Commands

From the repository, use `python csef.py` (or installed `csef-gate`):

- `init --control DIR --project DIR --spec FILE`: freeze trusted inputs in a new,
  disjoint control directory.
- `prepare --control DIR`: create a run and a candidate copy.
- `propose --control DIR --run-id ID`: one bounded live Codex attempt.
- `apply --control DIR --run-id ID --proposal FILE`: validate an external proposal;
  this never authorizes acceptance.
- `evaluate --control DIR --run-id ID [--measure-only]`: independently observe behavior.
- `accept --control DIR --run-id ID`: consume current strict passing authority.
- `run --control DIR [--run-id ID] [--measure-only]`: evaluate, repair, reevaluate within
  the persistent attempt budget, then accept or report REVIEW/failure.

Exit 0 is successful command/strict acceptance; exit 1 is failed/blocked evaluation;
exit 2 is REVIEW or refused/invalid input. Successful init/prepare does not verify an app.

Official interfaces: [non-interactive Codex](https://learn.chatgpt.com/docs/non-interactive-mode),
[permission profiles](https://learn.chatgpt.com/docs/permissions),
[native Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox).
