"""Authority boundary: the only path from evidence to a valid checkpoint.

Two things are deliberately absent from this module's API:

* a way for a caller to hand in a verdict;
* a way to obtain a permit without a matching record in the trusted journal.

If either existed, "the agent cannot approve its own work" would be a sentence in a
document instead of a property of the code.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import StringConstraints

from .common import Contract, GitSha, Refused, Sha256, Verdict
from .evidence import EvidenceBundle, VerificationRecord, VerdictInputs, compute_verdict
from .task import Task


class HarnessJournal:
    """Append-only log written by the harness process only.

    Keyed by ``invocation_id``: one invocation, one record. A duplicate is refused
    because two records for one invocation means two claims about one execution.
    """

    def __init__(self) -> None:
        self._records: dict[str, VerificationRecord] = {}

    def append(self, record: VerificationRecord) -> None:
        if record.invocation_id in self._records:
            raise Refused(f"invocation {record.invocation_id} already has a journal record")
        self._records[record.invocation_id] = record

    def record_for(self, invocation_id: str) -> VerificationRecord | None:
        return self._records.get(invocation_id)

    def __len__(self) -> int:
        return len(self._records)

    def invocations(self) -> tuple[str, ...]:
        return tuple(sorted(self._records))


class VerificationPermit(Contract):
    """Minted by the controller after a PASS. Bound to everything the checkpoint will claim."""

    permit_id: Annotated[str, StringConstraints(pattern=r"^pm-[0-9a-f]{4}$")]
    task_id: Annotated[str, StringConstraints(pattern=r"^T-[0-9]{4}$")]
    commit: GitSha
    bundle_hash: Sha256
    policy_hash: Sha256
    baseline_hash: Sha256
    env_fingerprint: Sha256
    verdict: Literal[Verdict.PASS] = Verdict.PASS
    issued_at: datetime


class Controller:
    """The public boundary.

    ``verify`` is the only producer of a permit, and ``promote`` is the only consumer.
    A caller can construct a ``VerificationPermit`` object directly only by lying about
    every hash it binds — which changes the checkpoint, so the lie is visible.
    """

    def __init__(self, journal: HarnessJournal) -> None:
        self.journal = journal

    def verify(self, task: Task, bundle: EvidenceBundle, inputs: VerdictInputs, *, at: datetime) -> VerificationPermit:
        verdict = compute_verdict(task, bundle, inputs, self.journal)
        if verdict is not Verdict.PASS:
            raise Refused(f"verification verdict is {verdict.value}; no permit issued")
        return VerificationPermit(
            permit_id="pm-" + bundle.chain_head[-4:],
            task_id=task.task_id,
            commit=bundle.source_revision,
            bundle_hash=bundle.chain_head,
            policy_hash=bundle.policy_hash,
            baseline_hash=bundle.baseline_hash,
            env_fingerprint=bundle.env_fingerprint,
            issued_at=at,
        )
