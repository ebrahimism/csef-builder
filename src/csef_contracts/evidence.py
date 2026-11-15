"""Contract 40: evidence. The harness is the only accepted producer (I3 / EVIDENCE-AUTHORITY).

A record alone proves nothing: it must join to a trusted ``VerificationRecord`` in the
harness journal (same invocation, same revision, execution status ok). Without that join,
metadata is just metadata — see ``a01``/``a04`` in ``tests/audit/test_residual_gaps.py``.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, StringConstraints

from .common import Contract, GitSha, Producer, Sha256, Verdict
from .task import Criterion, CriterionType, Task

if TYPE_CHECKING:
    from .verification import HarnessJournal

InvocationId = Annotated[str, StringConstraints(pattern=r"^inv-[0-9]{6}$")]
CriterionId = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9]+-[0-9]{3}-T[0-9]+$")]


class EvidenceKind(StrEnum):
    TEST_REPORT = "test_report"
    EXIT_CODE = "exit_code"
    ARTIFACT = "artifact"
    METRIC = "metric"
    SCAN_REPORT = "scan_report"
    ENV_FINGERPRINT = "env_fingerprint"
    HUMAN_APPROVAL = "human_approval"


class EvidenceRecord(Contract):
    """A record captured by the harness.

    ``producer`` is a literal, not an enum field: an agent-produced record cannot even be
    constructed, so a forged report is a type error before it is a policy question.
    """

    evidence_id: Annotated[str, StringConstraints(pattern=r"^ev-[0-9]{5}$")]
    kind: EvidenceKind
    criterion_id: CriterionId
    producer: Literal[Producer.HARNESS] = Producer.HARNESS
    invocation_id: InvocationId
    source_revision: GitSha
    env_fingerprint: Sha256
    sandbox_id: Annotated[str, StringConstraints(pattern=r"^sbx-[a-z0-9-]{1,40}$")]
    captured_at: datetime
    content_hash: Sha256
    size_bytes: int = Field(ge=0)
    truncated: bool = False


class VerificationRecord(Contract):
    """The verifier's own account of one verification run.

    Fields alone do not make a record forge-proof; write access, ordering and storage
    integrity are part of the trust model (docs/contracts/40-evidence.md §9).
    """

    harness_record_id: Annotated[str, StringConstraints(pattern=r"^hr-[0-9]{6}$")]
    invocation_id: InvocationId
    task_id: Annotated[str, StringConstraints(pattern=r"^T-[0-9]{4}$")]
    source_commit_hash: GitSha
    acceptance_bundle_hash: Sha256
    policy_version_hash: Sha256
    sandbox_image_digest: Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
    dependency_lock_hash: Sha256
    command_spec_hash: Sha256
    captured_exit_code: int
    captured_stdout_hash: Sha256
    captured_stderr_hash: Sha256
    execution_status: Annotated[str, StringConstraints(pattern=r"^(ok|failed|unknown|cancelled|denied)$")]
    verification_verdict: Verdict
    recorded_at: datetime


class EvidenceBundle(Contract):
    bundle_id: Annotated[str, StringConstraints(pattern=r"^eb-[0-9]{5}$")]
    task_id: Annotated[str, StringConstraints(pattern=r"^T-[0-9]{4}$")]
    source_revision: GitSha
    baseline_hash: Sha256
    policy_hash: Sha256
    env_fingerprint: Sha256
    items: tuple[EvidenceRecord, ...] = ()
    chain_head: Sha256


class VerdictInputs(Contract):
    task_id: Annotated[str, StringConstraints(pattern=r"^T-[0-9]{4}$")]
    source_revision: GitSha
    baseline_hash: Sha256
    env_fingerprint: Sha256


def _evidence_for(bundle: EvidenceBundle, criterion_id: str) -> list[EvidenceRecord]:
    return [e for e in bundle.items if e.criterion_id == criterion_id]


_HASH_BOUND_KINDS = frozenset(
    {EvidenceKind.TEST_REPORT, EvidenceKind.ARTIFACT, EvidenceKind.SCAN_REPORT, EvidenceKind.METRIC}
)


def _joined(record: EvidenceRecord, journal: "HarnessJournal") -> bool:
    """True only if a trusted execution record attests this exact evidence."""
    execution = journal.record_for(record.invocation_id)
    if execution is None:
        return False
    if execution.source_commit_hash != record.source_revision:
        return False
    if execution.execution_status != "ok":
        return False
    if execution.verification_verdict is Verdict.FAIL:
        return False
    if record.kind in _HASH_BOUND_KINDS and execution.captured_stdout_hash != record.content_hash:
        return False
    return True


def compute_verdict(
    task: Task,
    bundle: EvidenceBundle,
    inputs: VerdictInputs,
    journal: "HarnessJournal",
) -> Verdict:
    """Fail-closed evaluation. Absence of evidence, or of its attestation, is a failure."""
    if bundle.task_id != task.task_id or inputs.task_id != task.task_id:
        return Verdict.FAIL
    if bundle.baseline_hash != task.acceptance.baseline_hash:
        return Verdict.TAMPER_SUSPECTED
    if inputs.baseline_hash != task.acceptance.baseline_hash:
        return Verdict.TAMPER_SUSPECTED
    if bundle.source_revision != inputs.source_revision:
        return Verdict.FAIL
    if bundle.env_fingerprint != inputs.env_fingerprint:
        return Verdict.STALE

    needs_review = False
    for criterion in task.acceptance.criteria:
        records = _evidence_for(bundle, criterion.id)
        if not records:
            return Verdict.FAIL
        if criterion.type is CriterionType.EXECUTABLE:
            fresh = [r for r in records if r.source_revision == inputs.source_revision]
            if not fresh:
                return Verdict.FAIL
            for record in fresh:
                if record.truncated:
                    return Verdict.FAIL
                if record.env_fingerprint != inputs.env_fingerprint:
                    return Verdict.FAIL
                if not _joined(record, journal):
                    return Verdict.FAIL
        else:
            needs_review = True
    return Verdict.REVIEW if needs_review else Verdict.PASS


def record_criterion_ids(criteria: tuple[Criterion, ...]) -> tuple[str, ...]:
    return tuple(c.id for c in criteria)
