# Independent compatibility audit and Step 5 gate

Audit date: 2026-11-15. Status labels: EXECUTED = inspected or run here;
PROPOSED = intended rule/change, not accepted or implemented; BLOCKED = a named
prerequisite is absent. This document does not redefine the existing baseline.

## Executive determination

EXECUTED: the original suite passed 48/48. Eighteen new characterization probes
reproduce missing enforcement or contradictions. Their passing means the gaps
are present, not that the implementation satisfies the desired security rules.
No production contract code was changed. Step 5 is not complete.

Execution record: Python 3.11.9, Pydantic 2.14.3, pytest 8.4.2. Original suite:
48 passed in 1.54s. Final suite: 72 passed in 4.19s (48 original + 18 gap
characterizations + 6 runner checks). Seed compatibility: 3 pass, 1 fail
(bad_input -> unknown), 1 pending (timeout), exit 1; see
../../compatibility/results-primary.json. The initial runner-test invocation had
six setup errors because the host's default pytest temporary directory was
inaccessible. Re-running with a fresh workspace-local --basetemp passed.
No contract fix is implied by these counts.

The original suite is useful regression evidence for selected API examples. It
does not establish end-to-end authorization, authenticated evidence, byte-level
baseline integrity, durable recovery, or checkpoint validity. Several gaps are
direct violations of written rules, not merely ambiguous implementation choices.

## Ranked findings / risk register

Severity: P0 blocks reliance on a security/correctness boundary; P1 blocks
contract release; P2 blocks portability/reproducibility claims. These are contract
boundary severities, not claims of a deployed exploit. Owners below are proposed
accountable roles, not assigned people. Every risk remains OPEN.

| ID / priority | Executed evidence and divergent sequence | Impact / owner / release gate |
| --- | --- | --- |
| R1 P0 | A01-A05: metadata with no execution record produces PASS; empty bundle + caller PASS promotes; promotion accepts a different commit and policy. One implementation trusts enum PASS; another requires a verifier attestation. | Unverified checkpoint. Verifier/controller owner. Require trusted result and exact tuple binding. |
| R2 P0 | A06-A07: reserve 1, rollback twice => reserved=-1; two further live reservations of 1 fit a cap of 1. A foreign ledger reservation also settles. | Budget cap evasion. Accounting owner. Exactly-once settlement bound to durable ledger identity. |
| R3 P0 | A08-A09: src/../../outside.txt and missing path return allow for a scoped write. A canonicalizing implementation rejects both. | Scope escape if callers rely on this policy API. Gateway owner. Resolve and enforce scope at the effect boundary. |
| R4 P0 | A10: AUTHORIZED with open_decisions transitions to EXECUTING; calling the separate readiness method refuses it. | I15 not enforced by transition. Controller owner. Mandatory guarded transition. |
| R5 P1 | A11-A12: invalidate an appended checkpoint; chain still returns original valid head. Reuse checkpoint ID with another project and expected parent; append succeeds. | Recovery selects invalid lineage. State owner. Append-only invalidation events and ancestor validity. |
| R6 P1 | A13-A15: frozen Policy.tools is mutable without changing hash; unknown capability inherits allow default; arbitrary BaseModel input silently drops extra fields. | Policy and closed-schema assumptions diverge. Contract owner. Deep value immutability and explicit input closure rules. |
| R7 P1 | A16-A18: bad_input becomes unknown; UNKNOWN + POLICY_DENIED + read_only => replay; can_transition_to permits HALTED_FOR_SECURITY -> ABANDONED but transition refuses. | Wrong recovery or unusable state machine. Recovery owner. Total decision table and consistent transition relation. |
| R8 P1 | Inspected: policy scope, sandbox_required, network_required and once_per_task are not consumed by decide; effect check does not bind name/version/idempotency; registry does not compose policy, approval, reservation and journal. | Local checks are not a gateway guarantee. Gateway owner. One admission operation with ordered failure semantics. |
| R9 P1 | Inspected: I14 compares caller-supplied hash strings, never hashes acceptance bytes; chain_head and content_hash are unverified strings. | Modified bytes with unchanged labels evade model checks. Evidence owner. Canonical bytes, trusted storage and recomputation. |
| R10 P2 | Inspected: unpinned Pydantic lower bound, coercive models, naive timestamps, abbreviated Git SHA, unconstrained schema_version; docs and models differ on content_ref/base_commit. | Cross-runtime disagreement. Schema owner. Versioned wire format, locks and normative vectors. |

Probe IDs refer to tests/audit/test_residual_gaps.py. Counterexamples use normal
validated reconstruction, not model_copy's unchecked update shortcut.

## I13-I15 and evidence limitations

* I13: rejecting producer="agent" proves a discriminant constraint. Anyone who can
  construct input can supply producer="harness" (also the default). A01 has no
  trusted invocation lookup, authenticated writer, content bytes or execution
  record. VerificationRecord is neither consumed by compute_verdict nor promote.
* I14: mismatching two hash labels is detected; changing underlying bytes while
  preserving labels is untested and cannot be detected by these APIs. There is no
  acceptance-byte input or trusted digest resolver. No ACL/VM boundary was tested.
* I15: the explicit readiness helper rejects open decisions, but transition does
  not call it. The documented RUNNING state is named EXECUTING in the model.
  guessed=False validates a claim, not the provenance of a decision.
* Evidence records lack the captured outcome needed to compare expected exit
  codes. Item environment, task identity and evidence kind are not fully joined.
  Duplicate evidence IDs are used even in the existing happy-path fixtures.
* Existing concurrency test exercises 24 reservations under one in-memory lock;
  it does not test competing processes, settlement, crash recovery or durability.
* Existing checkpoint tests verify selected precondition branches; they do not
  establish Controller identity, verifier authority, Git/journal/store atomicity,
  replay verification, stale ancestors or lease fencing.
* No claim of line/branch coverage, mutation score, property-test coverage or
  cross-version conformance is made. No real sandbox, clean checkout verifier,
  signed authorization, byte tampering or power-loss experiment was executed.

## Independent implementation specification

PROPOSED: implement B in Go using standard-library JSON, explicit tagged values,
integer money units and a small persistent state store. No Pydantic, Python
contract imports, copied source, copied fixtures, generated schemas from A, or
shared domain helpers. Language diversity helps but is not itself independence.

BLOCKED: no independent implementer/build is supplied in this workspace. The
auditor has read A and must not claim clean-room authorship of B. No subagent was
used. Before B starts, a separate spec steward must freeze a reviewed normative
packet and decision log. B receives those documents and public wire examples,
not src/, tests/support.py, A outputs, this code-directed probe suite, or hidden
oracle answers. Record author exposure and packet hashes. A disagreement is
submitted to the steward; do not show B the A patch or ask it to match A.

Isolation has two distinct gates:

1. Semantic independence: separate repository, author context, dependency tree,
   implementation design, fixtures and build. Inspect imports and provenance.
2. Execution isolation: independent fresh process and state directory per case;
   sequences remain within one request. Real untrusted-workload experiments
   require D1's dedicated Linux VM. A local subprocess is not that boundary.

## Wire harness and oracle

EXECUTED artifact: compatibility/run.py accepts an adapter command, sends one JSON
request per fresh process, enforces a ten-second timeout, compares parsed JSON,
and emits per-case results plus a vector digest. Nonzero exit, malformed JSON and
timeouts fail. stdout is protocol-only. No domain imports in the runner.
This is a seed harness, not the completed full suite or a hostile-process sandbox.

The primary adapter currently supports only resolve and classify. Five seed
vectors include a known normative mismatch and an unresolved timeout decision.
The old 48 tests directly import A and are NOT portable conformance tests.

PROPOSED wire v1 expansion: request {protocol:1, case_id, initial_state, operations};
response {protocol:1, results:[{status, code, value}], final_state, events}.
Use stable machine codes, decimal money strings, UTC timestamps, full commit
identities and sorted set arrays. Never compare Python exception wording, UUID
values or wall-clock timestamps. Inject clock/ID sources through adapter inputs.
Adapters translate types only; any decision logic in them invalidates the test.

Oracle authority order: explicit invariant -> ratified decision -> versioned
normative vector. A is never the oracle. Differential equality alone is not a
pass: both implementations can be wrong. Contradictory prose is an OPEN decision,
not a majority vote or silently accepted set of outcomes. Proposed cases remain
pending even when their proposed result happens to match. Runner exit 2 means
pending-only; exit 1 means at least one mismatch/protocol failure. Neither passes.

Freeze normative packet, vectors, build identities, dependencies and runner digest
in a release manifest. Publish public vectors; keep independently authored
adversarial cases hidden until both builds are frozen. Review every oracle change
and rerun both builds against the SAME new manifest. Never update expected values
merely to get agreement.

## Compatibility and acceptance matrix

E = executed characterization; S = executed seed conformance; P = proposed;
B = blocked by absent runtime/independent build. All P/B rows are release gates.

| Family / status | Required inputs or sequences | Oracle / acceptance |
| --- | --- | --- |
| Policy precedence S | empty; allow/ask/deny | Written precedence; 3 seed cases. Expand all 121 sequences of lengths 0..4 and permutations P. |
| Classification S | failed/bad_input; failed/timeout | bad_input normative; timeout pending D12. |
| Evidence E/P | no outcome; wrong task; mismatched item env; wrong kind; duplicate IDs; conflicting reports | No PASS without trusted joined execution result. Full outcome selection rule requires D9. |
| I13 B | agent labels report harness; nonexistent invocation; replayed record; altered stdout | Trusted store rejects or verifier refuses; test real identity boundary. |
| I14 B | change one byte but retain old hash; edit criteria; clean/dirty tree | Recompute bytes, refuse changed baseline; no effect/checkpoint after tamper. |
| Promotion E/P | empty bundle + PASS; revision/policy mismatch; stale/reused attestation | Reject without exact authenticated verdict tuple, under D9. |
| Paths E/P/B | missing path; ..; absolute, backslash, UNC, case, glob, symlink/junction swap | D10 portable grammar plus real resolved-root enforcement; no out-of-root write. |
| Tool-policy P | mismatched name/version/idempotency; unknown capability; multiple capabilities; missing approval/budget | One admission decision; deny wins; no journal outcome/effect on refusal. |
| Budget E/P | commit twice; rollback twice; cross-ledger; fabricated token; concurrent commit/rollback | D11: exactly one settlement; nonnegative balances; total committed + live reservations <= cap. |
| Approval P/B | expiry equality; future grant; mixed timezone; wrong capability/task/hash; concurrent consume; restart | Exactly one eligible use, bound to policy/intent; no reset on restart. |
| States E/P | all 15x15 state pairs; unresolved execution; unfrozen criteria; security stop at every live state | D12 total state relation; guard and query agree; blocked transition emits no effect. |
| Failure E/P | 3 idempotencies x 5 outcomes x 11 error choices including null = 165 cases | D12 total table including invalid combinations; unknown non-idempotent never replayed. |
| Checkpoint E/P | duplicate ID; cross-project parent; invalidate ancestor after descendants; stale head | D13 longest valid prefix; explicit invalidation/staleness distinction. |
| Crash B | kill before intent durability, after intent, after effect, before outcome, during promotion | Durable intent precedes effect; uncertain effects reconciled; no blind replay. |
| Wire P | unknown fields/enums; null/missing; bool-as-int; NaN; timezone; Unicode normalization; version mismatch | D14 explicit rejection/coercion policy, exact canonical bytes. |
| Mutation P | remove guard, trust producer label, swap deny priority, allow settlement replay | Every named safety mutant killed by at least one normative vector. |

Acceptance requires both implementations pass every normative case, zero pending
blocking decisions, zero unsupported operations/skips, and recorded counterexample
adjudication. Repeat seeded generated cases with recorded seeds (default 10,000
sequences per stateful family); this is a sampling budget, not a proof. Require
independent boundary tests for I13/I14/I8/I9 and every named safety mutation killed.
Any shared helper leak or source exposure invalidates the independence claim.

## Exact commands and file-level work

EXECUTED/available from F:\cffmam in PowerShell:

```powershell
python -m pytest tests/test_task_contract.py tests/test_tool_contract.py tests/test_policy_contract.py tests/test_evidence_contract.py tests/test_checkpoint_contract.py tests/test_failure_contract.py
python -m pytest tests/audit -q
python compatibility/run.py --vectors compatibility/vectors.json --report compatibility/results-primary.json -- python compatibility/primary_adapter.py
```

Full-suite reproduction with a fresh workspace-local temporary directory:

```powershell
$auditTemp = Join-Path 'F:\cffmam\.pytest_cache' ('compat-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $auditTemp) { throw 'Expected a fresh test directory' }
python -m pytest --basetemp $auditTemp
```

The audit tests intentionally characterize unsafe behavior and must not be counted
as safety acceptance. When fixes land, invert or replace their assertions with
normative negative tests rather than preserving unsafe behavior for compatibility.

PROPOSED after B delivers an adapter binary (command is not runnable yet):

```powershell
python compatibility/run.py --vectors compatibility/vectors.json --report compatibility/results-secondary.json -- F:\csef-independent\bin\adapter.exe
```

PROPOSED files: compatibility/protocol-v1.json; vectors/{wire,task,tool,policy,
evidence,checkpoint,failure,crash}.json; manifest.json; mutations.json;
adapters/secondary (owned by B). EXECUTED: tests/compatibility/test_runner.py checks
success, mismatch, pending, malformed output, nonzero adapter exit and empty-suite
rejection. PROPOSED additional runner checks: timeout, duplicate/invalid vectors,
state isolation, output/resource bounds and exact JSON typing (Python equality
currently equates true and 1; the current string-result vectors do not exercise it).

PROPOSED production changes, only after decision adjudication:

* common.py: canonical serialization, explicit wire strictness; deep immutable values.
* task.py: guards inside transitions, consistent terminal relation, requirement links.
* tool.py: bind invocation identity/idempotency to registry; closed input contract.
* policy.py: canonical resource checks, explicit unknown-deny; durable token-bound settlement.
* evidence.py: verified execution joins, content validation, deterministic result selection.
* checkpoint.py: trusted promotion authorization and persistent invalidation/ancestor semantics.
* failure.py: exhaustive classification/recovery table and retry budgets/diagnosis linkage.

## Proposed decision records (not ratified)

| Decision | Question and recommended default | Owner / deadline / blocker |
| --- | --- | --- |
| D9 | What authorizes PASS? Trusted verifier result binds task, full revision, baseline bytes digest, bundle digest, policy, environment, command and invocation; no caller enum as authority. Define canonical hashing and attestation trust anchor. | Contract/security steward; before oracle freeze; blocks R1/R9. |
| D10 | Who owns path and admission semantics? Gateway validates canonical relative resources, rejects unresolved paths, composes all capabilities, policy, approvals and reservations before effect. Final resource check must resist symlink races. | Gateway owner; before B implementation; blocks R3/R8. |
| D11 | What is settlement identity/durability? Ledger-owned persistent token with atomic single settlement; reject repeated/foreign settlement; retain uncertain reservations until reconciliation. Define money precision/rounding and project aggregation. | Accounting owner; before stateful vectors; blocks R2. |
| D12 | Which failures dominate and how do states propagate? Reject contradictory outcome/error pairs; quarantine dominates; policy denial never auto-replays; define timeout, cancellation, bad_input mapping and security terminal exit. | Recovery owner; before table freeze; blocks R4/R7. |
| D13 | Can descendants survive invalidation? Default valid head is longest unbroken valid prefix; stale differs from invalid; revalidation creates events, not silent mutation. | State owner; before recovery vectors; blocks R5. |
| D14 | What exact wire language is shared? Strict JSON, finite decimal strings, UTC-aware times, full Git identity, closed versioned schemas, no coercion; settle glob/case/Unicode rules explicitly. | Schema owner; before packet freeze; blocks R6/R10. |

Additional contradictions requiring steward resolution: evidence section 4 permits
FAIL or STALE for environment drift; section 6 calls all listed anomalies quarantine.
Evidence section 9 says intent/outcome in one transaction, while I8 requires durable
intent before external effect (an uncommitted transaction cannot provide that).
Checkpoint section 7 describes rollback as FAILED and also AWAITING_HUMAN.
Failure section 3 prohibits a third attempt but asks for three attempt reports.
Network registration rejects NETWORK + network=True but accepts NETWORK + False:
the schema does not identify a separately authorized network broker. Define that
architecture before treating either combination as proof of network confinement.

## Accountable next action

Close D9 first with a negative end-to-end acceptance trace: agent-originated report
claiming harness identity, no trusted successful execution -> no PASS and no
checkpoint. Freeze this oracle, repair A under it, then hand the source-blind
packet to B. D11 and D10 are parallel release blockers. Do not certify Step 5 from
two implementations agreeing on the existing 48 tests.
