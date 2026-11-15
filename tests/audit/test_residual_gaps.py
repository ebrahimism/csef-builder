"""Regression suite for the step-5 audit gaps (a01..a18).

Each probe used to *confirm* a defect. It now asserts the contract instead, and keeps the
original id so the traceability of the audit survives the fix.

Honest scope note: an in-process caller can still construct a ``VerificationPermit``
object by hand if it knows every bound hash. What the permit buys is that the forgery is
visible and must be consistent with the checkpoint it claims; what it does not buy is
process isolation. That remains I2's job (VM boundary), not this module's.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from csef_contracts import (
    BudgetLedger,
    CheckpointChain,
    Decision,
    EvidenceBundle,
    InvalidationReason,
    Policy,
    Refused,
    TaskState,
    Verdict,
    compute_verdict,
    decide,
    promote,
)
from csef_contracts.common import ExecutionStatus, Idempotency
from csef_contracts.failure import classify_failure, plan_recovery
from csef_contracts.tool import ErrorClass, Invocation, ToolRegistry
from csef_contracts.verification import Controller, HarnessJournal
from support import (
    NOW,
    OTHER_ENV,
    OTHER_REV,
    POLICY_HASH,
    REV,
    bundle,
    evidence,
    journal_for,
    make_policy,
    make_task,
    passing_journal,
    sha,
    tool_spec,
    verdict_inputs,
)


def passing_bundle(**kwargs):
    return bundle((evidence("AUTH-001-T1"), evidence("AUTH-001-T2")), **kwargs)


def test_a01_unattested_metadata_no_longer_yields_pass():
    # Harness-labelled records without a journal entry: metadata, not evidence.
    assert compute_verdict(make_task(), passing_bundle(), verdict_inputs(), HarnessJournal()) is Verdict.FAIL


def test_a02_other_task_bundle_no_longer_yields_pass():
    foreign = bundle((evidence("AUTH-001-T1"), evidence("AUTH-001-T2")), task_id="T-9999")
    assert compute_verdict(make_task(), foreign, verdict_inputs(), passing_journal()) is Verdict.FAIL


def test_a03_record_environment_drift_no_longer_yields_pass():
    drifted = bundle((evidence("AUTH-001-T1", env=OTHER_ENV), evidence("AUTH-001-T2")))
    assert compute_verdict(make_task(), drifted, verdict_inputs(), passing_journal()) is Verdict.FAIL


def test_a04_empty_bundle_cannot_promote():
    task = make_task(state=TaskState.CHECKPOINTING)
    with pytest.raises(Refused, match="no permit issued"):
        Controller(HarnessJournal()).verify(task, bundle(()), verdict_inputs(), at=NOW)


def test_a05_revision_and_policy_are_bound_into_the_permit():
    task = make_task(state=TaskState.CHECKPOINTING)
    b = passing_bundle()
    permit = Controller(passing_journal()).verify(task, b, verdict_inputs(), at=NOW)
    with pytest.raises(Refused, match="commit"):
        promote(task, b, permit, checkpoint_id="ck-0001", project_id="prj-alpha", parent=None,
                commit=OTHER_REV, policy_hash=POLICY_HASH, at=NOW)
    with pytest.raises(Refused, match="policy hash"):
        promote(task, b, permit, checkpoint_id="ck-0001", project_id="prj-alpha", parent=None,
                commit=REV, policy_hash=sha("other"), at=NOW)


def test_a06_replayed_rollback_no_longer_creates_capacity():
    ledger = BudgetLedger("1", "1")
    reservation = ledger.reserve("1")
    ledger.rollback(reservation)
    with pytest.raises(Exception, match="already settled"):
        ledger.rollback(reservation)
    assert ledger.reserved == Decimal("0.0000")


def test_a07_foreign_reservation_cannot_settle_here():
    first, second = BudgetLedger("1", "1"), BudgetLedger("1", "1")
    with pytest.raises(Exception, match="another ledger"):
        second.commit(first.reserve("1"), "1")


def test_a08_dotdot_path_is_refused():
    with pytest.raises(Refused, match=r"'\.\.'|segment"):
        decide(make_policy(), "edit_project_files", path="src/../../outside.txt")


def test_a09_missing_path_cannot_skip_scope():
    assert decide(make_policy(), "edit_project_files") is Decision.DENY


def test_a10_transition_enforces_the_ambiguity_guard():
    task = make_task(state=TaskState.AUTHORIZED, open_decisions=("unresolved",))
    with pytest.raises(Refused, match="BLOCKED_ON_AMBIGUITY"):
        task.transition(TaskState.EXECUTING)


def test_a11_invalidation_is_visible_to_the_chain():
    chain = CheckpointChain()
    checkpoint = _checkpoint()
    chain.append(checkpoint)
    chain.invalidate(checkpoint.checkpoint_id, InvalidationReason.VERIFY_FAILED)
    assert chain.valid_head is None


def test_a12_cross_project_and_duplicate_ids_are_refused():
    chain = CheckpointChain()
    first = _checkpoint()
    chain.append(first)
    with pytest.raises(Refused, match="cannot join chain"):
        chain.append(first.model_copy(update={"checkpoint_id": "ck-0002", "parent": "ck-0001", "project_id": "prj-other"}))
    with pytest.raises(Refused, match="duplicate checkpoint id"):
        chain.append(first.model_copy(update={"checkpoint_id": "ck-0001", "parent": "ck-0001"}))


def test_a13_policy_is_deeply_frozen():
    policy = make_policy()
    with pytest.raises((AttributeError, TypeError)):
        policy.tools.clear()  # type: ignore[attr-defined]


def test_a14_allow_default_is_not_constructible():
    with pytest.raises(ValidationError):
        Policy(policy_version=1, policy_hash=POLICY_HASH, execution_default=Decision.ALLOW)


def test_a15_undeclared_tool_parameter_is_refused():
    registry = ToolRegistry()
    registry.register(tool_spec())
    with pytest.raises(Refused, match="undeclared parameter"):
        registry.validate_call("run_tests", {"target": "tests", "undeclared": "value"})


def test_a16_bad_input_keeps_its_class():
    assert classify_failure(ErrorClass.BAD_INPUT, ExecutionStatus.FAILED).value == "bad_input"


def test_a17_denial_outranks_unknown_outcome():
    invocation = Invocation(
        invocation_id="inv-000001", task_id="T-0042", tool="run_tests", tool_version=1, attempt=1,
        idempotency_key=sha("key"), input_hash=sha("input"), effects=frozenset(),
        idempotency=Idempotency.READ_ONLY,
    )
    assert plan_recovery(invocation, ExecutionStatus.UNKNOWN, ErrorClass.POLICY_DENIED).value == "escalate"


def test_a18_halted_security_state_allows_human_abandonment():
    task = make_task().model_copy(update={"state": TaskState.HALTED_FOR_SECURITY})
    assert task.can_transition_to(TaskState.ABANDONED)
    assert task.transition(TaskState.ABANDONED).state is TaskState.ABANDONED


def _checkpoint():
    task = make_task(state=TaskState.CHECKPOINTING)
    b = passing_bundle()
    permit = Controller(passing_journal()).verify(task, b, verdict_inputs(), at=NOW)
    return promote(task, b, permit, checkpoint_id="ck-0001", project_id="prj-alpha",
                   parent=None, commit=REV, policy_hash=POLICY_HASH, at=NOW)
