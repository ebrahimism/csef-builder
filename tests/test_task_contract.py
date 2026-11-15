"""Contract 10 — the state machine refuses illegal moves and ambiguity blocks execution."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from csef_contracts.task import (
    Criterion,
    CriterionType,
    TaskState,
    apply_transitions,
)
from csef_contracts.common import Refused
from support import NOW, acceptance, make_task


def test_illegal_transition_is_refused() -> None:
    task = make_task()
    with pytest.raises(Refused, match="not allowed"):
        task.transition(TaskState.DONE)


def test_terminal_state_has_no_exit() -> None:
    task = make_task()
    for target in (TaskState.PLANNED, TaskState.PREPARED):
        task = task.transition(target)
    terminal = task.model_copy(update={"state": TaskState.DONE})
    with pytest.raises(Refused, match="terminal"):
        terminal.transition(TaskState.EXECUTING)


def test_ambiguity_blocks_execution() -> None:
    task = make_task(
        state=TaskState.AUTHORIZED,
        open_decisions=("password hash: bcrypt-12 or argon2id?",),
    )
    with pytest.raises(Refused, match="BLOCKED_ON_AMBIGUITY"):
        task.assert_ready_to_execute()


def test_execution_requires_an_executable_criterion() -> None:
    human_only = acceptance(
        criteria_=(Criterion(id="UX-001-T1", type=CriterionType.HUMAN),),
        requirement_id="UX-001",
    )
    task = make_task(state=TaskState.AUTHORIZED, acceptance_=human_only)
    with pytest.raises(Refused, match="no executable acceptance criterion"):
        task.assert_ready_to_execute()


def test_executable_criterion_needs_target_and_exit_code() -> None:
    with pytest.raises(ValidationError):
        Criterion(id="AUTH-001-T9", type=CriterionType.EXECUTABLE, runner="pytest")


def test_transition_log_records_every_step() -> None:
    task, log = apply_transitions(
        make_task(),
        [TaskState.PLANNED, TaskState.PREPARED],
        NOW,
    )
    assert task.state is TaskState.PREPARED
    assert [(entry.from_state, entry.to_state) for entry in log] == [
        (TaskState.CREATED, TaskState.PLANNED),
        (TaskState.PLANNED, TaskState.PREPARED),
    ]
