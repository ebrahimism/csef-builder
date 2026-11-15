"""Contract 60 — recovery decisions for the cases that actually happen at 3am."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from csef_contracts.common import ExecutionStatus, Idempotency
from csef_contracts.failure import (
    AmbiguityBlock,
    FailureClass,
    RecoveryAction,
    classify_failure,
    next_attempt_allowed,
    plan_recovery,
)
from csef_contracts.tool import Effect, ErrorClass, Invocation
from support import sha


def invocation(idempotency: Idempotency) -> Invocation:
    return Invocation(
        invocation_id="inv-000042",
        task_id="T-0042",
        tool="run_tests",
        tool_version=1,
        attempt=2,
        idempotency_key=sha("idem-42"),
        input_hash=sha("input-42"),
        effects=frozenset({Effect.PROCESS}),
        idempotency=idempotency,
    )


def test_non_idempotent_unknown_outcome_must_not_be_replayed() -> None:
    action = plan_recovery(invocation(Idempotency.NON_IDEMPOTENT), ExecutionStatus.UNKNOWN, None)
    assert action is RecoveryAction.STOP_UNKNOWN


def test_idempotent_unknown_outcome_may_be_replayed() -> None:
    assert plan_recovery(invocation(Idempotency.IDEMPOTENT), ExecutionStatus.UNKNOWN, None) is RecoveryAction.REPLAY
    assert plan_recovery(invocation(Idempotency.READ_ONLY), ExecutionStatus.UNKNOWN, None) is RecoveryAction.REPLAY


def test_transient_failure_is_retried_but_product_bug_is_diagnosed() -> None:
    inv = invocation(Idempotency.READ_ONLY)
    assert plan_recovery(inv, ExecutionStatus.FAILED, ErrorClass.TRANSIENT) is RecoveryAction.RETRY_TRANSIENT
    assert plan_recovery(inv, ExecutionStatus.FAILED, ErrorClass.PRODUCT_BUG) is RecoveryAction.DIAGNOSE


def test_security_class_failures_quarantine_or_escalate() -> None:
    inv = invocation(Idempotency.READ_ONLY)
    assert plan_recovery(inv, ExecutionStatus.FAILED, ErrorClass.SANDBOX_VIOLATION) is RecoveryAction.QUARANTINE
    assert plan_recovery(inv, ExecutionStatus.DENIED, ErrorClass.POLICY_DENIED) is RecoveryAction.ESCALATE


def test_success_is_not_a_recovery_case() -> None:
    with pytest.raises(ValueError):
        plan_recovery(invocation(Idempotency.READ_ONLY), ExecutionStatus.OK, None)


def test_identical_failure_twice_blocks_the_third_attempt() -> None:
    fingerprints = [sha("same"), sha("same")]
    assert not next_attempt_allowed(fingerprints, max_identical=2)
    assert next_attempt_allowed([sha("a"), sha("b")], max_identical=2)


def test_ambiguity_block_cannot_claim_a_guess() -> None:
    with pytest.raises(ValidationError):
        AmbiguityBlock(
            question="which hash algorithm?",
            blocking_decision="hash algorithm",
            why_it_matters="migration cost later",
            guessed=True,
        )


def test_classification_keeps_security_classes_distinct() -> None:
    assert classify_failure(ErrorClass.SANDBOX_VIOLATION, ExecutionStatus.FAILED) is FailureClass.SANDBOX_VIOLATION
    assert classify_failure(None, ExecutionStatus.UNKNOWN) is FailureClass.UNKNOWN
