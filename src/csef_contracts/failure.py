"""Contract 60: failure taxonomy, recovery planning, and ambiguity blocking."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import StringConstraints

from .common import Contract, ExecutionStatus, Idempotency
from .tool import ErrorClass, Invocation

EventId = Annotated[str, StringConstraints(pattern=r"^fx-[0-9]{5}$")]


class FailureClass(StrEnum):
    TRANSIENT = "transient"
    POLICY_DENIED = "policy_denied"
    BAD_INPUT = "bad_input"
    ENVIRONMENT = "environment"
    PRODUCT_BUG = "product_bug"
    SPEC_AMBIGUITY = "spec_ambiguity"
    TEST_DEFECT = "test_defect"
    BUDGET_EXHAUSTED = "budget_exhausted"
    SANDBOX_VIOLATION = "sandbox_violation"
    TAMPER_SUSPECTED = "tamper_suspected"
    UNKNOWN = "unknown"


class RecoveryAction(StrEnum):
    REPLAY = "replay"
    RETRY_TRANSIENT = "retry_transient"
    DIAGNOSE = "diagnose"
    ESCALATE = "escalate"
    STOP_UNKNOWN = "stop_unknown"
    QUARANTINE = "quarantine"


class FailureEvent(Contract):
    event_id: EventId
    task_id: Annotated[str, StringConstraints(pattern=r"^T-[0-9]{4}$")]
    failure_class: FailureClass
    fingerprint: Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
    attempt: int
    at: datetime


class AmbiguityBlock(Contract):
    """An agent may not move past this by guessing (I12 / AMBIGUITY-BLOCK)."""

    question: str
    options: tuple[str, ...] = ()
    blocking_decision: str
    why_it_matters: str
    guessed: Literal[False] = False


_MAX_TRANSIENT = 4


def plan_recovery(invocation: Invocation, outcome: ExecutionStatus, error_class: ErrorClass | None) -> RecoveryAction:
    """The decision table for a crashed or failed invocation.

    The dangerous case is a non-idempotent effect whose outcome is unknown: replaying it
    may duplicate an effect, so the contract demands a human.
    """
    if outcome is ExecutionStatus.OK:
        raise ValueError("plan_recovery is only meaningful for a failed or unknown outcome")

    if error_class is ErrorClass.SANDBOX_VIOLATION:
        return RecoveryAction.QUARANTINE
    if error_class is ErrorClass.POLICY_DENIED:
        # An explicit denial outranks an unknown outcome: a denied call was never
        # authorised, so replaying it is not a recovery plan (``a17``).
        return RecoveryAction.ESCALATE
    if outcome is ExecutionStatus.UNKNOWN:
        if invocation.idempotency is Idempotency.NON_IDEMPOTENT:
            return RecoveryAction.STOP_UNKNOWN
        return RecoveryAction.REPLAY
    if error_class is ErrorClass.TRANSIENT:
        return RecoveryAction.RETRY_TRANSIENT
    if error_class is ErrorClass.PRODUCT_BUG:
        return RecoveryAction.DIAGNOSE
    if error_class in (ErrorClass.ENVIRONMENT, ErrorClass.BUDGET_EXHAUSTED):
        return RecoveryAction.ESCALATE
    if error_class is ErrorClass.BAD_INPUT:
        return RecoveryAction.DIAGNOSE
    return RecoveryAction.STOP_UNKNOWN


def next_attempt_allowed(fingerprints: list[str], max_identical: int = 2) -> bool:
    """The same failure twice means the next attempt needs a new diagnosis, not a new try."""
    if not fingerprints:
        return True
    most_common = max(fingerprints.count(f) for f in set(fingerprints))
    return most_common < max_identical


def classify_failure(error_class: ErrorClass | None, outcome: ExecutionStatus) -> FailureClass:
    if error_class is ErrorClass.SANDBOX_VIOLATION:
        return FailureClass.SANDBOX_VIOLATION
    if error_class is ErrorClass.POLICY_DENIED:
        return FailureClass.POLICY_DENIED
    if error_class is ErrorClass.TRANSIENT:
        return FailureClass.TRANSIENT
    if error_class is ErrorClass.BUDGET_EXHAUSTED:
        return FailureClass.BUDGET_EXHAUSTED
    if error_class is ErrorClass.ENVIRONMENT:
        return FailureClass.ENVIRONMENT
    if error_class is ErrorClass.PRODUCT_BUG:
        return FailureClass.PRODUCT_BUG
    if error_class is ErrorClass.BAD_INPUT:
        return FailureClass.BAD_INPUT
    if outcome is ExecutionStatus.UNKNOWN:
        return FailureClass.UNKNOWN
    return FailureClass.UNKNOWN
