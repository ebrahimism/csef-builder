"""Contract 50 — a checkpoint is not a place where optimism is recorded."""
from __future__ import annotations

import pytest

from csef_contracts.checkpoint import (
    CheckpointChain,
    InvalidationReason,
    promote,
)
from csef_contracts.common import Refused, Verdict
from csef_contracts.task import TaskState
from csef_contracts.verification import Controller, HarnessJournal
from support import (
    NOW,
    OTHER_REV,
    POLICY_HASH,
    REV,
    bundle,
    evidence,
    journal_for,
    make_task,
    permit_for,
    sha,
    verdict_inputs,
)


def passing_bundle(**kwargs):
    return bundle((evidence("AUTH-001-T1"), evidence("AUTH-001-T2")), **kwargs)


def checkpoint(
    *,
    revision: str = REV,
    checkpoint_id: str = "ck-0001",
    project_id: str = "prj-alpha",
    parent: str | None = None,
):
    task = make_task(state=TaskState.CHECKPOINTING)
    b = bundle(
        (evidence("AUTH-001-T1", revision=revision), evidence("AUTH-001-T2", revision=revision)),
        revision=revision,
    )
    permit = Controller(journal_for("AUTH-001-T1", "AUTH-001-T2", revision=revision)).verify(
        task, b, verdict_inputs(revision=revision), at=NOW
    )
    return promote(
        task, b, permit,
        checkpoint_id=checkpoint_id, project_id=project_id, parent=parent,
        commit=revision, policy_hash=POLICY_HASH, at=NOW,
    )


def test_promotion_requires_checkpointing_state() -> None:
    task = make_task(state=TaskState.VERIFYING)
    b = passing_bundle()
    with pytest.raises(Refused, match="CHECKPOINTING"):
        promote(
            task, b, permit_for(task, b),
            checkpoint_id="ck-0001", project_id="prj-alpha", parent=None,
            commit=REV, policy_hash=POLICY_HASH, at=NOW,
        )


def test_no_permit_exists_without_attested_evidence() -> None:
    """``a04``: an empty bundle used to promote on a caller-supplied PASS."""
    task = make_task(state=TaskState.CHECKPOINTING)
    with pytest.raises(Refused, match="no permit issued"):
        Controller(HarnessJournal()).verify(task, bundle(()), verdict_inputs(), at=NOW)
    with pytest.raises(Refused, match="no permit issued"):
        Controller(HarnessJournal()).verify(task, passing_bundle(), verdict_inputs(), at=NOW)


def test_permit_is_bound_to_the_commit() -> None:
    """``a05``: evidence from revision A could promote commit B."""
    task = make_task(state=TaskState.CHECKPOINTING)
    b = passing_bundle()
    with pytest.raises(Refused, match="commit"):
        promote(
            task, b, permit_for(task, b),
            checkpoint_id="ck-0001", project_id="prj-alpha", parent=None,
            commit=OTHER_REV, policy_hash=POLICY_HASH, at=NOW,
        )


def test_permit_is_bound_to_the_bundle() -> None:
    task = make_task(state=TaskState.CHECKPOINTING)
    b = passing_bundle()
    other_bundle = passing_bundle(chain_head=sha("another-bundle"))
    with pytest.raises(Refused, match="different evidence bundle"):
        promote(
            task, other_bundle, permit_for(task, b),
            checkpoint_id="ck-0001", project_id="prj-alpha", parent=None,
            commit=REV, policy_hash=POLICY_HASH, at=NOW,
        )


def test_permit_is_bound_to_the_policy() -> None:
    task = make_task(state=TaskState.CHECKPOINTING)
    b = passing_bundle()
    with pytest.raises(Refused, match="policy hash"):
        promote(
            task, b, permit_for(task, b),
            checkpoint_id="ck-0001", project_id="prj-alpha", parent=None,
            commit=REV, policy_hash=sha("other-policy"), at=NOW,
        )


def test_happy_path_creates_a_valid_checkpoint() -> None:
    checkpoint_ = checkpoint()
    assert checkpoint_.valid
    assert checkpoint_.created_by == "controller"
    assert checkpoint_.verdict is Verdict.PASS
    assert checkpoint_.requirements_satisfied == ("AUTH-001",)

    chain = CheckpointChain()
    chain.append(checkpoint_)
    assert chain.head is checkpoint_
    assert chain.valid_head is checkpoint_


def test_chain_lineage_must_be_linear() -> None:
    first = checkpoint()
    chain = CheckpointChain()
    chain.append(first)
    stray = first.model_copy(update={"checkpoint_id": "ck-0002", "parent": None})
    with pytest.raises(Refused, match="lineage must be linear"):
        chain.append(stray)


def test_chain_refuses_duplicate_checkpoint_ids() -> None:
    chain = CheckpointChain()
    chain.append(checkpoint())
    second = checkpoint(parent="ck-0001", checkpoint_id="ck-0002", revision=OTHER_REV)
    duplicate = second.model_copy(update={"checkpoint_id": "ck-0001"})
    with pytest.raises(Refused, match="duplicate checkpoint id"):
        chain.append(duplicate)


def test_chain_refuses_cross_project_succession() -> None:
    chain = CheckpointChain()
    chain.append(checkpoint())
    foreign = checkpoint(parent="ck-0001", checkpoint_id="ck-0002", project_id="prj-other")
    with pytest.raises(Refused, match="cannot join chain"):
        chain.append(foreign)


def test_chain_invalidation_closes_the_resume_point() -> None:
    """``a11``: invalidating a copy left the chain's valid head intact."""
    chain = CheckpointChain()
    chain.append(checkpoint())
    invalid = chain.invalidate("ck-0001", InvalidationReason.VERIFY_FAILED)
    assert not invalid.valid
    assert chain.valid_head is None
    assert not chain.is_resumable("ck-0001")


def test_invalidating_an_ancestor_blocks_its_descendants() -> None:
    chain = CheckpointChain()
    chain.append(checkpoint())
    second = checkpoint(parent="ck-0001", checkpoint_id="ck-0002", revision=OTHER_REV)
    chain.append(second)
    assert chain.is_resumable("ck-0002")
    chain.invalidate("ck-0001", InvalidationReason.BASELINE_CHANGED)
    assert chain.valid_head is None
    assert not chain.is_resumable("ck-0002")


def test_double_invalidation_is_refused() -> None:
    chain = CheckpointChain()
    chain.append(checkpoint())
    chain.invalidate("ck-0001", InvalidationReason.UNAUTHORIZED_CODE_CHANGE)
    with pytest.raises(Refused, match="already invalidated"):
        chain.invalidate("ck-0001", InvalidationReason.SECURITY_INCIDENT)


def test_invalidation_of_unknown_checkpoint_is_refused() -> None:
    with pytest.raises(Refused, match="not part of this chain"):
        CheckpointChain().invalidate("ck-9999", InvalidationReason.VERIFY_FAILED)
