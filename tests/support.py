"""Builders shared by the compatibility tests. Every fixture is deterministic."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel

from csef_contracts.common import Decision, Verdict
from csef_contracts.evidence import (
    EvidenceBundle,
    EvidenceKind,
    EvidenceRecord,
    VerificationRecord,
    VerdictInputs,
)
from csef_contracts.policy import Budgets, Policy, Protection, Rule
from csef_contracts.task import (
    AcceptanceSpec,
    Budget,
    Criterion,
    CriterionType,
    Profile,
    Scope,
    Task,
    TaskState,
)
from csef_contracts.tool import Effect, Idempotency, SandboxProfile, ToolSpec
from csef_contracts.verification import HarnessJournal

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def sha(seed: str) -> str:
    return "sha256:" + hashlib.sha256(seed.encode()).hexdigest()


def git(seed: str) -> str:
    return "git:" + hashlib.sha1(seed.encode()).hexdigest()[:40]


REV = git("rev-1")
OTHER_REV = git("rev-2")
BASELINE = sha("baseline-auth-v1")
ENV_FP = sha("win10ent-22h2/py3.11")
OTHER_ENV = sha("win10ent-22h2/py3.12")
POLICY_HASH = sha("policy-v1")


class RunTestsInput(BaseModel):
    target: str
    timeout_s: int = 600


def criteria() -> tuple[Criterion, ...]:
    return (
        Criterion(
            id="AUTH-001-T1",
            type=CriterionType.EXECUTABLE,
            runner="pytest",
            target="tests/test_auth.py::test_login_valid",
            expected_exit_code=0,
        ),
        Criterion(
            id="AUTH-001-T2",
            type=CriterionType.EXECUTABLE,
            runner="pytest",
            target="tests/test_auth.py::test_login_invalid",
            expected_exit_code=0,
        ),
    )


def acceptance(criteria_: tuple[Criterion, ...] | None = None, requirement_id: str = "AUTH-001") -> AcceptanceSpec:
    return AcceptanceSpec(
        requirement_id=requirement_id,
        criteria=criteria_ or criteria(),
        baseline_hash=BASELINE,
        frozen_at=NOW,
    )


def task_state_path() -> list[TaskState]:
    return [
        TaskState.PLANNED,
        TaskState.PREPARED,
        TaskState.AUTHORIZED,
        TaskState.EXECUTING,
        TaskState.COLLECTING,
        TaskState.VERIFYING,
        TaskState.CHECKPOINTING,
    ]


def make_task(
    *,
    state: TaskState = TaskState.CREATED,
    open_decisions: tuple[str, ...] = (),
    acceptance_: AcceptanceSpec | None = None,
) -> Task:
    task = Task(
        task_id="T-0042",
        requirement_ids=("AUTH-001",),
        profile=Profile.STANDARD,
        objective="login works with valid credentials and rejects invalid ones",
        acceptance=acceptance_ or acceptance(),
        scope=Scope(
            writable_paths=("src/auth/**", "tests/**"),
            readonly_paths=("src/core/**",),
            max_files_changed=8,
            max_lines_changed=400,
        ),
        budget=Budget(
            max_patch_attempts=3,
            max_cost_usd=Decimal("2.50"),
            max_wall_clock_s=1800,
            max_tool_calls=120,
        ),
        open_decisions=open_decisions,
    )
    path = task_state_path()
    if state in path:
        for target in path[: path.index(state) + 1]:
            task = task.transition(target)
    return task


def _invocation(criterion_id: str) -> str:
    digest = hashlib.sha1(criterion_id.encode()).hexdigest()[:6]
    return "inv-" + str(int(digest, 16) % 900000 + 100000).zfill(6)


def content_hash(criterion_id: str) -> str:
    return sha("report-" + criterion_id)


def evidence(
    criterion_id: str,
    *,
    revision: str | None = None,
    env: str | None = None,
    invocation_id: str | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="ev-00001",
        kind=EvidenceKind.TEST_REPORT,
        criterion_id=criterion_id,
        invocation_id=invocation_id or _invocation(criterion_id),
        source_revision=revision or REV,
        env_fingerprint=env or ENV_FP,
        sandbox_id="sbx-runner-01",
        captured_at=NOW,
        content_hash=content_hash(criterion_id),
        size_bytes=1200,
        truncated=False,
    )


def harness_record(
    criterion_id: str,
    *,
    revision: str | None = None,
    verdict: Verdict = Verdict.PASS,
    execution_status: str = "ok",
    stdout_hash: str | None = None,
    invocation_id: str | None = None,
) -> VerificationRecord:
    """The trusted side of the join: an execution record the harness would write."""
    return VerificationRecord(
        harness_record_id="hr-000" + str(criteria().index(next(c for c in criteria() if c.id == criterion_id)) + 1).zfill(3),
        invocation_id=invocation_id or _invocation(criterion_id),
        task_id="T-0042",
        source_commit_hash=revision or REV,
        acceptance_bundle_hash=BASELINE,
        policy_version_hash=POLICY_HASH,
        sandbox_image_digest=sha("image-1"),
        command_spec_hash=sha("cmd-" + criterion_id),
        dependency_lock_hash=sha("lock-1"),
        captured_exit_code=0,
        captured_stdout_hash=stdout_hash or content_hash(criterion_id),
        captured_stderr_hash=sha("stderr-" + criterion_id),
        execution_status=execution_status,
        verification_verdict=verdict,
        recorded_at=NOW,
    )


def journal_for(*criterion_ids: str, revision: str | None = None) -> HarnessJournal:
    journal = HarnessJournal()
    for criterion_id in criterion_ids:
        journal.append(harness_record(criterion_id, revision=revision))
    return journal


def passing_journal() -> HarnessJournal:
    return journal_for("AUTH-001-T1", "AUTH-001-T2")


def bundle(
    items: tuple[EvidenceRecord, ...],
    *,
    revision: str | None = None,
    env: str | None = None,
    baseline: str | None = None,
    task_id: str | None = None,
    chain_head: str | None = None,
    policy_hash: str | None = None,
) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="eb-00001",
        task_id=task_id or "T-0042",
        source_revision=revision or REV,
        baseline_hash=baseline or BASELINE,
        policy_hash=policy_hash or POLICY_HASH,
        env_fingerprint=env or ENV_FP,
        items=items,
        chain_head=chain_head or sha("chain-head-1"),
    )


def verdict_inputs(*, revision: str | None = None, env: str | None = None, baseline: str | None = None) -> VerdictInputs:
    return VerdictInputs(
        task_id="T-0042",
        source_revision=revision or REV,
        baseline_hash=baseline or BASELINE,
        env_fingerprint=env or ENV_FP,
    )


def permit_for(task, b, *, journal=None, inputs=None):
    """Mint a permit through the real controller; there is no other way to get one."""
    from csef_contracts.verification import Controller

    controller = Controller(journal or passing_journal())
    return controller.verify(task, b, inputs or verdict_inputs(), at=NOW)


def make_policy(**overrides: object) -> Policy:
    base = Policy(
        policy_version=1,
        policy_hash=POLICY_HASH,
        execution_default=Decision.DENY,
        tools={
            "run_tests": Rule(decision=Decision.ALLOW, sandbox_required=True),
            "edit_project_files": Rule(
                decision=Decision.ALLOW, scope="isolated_worktree", paths=("src/**", "tests/**")
            ),
            "install_dependencies": Rule(decision=Decision.ASK, network_required=True, once_per_task=True),
            "run_command": Rule(decision=Decision.DENY),
            "delete_project": Rule(decision=Decision.DENY),
        },
        budgets=Budgets(),
        protection=Protection(immutable_paths=(".csef/policy.yaml", ".csef/acceptance/**", ".csef/evidence/**")),
    )
    return base if not overrides else Policy.model_validate(
        {
            "policy_version": base.policy_version,
            "policy_hash": base.policy_hash,
            "execution_default": base.execution_default,
            "tools": dict(base.tools),
            "budgets": base.budgets,
            "protection": base.protection,
            **overrides,
        }
    )


def tool_spec(**overrides: object) -> ToolSpec:
    base = ToolSpec(
        name="run_tests",
        version=1,
        description_for_model="run tests in the sandbox and return raw output",
        effects=frozenset({Effect.PROCESS}),
        capabilities=("run_tests",),
        sandbox=SandboxProfile(required=True, profile="default", network=False),
        input_model=RunTestsInput,
        idempotency=Idempotency.READ_ONLY,
        timeout_s=900,
    )
    return base.model_copy(update=overrides) if overrides else base
