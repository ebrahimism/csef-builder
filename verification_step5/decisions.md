# Proposed decision records — not adopted

All records are PROPOSED; owner roles are requested assignments, not accepted ownership. Required before a full Step 5 acceptance claim.

## ADR-S5-001 — authenticated verification and promotion (BLOCKING)

Owner: contract architect + verifier owner. Sources: I4/I13/I14, evidence §4/8/9, checkpoint §2.
Conflict: I4 requires signed verifier authority; evidence §8 proposes no signature for v1; models permit caller-declared metadata.
Alternatives: signed permit; unforgeable capability referencing protected single-writer durable store; unchecked enum (reject, violates I4).
Proposed default: protected verifier record plus single-use authority bound to task, full revision, baseline bytes manifest, policy version, environment, command, completed outcome and verified bundle digest. Decide whether cryptographic signatures are mandatory across this trust boundary. Reject caller-issued PASS as authority. Recompute actual content hashes; a hash chain without authenticated origin does not authenticate a writer.
Acceptance: missing/mismatched/replayed permit, changed bytes, failed/unknown execution and different revision cannot promote; crash-safe consume-and-promote. Decision remains open until representation and boundary are approved.

## ADR-S5-002 — authoritative transition and policy transaction (BLOCKING)

Owner: controller + policy owners. Sources: I1/I6/I8/I15, policy §5.
Proposed default: atomic guarded state transition; all capabilities resolved with deny > ask > allow; unknown capability always deny independently of fallback; missing required scope rejects. Approved ASK cannot soften DENY. Authorize exact invocation/capability/task/policy, reserve bounded cost, persist durable intent, then effect; cancellation/crash semantics require explicit state transitions.
Path default: reject absolute/dot-segment inputs, specify platform normalization and handle-based reparse checks; lexical checks alone cannot enforce containment.
Reservation alternatives: repeated terminal settlement refuses or returns original result; choose one. Both must reject foreign IDs and prevent additional budget release. Money scale/rounding/nonfinite rejection require canonical boundary definition.
Acceptance: I15 bypass, scope omission, traversal and duplicate/foreign settlement regressions; no effect on any rejection. No production behavior changed by this record.

## ADR-S5-003 — failure precedence and journal durability (BLOCKING)

Owner: recovery owner. Sources: failure §1/3/4/8, checkpoint §5, I8.
Proposed ordering: security quarantine; explicit policy denial stop/escalate; reconcile unknown effects according to verified idempotency; then transient/diagnosis handling. A forged invocation's own idempotency declaration is not sufficient authority. Define FAILED transient non-idempotent semantics explicitly.
Retain BAD_INPUT as named class. Timeout/cancelled mapping, total cross product, consecutive vs epoch-wide fingerprint count, retries/backoff remain decisions; do not silently use unused constants as normative values.
Durability: intent must commit before an effect; outcome commits afterward. A single database transaction spanning an arbitrary external effect cannot provide atomicity. Define reconciliation and deduplication, not an unsupported exactly-once claim.
Acceptance: all status/error/idempotency combinations have reviewed outcomes; crash traces establish durable intent and safe unknown handling.

## ADR-S5-004 — checkpoint validity, oracle and independence (BLOCKING)

Owner: contract owner + independent reviewer. Sources: I10/I11, checkpoint §3–5.
Proposed default: project-specific unique chain IDs; immutable snapshots plus separate durable invalidation events; STALE distinct from invalid; valid head is valid prefix and no traversal through stale ancestor. Define policy reevaluation separately from code/baseline invalidation.
Oracle changes require rule citation, competing readings, counterexample, approved rationale and versioned expected cases. Agreement with v1 is never the deciding rationale. Implementer must receive only frozen docs/protocol/neutral fixtures before authoring; current reference cannot meet that provenance condition.
Acceptance: two frozen implementations conform, all high/critical ambiguities resolved, valid-prefix/restart tests pass, selected critical mutants killed and held-out negative cases pass. Pilot status remains incomplete.
