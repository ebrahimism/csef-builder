"""Contract 40 — a forged or unattested report must never produce a PASS."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from csef_contracts.common import Refused, Verdict
from csef_contracts.evidence import EvidenceKind, EvidenceRecord, compute_verdict
from csef_contracts.task import Criterion, CriterionType
from csef_contracts.verification import Controller, HarnessJournal
from support import (
    ENV_FP,
    NOW,
    OTHER_ENV,
    OTHER_REV,
    POLICY_HASH,
    REV,
    acceptance,
    bundle,
    criteria,
    evidence,
    harness_record,
    journal_for,
    make_task,
    passing_journal,
    sha,
    verdict_inputs,
)


def test_agent_produced_evidence_cannot_be_constructed() -> None:
    with pytest.raises(ValidationError):
        EvidenceRecord(
            evidence_id="ev-00009",
            kind=EvidenceKind.TEST_REPORT,
            criterion_id="AUTH-001-T1",
            producer="agent",
            invocation_id="inv-000001",
            source_revision=REV,
            env_fingerprint=ENV_FP,
            sandbox_id="sbx-runner-01",
            captured_at=NOW,
            content_hash=sha("fake"),
            size_bytes=10,
        )


def test_missing_evidence_is_a_failure_not_a_pass() -> None:
    task = make_task()
    assert compute_verdict(task, bundle(()), verdict_inputs(), passing_journal()) is Verdict.FAIL


def test_harness_label_without_execution_record_yields_fail() -> None:
    """``a01``: metadata says 'harness'; the journal has never heard of the invocation."""
    task = make_task()
    items = (evidence("AUTH-001-T1"), evidence("AUTH-001-T2"))
    assert compute_verdict(task, bundle(items), verdict_inputs(), HarnessJournal()) is Verdict.FAIL


def test_execution_record_for_another_revision_does_not_attest() -> None:
    task = make_task()
    items = (evidence("AUTH-001-T1"), evidence("AUTH-001-T2"))
    stale_journal = journal_for("AUTH-001-T1", "AUTH-001-T2", revision=OTHER_REV)
    assert compute_verdict(task, bundle(items), verdict_inputs(), stale_journal) is Verdict.FAIL


def test_failed_execution_record_cannot_attest_success() -> None:
    task = make_task()
    items = (evidence("AUTH-001-T1"), evidence("AUTH-001-T2"))
    journal = HarnessJournal()
    journal.append(harness_record("AUTH-001-T1", execution_status="failed"))
    journal.append(harness_record("AUTH-001-T2"))
    assert compute_verdict(task, bundle(items), verdict_inputs(), journal) is Verdict.FAIL


def test_content_hash_must_match_the_captured_stdout() -> None:
    task = make_task()
    items = (evidence("AUTH-001-T1"), evidence("AUTH-001-T2"))
    journal = HarnessJournal()
    journal.append(harness_record("AUTH-001-T1", stdout_hash=sha("some-other-output")))
    journal.append(harness_record("AUTH-001-T2"))
    assert compute_verdict(task, bundle(items), verdict_inputs(), journal) is Verdict.FAIL


def test_other_task_bundle_cannot_verify() -> None:
    """``a02``."""
    task = make_task()
    items = (evidence("AUTH-001-T1"), evidence("AUTH-001-T2"))
    foreign = bundle(items, task_id="T-9999")
    assert compute_verdict(task, foreign, verdict_inputs(), passing_journal()) is Verdict.FAIL


def test_record_environment_drift_is_a_failure() -> None:
    """``a03``: the bundle claims a clean env while its records were captured elsewhere."""
    task = make_task()
    items = (evidence("AUTH-001-T1", env=OTHER_ENV), evidence("AUTH-001-T2"))
    assert compute_verdict(task, bundle(items), verdict_inputs(), passing_journal()) is Verdict.FAIL


def test_evidence_from_another_revision_is_a_failure() -> None:
    task = make_task()
    items = (evidence("AUTH-001-T1", revision=OTHER_REV), evidence("AUTH-001-T2", revision=OTHER_REV))
    assert compute_verdict(task, bundle(items), verdict_inputs(), passing_journal()) is Verdict.FAIL


def test_environment_drift_marks_evidence_stale() -> None:
    task = make_task()
    items = (evidence("AUTH-001-T1"), evidence("AUTH-001-T2"))
    assert compute_verdict(task, bundle(items, env=OTHER_ENV), verdict_inputs(), passing_journal()) is Verdict.STALE


def test_tampered_baseline_is_detected() -> None:
    task = make_task()
    items = (evidence("AUTH-001-T1"), evidence("AUTH-001-T2"))
    tampered = bundle(items, baseline=sha("baseline-attacker"))
    assert compute_verdict(task, tampered, verdict_inputs(), passing_journal()) is Verdict.TAMPER_SUSPECTED


def test_attested_bundle_passes() -> None:
    task = make_task()
    items = (evidence("AUTH-001-T1"), evidence("AUTH-001-T2"))
    assert compute_verdict(task, bundle(items), verdict_inputs(), passing_journal()) is Verdict.PASS


def test_non_executable_criterion_forces_review() -> None:
    mixed = acceptance(
        criteria_=criteria() + (Criterion(id="AUTH-001-T3", type=CriterionType.HUMAN),),
    )
    task = make_task(acceptance_=mixed)
    items = (evidence("AUTH-001-T1"), evidence("AUTH-001-T2"), evidence("AUTH-001-T3"))
    assert compute_verdict(task, bundle(items), verdict_inputs(), passing_journal()) is Verdict.REVIEW


def test_truncated_output_is_not_evidence() -> None:
    task = make_task()
    items = (
        evidence("AUTH-001-T1").model_copy(update={"truncated": True}),
        evidence("AUTH-001-T2"),
    )
    assert compute_verdict(task, bundle(items), verdict_inputs(), passing_journal()) is Verdict.FAIL


def test_only_one_criterion_covered_is_not_enough() -> None:
    task = make_task()
    assert compute_verdict(task, bundle((evidence("AUTH-001-T1"),)), verdict_inputs(), passing_journal()) is Verdict.FAIL


def test_controller_issues_no_permit_without_attestation() -> None:
    """The public boundary: no journal join, no permit, no exception to argue about."""
    task = make_task()
    items = (evidence("AUTH-001-T1"), evidence("AUTH-001-T2"))
    controller = Controller(HarnessJournal())
    with pytest.raises(Refused, match="no permit issued"):
        controller.verify(task, bundle(items), verdict_inputs(), at=NOW)


def test_controller_issues_a_permit_for_an_attested_bundle() -> None:
    task = make_task()
    items = (evidence("AUTH-001-T1"), evidence("AUTH-001-T2"))
    controller = Controller(passing_journal())
    permit = controller.verify(task, bundle(items), verdict_inputs(), at=NOW)
    assert permit.verdict is Verdict.PASS
    assert permit.commit == REV
    assert permit.policy_hash == POLICY_HASH


def test_journal_refuses_two_records_for_one_invocation() -> None:
    journal = HarnessJournal()
    journal.append(harness_record("AUTH-001-T1"))
    with pytest.raises(Refused, match="already has a journal record"):
        journal.append(harness_record("AUTH-001-T1"))
