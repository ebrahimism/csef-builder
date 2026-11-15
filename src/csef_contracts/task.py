"""Contract 10: task, acceptance criteria, profile, and the state machine guards."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator

from .common import Contract, GitSha, Refused, Sha256, Slug

TaskId = Annotated[str, StringConstraints(pattern=r"^T-[0-9]{4}$")]
CriterionId = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9]+-[0-9]{3}-T[0-9]+$")]


class Profile(StrEnum):
    QUICK = "quick"
    STANDARD = "standard"
    ADVANCED = "advanced"


class CriterionType(StrEnum):
    EXECUTABLE = "executable"
    EVIDENCE_BASED = "evidence_based"
    HUMAN = "human"


class TaskState(StrEnum):
    CREATED = "created"
    PLANNED = "planned"
    PREPARED = "prepared"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    COLLECTING = "collecting"
    VERIFYING = "verifying"
    CHECKPOINTING = "checkpointing"
    DONE = "done"
    DIAGNOSING = "diagnosing"
    PATCHING = "patching"
    AWAITING_HUMAN = "awaiting_human"
    FAILED = "failed"
    ABANDONED = "abandoned"
    HALTED_FOR_SECURITY = "halted_for_security"


TERMINAL = frozenset({TaskState.DONE, TaskState.FAILED, TaskState.ABANDONED})

ALLOWED: dict[TaskState, frozenset[TaskState]] = {
    TaskState.CREATED: frozenset({TaskState.PLANNED}),
    TaskState.PLANNED: frozenset({TaskState.PREPARED}),
    TaskState.PREPARED: frozenset({TaskState.AUTHORIZED, TaskState.AWAITING_HUMAN}),
    TaskState.AUTHORIZED: frozenset({TaskState.EXECUTING}),
    TaskState.EXECUTING: frozenset(
        {TaskState.COLLECTING, TaskState.AWAITING_HUMAN, TaskState.HALTED_FOR_SECURITY}
    ),
    TaskState.COLLECTING: frozenset({TaskState.VERIFYING}),
    TaskState.VERIFYING: frozenset(
        {
            TaskState.CHECKPOINTING,
            TaskState.DIAGNOSING,
            TaskState.AWAITING_HUMAN,
            TaskState.HALTED_FOR_SECURITY,
            TaskState.FAILED,
        }
    ),
    TaskState.CHECKPOINTING: frozenset({TaskState.DONE}),
    TaskState.DIAGNOSING: frozenset({TaskState.PATCHING, TaskState.AWAITING_HUMAN, TaskState.FAILED}),
    TaskState.PATCHING: frozenset({TaskState.VERIFYING, TaskState.AWAITING_HUMAN}),
    TaskState.AWAITING_HUMAN: frozenset({TaskState.AUTHORIZED, TaskState.ABANDONED}),
    TaskState.HALTED_FOR_SECURITY: frozenset({TaskState.ABANDONED}),
    TaskState.DONE: frozenset(),
    TaskState.FAILED: frozenset(),
    TaskState.ABANDONED: frozenset(),
}


class Criterion(Contract):
    """A single acceptance criterion. Executable criteria are the only ones that can gate alone."""

    id: CriterionId
    type: CriterionType
    runner: Slug | None = None
    target: str | None = Field(default=None, max_length=400)
    expected_exit_code: int | None = None
    frozen: bool = True

    @model_validator(mode="after")
    def _executable_needs_target(self) -> Self:
        if self.type is CriterionType.EXECUTABLE:
            if self.runner is None or self.target is None or self.expected_exit_code is None:
                raise ValueError(f"{self.id}: executable criteria need runner, target and expected_exit_code")
        return self


class AcceptanceSpec(Contract):
    requirement_id: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9]+-[0-9]{3}$")]
    criteria: tuple[Criterion, ...] = Field(min_length=1)
    baseline_hash: Sha256
    frozen_at: datetime

    @model_validator(mode="after")
    def _unique_ids(self) -> Self:
        ids = [c.id for c in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("criteria ids must be unique within a requirement")
        return self

    @property
    def executable(self) -> tuple[Criterion, ...]:
        return tuple(c for c in self.criteria if c.type is CriterionType.EXECUTABLE)

    def all_executable(self) -> bool:
        return all(c.type is CriterionType.EXECUTABLE for c in self.criteria)


class Budget(Contract):
    max_patch_attempts: int = Field(ge=0, le=10)
    max_cost_usd: Decimal | None = Field(default=None, ge=0)
    max_wall_clock_s: int = Field(ge=1)
    max_tool_calls: int = Field(ge=1)

    def assert_cost_is_set(self) -> None:
        """I6: an unset budget means 'not configured', never 'unlimited'."""
        if self.max_cost_usd is None:
            raise Refused("budget.max_cost_usd is unset; cost-bearing execution may not start (I6)")


class Scope(Contract):
    writable_paths: tuple[str, ...] = Field(min_length=1)
    readonly_paths: tuple[str, ...] = ()
    max_files_changed: int = Field(ge=1)
    max_lines_changed: int = Field(ge=1)


class Task(Contract):
    task_id: TaskId
    requirement_ids: tuple[str, ...] = Field(min_length=1)
    profile: Profile
    objective: str = Field(min_length=1, max_length=2000)
    acceptance: AcceptanceSpec
    scope: Scope
    budget: Budget
    state: TaskState = TaskState.CREATED
    attempts: int = Field(default=0, ge=0)
    open_decisions: tuple[str, ...] = ()

    def can_transition_to(self, target: TaskState) -> bool:
        return target in ALLOWED[self.state]

    def transition(self, target: TaskState) -> "Task":
        """Move to *target*, refusing anything the contract does not allow.

        Readiness is enforced by the transition itself, not by a guard the caller may
        forget to invoke (``a10``: AUTHORIZED -> EXECUTING with open decisions).
        """
        if self.state in TERMINAL:
            raise Refused(f"{self.task_id}: {self.state} is terminal; start a new attempt instead")
        if not self.can_transition_to(target):
            raise Refused(f"{self.task_id}: transition {self.state} -> {target} is not allowed")
        if target is TaskState.EXECUTING:
            self.assert_ready_to_execute()
        return self.model_copy(update={"state": target})

    def assert_ready_to_execute(self) -> None:
        """Guards for AUTHORIZED -> EXECUTING. Ambiguity blocks, always (I12)."""
        if self.open_decisions:
            raise Refused(
                f"{self.task_id}: BLOCKED_ON_AMBIGUITY: unresolved decisions {list(self.open_decisions)!r}"
            )
        if not any(c.type is CriterionType.EXECUTABLE for c in self.acceptance.criteria):
            raise Refused(f"{self.task_id}: no executable acceptance criterion; nothing can gate a checkpoint")
        if not self.acceptance.criteria or not all(c.frozen for c in self.acceptance.criteria):
            raise Refused(f"{self.task_id}: acceptance criteria are not frozen (I5)")


class TransitionLog(Contract):
    """Append-only evidence that the machine only took legal steps."""

    task_id: TaskId
    from_state: TaskState
    to_state: TaskState
    at: datetime
    reason: str


def apply_transitions(task: Task, sequence: list[TaskState], at: datetime) -> tuple[Task, list[TransitionLog]]:
    """Apply a sequence of states and return the log. Any illegal step raises, never silently skips."""
    log: list[TransitionLog] = []
    current = task
    for target in sequence:
        before = current.state
        current = current.transition(target)
        log.append(
            TransitionLog(task_id=task.task_id, from_state=before, to_state=target, at=at, reason="sequence")
        )
    return current, log


def bind_acceptance(requirement_id: str, criteria: list[Criterion], baseline_hash: Sha256, at: datetime) -> AcceptanceSpec:
    """Freeze the baseline. A baseline that can still be edited is not a baseline."""
    return AcceptanceSpec(
        requirement_id=requirement_id,
        criteria=tuple(criteria),
        baseline_hash=baseline_hash,
        frozen_at=at,
    )
