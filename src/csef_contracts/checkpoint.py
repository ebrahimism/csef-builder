"""Contract 50: checkpoints — the only thing allowed to become 'valid project state'.

Promotion consumes a ``VerificationPermit``; it never accepts a caller's opinion of the
verdict (see ``a04``/``a05``).
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from .common import Contract, GitSha, Refused, Sha256, Verdict
from .evidence import EvidenceBundle
from .task import Task, TaskState
from .verification import VerificationPermit

CheckpointId = Annotated[str, StringConstraints(pattern=r"^ck-[0-9]{4}$")]
ProjectId = Annotated[str, StringConstraints(pattern=r"^prj-[a-z0-9-]{2,40}$")]


class Checkpoint(Contract):
    checkpoint_id: CheckpointId
    project_id: ProjectId
    parent: CheckpointId | None = None
    commit: GitSha
    requirements_satisfied: tuple[str, ...] = Field(min_length=1)
    task_id: Annotated[str, StringConstraints(pattern=r"^T-[0-9]{4}$")]
    evidence_bundle_hash: Sha256
    policy_hash: Sha256
    baseline_hash: Sha256
    env_fingerprint: Sha256
    schema_version: int = 1
    created_by: Literal["controller"] = "controller"
    created_at: datetime
    verdict: Literal[Verdict.PASS] = Verdict.PASS
    invalidated_by: str | None = None

    @property
    def valid(self) -> bool:
        return self.invalidated_by is None


def promote(
    task: Task,
    bundle: EvidenceBundle,
    permit: VerificationPermit,
    *,
    checkpoint_id: str,
    project_id: str,
    parent: str | None,
    commit: str,
    policy_hash: str,
    at: datetime,
) -> Checkpoint:
    """Create a checkpoint. Every precondition is checked here, not by the caller."""
    if task.state is not TaskState.CHECKPOINTING:
        raise Refused(f"{task.task_id}: only a task in CHECKPOINTING may be checkpointed (state={task.state})")
    if bundle.task_id != task.task_id:
        raise Refused("bundle belongs to another task")
    if permit.task_id != task.task_id:
        raise Refused("permit was issued for another task")
    if commit != bundle.source_revision:
        raise Refused("checkpoint commit differs from the revision the evidence was captured on")
    if permit.commit != commit:
        raise Refused("permit is bound to a different commit")
    if permit.bundle_hash != bundle.chain_head:
        raise Refused("permit is bound to a different evidence bundle")
    if policy_hash != bundle.policy_hash or permit.policy_hash != policy_hash:
        raise Refused("policy hash differs between permit, bundle and request")
    if bundle.baseline_hash != task.acceptance.baseline_hash:
        raise Refused("bundle was produced against a different acceptance baseline")
    if permit.baseline_hash != bundle.baseline_hash:
        raise Refused("permit is bound to a different acceptance baseline")
    if permit.env_fingerprint != bundle.env_fingerprint:
        raise Refused("permit is bound to a different environment fingerprint")
    return Checkpoint(
        checkpoint_id=checkpoint_id,
        project_id=project_id,
        parent=parent,
        commit=commit,
        requirements_satisfied=task.requirement_ids,
        task_id=task.task_id,
        evidence_bundle_hash=bundle.chain_head,
        policy_hash=policy_hash,
        baseline_hash=task.acceptance.baseline_hash,
        env_fingerprint=bundle.env_fingerprint,
        created_at=at,
    )


class InvalidationReason(StrEnum):
    BASELINE_CHANGED = "baseline_changed"
    UNAUTHORIZED_CODE_CHANGE = "unauthorized_code_change"
    VERIFY_FAILED = "verify_failed"
    SECURITY_INCIDENT = "security_incident"


def invalidate(checkpoint: Checkpoint, reason: InvalidationReason) -> Checkpoint:
    """Invalidation is a record, never a deletion. History is evidence too."""
    if checkpoint.invalidated_by is not None:
        raise Refused(f"{checkpoint.checkpoint_id} is already invalidated")
    return checkpoint.model_copy(update={"invalidated_by": reason.value})


class CheckpointChain:
    """One project, one linear chain. Experiments live in worktrees, not in history.

    The chain owns invalidation: mutating a returned copy (``a11``) changes nothing,
    because validity is computed from the chain's own records, not from a caller's object.
    """

    def __init__(self, project_id: str | None = None) -> None:
        self._items: list[Checkpoint] = []
        self._project_id = project_id

    def append(self, checkpoint: Checkpoint) -> None:
        if checkpoint.invalidated_by is not None:
            raise Refused(f"{checkpoint.checkpoint_id}: an invalidated checkpoint cannot be appended")
        if any(item.checkpoint_id == checkpoint.checkpoint_id for item in self._items):
            raise Refused(f"{checkpoint.checkpoint_id}: duplicate checkpoint id")
        if self._project_id is None:
            self._project_id = checkpoint.project_id
        elif checkpoint.project_id != self._project_id:
            raise Refused(
                f"{checkpoint.checkpoint_id}: project {checkpoint.project_id} cannot join chain of {self._project_id}"
            )
        expected_parent = self._items[-1].checkpoint_id if self._items else None
        if checkpoint.parent != expected_parent:
            raise Refused(
                f"{checkpoint.checkpoint_id}: parent {checkpoint.parent!r} != expected {expected_parent!r} (lineage must be linear)"
            )
        self._items.append(checkpoint)

    def invalidate(self, checkpoint_id: str, reason: InvalidationReason) -> Checkpoint:
        """Invalidate an entry *in the chain*. Descendants stop being resumable."""
        for index, item in enumerate(self._items):
            if item.checkpoint_id == checkpoint_id:
                updated = invalidate(item, reason)
                self._items[index] = updated
                return updated
        raise Refused(f"{checkpoint_id}: not part of this chain")

    @property
    def head(self) -> Checkpoint | None:
        return self._items[-1] if self._items else None

    @property
    def valid_prefix_end(self) -> Checkpoint | None:
        """Last checkpoint whose entire ancestry is valid."""
        last: Checkpoint | None = None
        for item in self._items:
            if item.valid:
                last = item
            else:
                break
        return last

    @property
    def valid_head(self) -> Checkpoint | None:
        return self.valid_prefix_end

    def is_resumable(self, checkpoint_id: str) -> bool:
        for item in self._items:
            if item.checkpoint_id == checkpoint_id:
                return item.valid and self.valid_prefix_end is not None and item == self.valid_prefix_end
        return False

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)
