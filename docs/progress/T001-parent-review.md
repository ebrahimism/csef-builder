# T001 independent session review

The parent session reviewed the implementation produced by the fresh Codex CLI
session before accepting T001. Two issues were found and repaired:

1. The original test compared the historical baseline against every future
   checkout. Any legitimate next-task source change would fail the whole suite.
   Tests now check deterministic inventory behavior on a fixture and the stored
   manifest's internal consistency. Explicit current-tree comparison is available
   through `baseline_inventory.py --verify`; it is not a permanent freeze of all
   future development.
2. A JUnit parser hardcoded process exit 0 and a command it had not observed.
   It now reports only XML observations. The controller receipt is the source
   for the actual command, process exit, timeout and source digest.

This is an engineering review by a separate existing session, not independent
cryptographic attestation or release approval. No owner requirement was weakened.
The task's goal is reproducible historical evidence, not preventing later edits.

The first CLI session correctly blocked when its sandbox could not find an
existing Git identity and Git required explicit trust for this ownershipless
filesystem. The parent verified the already-connected GitHub account's actual
name/email through the GitHub connector. Git uses that existing account identity
and path-specific trust per command; no global settings or remotes are required.
