# Observed pilot evidence

These are copies for review; acceptance authority remains in the protected local
control store identified in `summary.json`.

- `initial-report.json`: real execution of the defective seed, 9/14 passing.
- `final-report.json`: same frozen acceptance suite and live Codex proposal, 14/14.
- `model-receipt.json`: one successful live Codex invocation and reported token usage.
- `summary.json`: exact source/spec digests, the acceptance rejection and zero checkpoints.

The final result is REVIEW, not PASS/accepted. Filesystem boundary probes succeeded;
the loopback network probe failed. The acceptance criteria were never weakened.

An adapter startup failed before the model turn; it consumed an attempt. An intermediate
measurement of the proposed code was 12/14 because isolated Python ignored the environment's
UTF-8 setting. The executor was corrected to use `-X utf8`; source and criteria remained
unchanged. This is recorded rather than attributed to the coding agent.

This single small pilot establishes integration, not an advantage over Codex alone,
general application-building reliability or production security.

## Fresh unattended workflow

After fixing the adapter/executor, the complete workflow was run again in a new control
store, with no manual changes during execution. One live Codex proposal took the sample
from 9/14 to 14/14. Filesystem probes passed; network isolation did not. The result was
REVIEW, and a separate acceptance attempt was refused with zero checkpoints.

See `clean-summary.json`, `clean-initial-report.json`, `clean-final-report.json` and
`clean-model-receipt.json`. The original source and acceptance specification were checked
against the frozen baseline and remained unchanged.
