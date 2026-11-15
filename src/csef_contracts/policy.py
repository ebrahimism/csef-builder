"""Contract 30: policy, single-use approvals, and cost budgets."""
from __future__ import annotations

import re
import threading
import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Mapping

from pydantic import Field, StringConstraints, field_validator

from .common import Contract, Decision, Refused, Sha256, usd


class OnLimit(StrEnum):
    STOP = "stop"
    DOWNGRADE = "downgrade"


class Rule(Contract):
    decision: Decision
    scope: str | None = None
    sandbox_required: bool | None = None
    network_required: bool | None = None
    paths: tuple[str, ...] = ()
    once_per_task: bool = False


class Budgets(Contract):
    run_limit_usd: Decimal | None = Field(default=None, ge=0)
    project_limit_usd: Decimal | None = Field(default=None, ge=0)
    per_call_limit_usd: Decimal | None = Field(default=None, ge=0)
    on_limit: OnLimit = OnLimit.STOP

    def assert_startable(self) -> None:
        """A cost-bearing run needs both a per-call ceiling and a run ceiling; null is not infinity."""
        if self.run_limit_usd is None or self.per_call_limit_usd is None:
            raise Refused("budgets are unset (null); cost-bearing execution may not start (I6)")


class Protection(Contract):
    immutable_paths: tuple[str, ...] = ()


class Policy(Contract):
    """Deeply immutable: a frozen model with a mutable dict is shallow theatre (``a13``)."""

    policy_version: int = Field(ge=1)
    policy_hash: Sha256
    execution_default: Decision = Decision.DENY
    tools: Mapping[str, Rule] = Field(default_factory=dict)
    budgets: Budgets = Field(default_factory=Budgets)
    protection: Protection = Field(default_factory=Protection)

    @field_validator("tools", mode="after")
    @classmethod
    def _freeze_tools(cls, value: Mapping[str, Rule]) -> Mapping[str, Rule]:
        return MappingProxyType(dict(value))

    @field_validator("execution_default", mode="after")
    @classmethod
    def _no_open_default(cls, value: Decision) -> Decision:
        if value is Decision.ALLOW:
            raise ValueError("execution_default may not be ALLOW: an unlisted capability is unknown (I6)")
        return value

    def rule_for(self, capability: str) -> Rule:
        return self.tools.get(capability, Rule(decision=self.execution_default))


def resolve(*decisions: Decision) -> Decision:
    """Precedence is deny > ask > allow. No rule can soften a deny."""
    if Decision.DENY in decisions:
        return Decision.DENY
    if Decision.ASK in decisions:
        return Decision.ASK
    if Decision.ALLOW in decisions:
        return Decision.ALLOW
    return Decision.DENY


_ABSOLUTE = re.compile(r"^(?:[A-Za-z]:|[\\/])")


def normalize_project_path(path: str) -> str:
    """Resolve nothing and trust nothing.

    A path is a project-relative, forward-slash, ``..``-free sequence. Anything else is
    refused instead of being silently interpreted (``a08``: ``src/../../outside.txt``).
    """
    if not path:
        raise Refused("empty path")
    if "\x00" in path or any(ord(ch) < 32 for ch in path):
        raise Refused("control characters in path")
    if "\\" in path:
        raise Refused(f"backslash separators are not project paths: {path!r}")
    if _ABSOLUTE.match(path):
        raise Refused(f"absolute paths are not project paths: {path!r}")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise Refused(f"empty, '.' or '..' segment in path: {path!r}")
    return "/".join(parts)


def _matches(path: str, pattern: str) -> bool:
    anchor = pattern.rstrip("*").rstrip("/")
    return path == anchor or path.startswith(anchor + "/")


def decide(policy: Policy, capability: str, *, path: str | None = None) -> Decision:
    """Path-scoped capabilities require a path; without one, scope is unchecked (``a09``)."""
    rule = policy.rule_for(capability)
    decisions = [rule.decision]
    normalized = normalize_project_path(path) if path is not None else None
    if rule.paths:
        if normalized is None:
            decisions.append(Decision.DENY)
        elif not any(_matches(normalized, pattern) for pattern in rule.paths):
            decisions.append(Decision.DENY)
    if normalized is not None and any(_matches(normalized, pattern) for pattern in policy.protection.immutable_paths):
        decisions.append(Decision.DENY)
    return resolve(*decisions)


class Authorization(Contract):
    """An approval bound to one exact invocation. It cannot be replayed for another command."""

    approval_id: Annotated[str, StringConstraints(pattern=r"^apr-[0-9]{4}$")]
    invocation_hash: Sha256
    capability: str
    scope_task_id: Annotated[str, StringConstraints(pattern=r"^T-[0-9]{4}$")]
    granted_by: Annotated[str, StringConstraints(pattern=r"^(human|system):[A-Za-z0-9_.-]{1,64}$")]
    granted_at: datetime
    expires_at: datetime | None = None
    max_uses: int = Field(default=1, ge=1, le=100)


class AuthorizationStore:
    """The store is the authority; the record is the artifact. Uses are consumed atomically."""

    def __init__(self) -> None:
        self._grants: dict[str, tuple[Authorization, int]] = {}
        self._lock = threading.Lock()

    def grant(self, authorization: Authorization) -> None:
        with self._lock:
            if authorization.approval_id in self._grants:
                raise Refused(f"approval {authorization.approval_id} already exists")
            self._grants[authorization.approval_id] = (authorization, 0)

    def consume(self, approval_id: str, invocation_hash: str, now: datetime, task_id: str) -> Authorization:
        with self._lock:
            if approval_id not in self._grants:
                raise Refused(f"approval {approval_id} is unknown")
            auth, used = self._grants[approval_id]
            if auth.invocation_hash != invocation_hash:
                raise Refused("approval is bound to a different invocation; hash mismatch")
            if auth.scope_task_id != task_id:
                raise Refused("approval is bound to a different task")
            if auth.expires_at is not None and now >= auth.expires_at:
                raise Refused(f"approval {approval_id} expired")
            if used >= auth.max_uses:
                raise Refused(f"approval {approval_id} already used {used} time(s); replay rejected")
            self._grants[approval_id] = (auth, used + 1)
            return auth


class Reservation(Contract):
    reservation_id: Annotated[str, StringConstraints(pattern=r"^rsv-[0-9a-f]{8}$")]
    ledger_id: Annotated[str, StringConstraints(pattern=r"^led-[0-9a-f]{8}$")]
    amount_usd: Decimal = Field(gt=0)


class BudgetExceeded(Refused):
    pass


class BudgetLedger:
    """reserve -> execute -> commit/rollback.

    Settlement is terminal: a second settle, or a settle from a foreign ledger, is refused.
    Otherwise a replayed rollback manufactures spending capacity (``a06``/``a07``).
    """

    def __init__(self, per_call_limit_usd: Decimal | str, run_limit_usd: Decimal | str) -> None:
        self.ledger_id = f"led-{uuid.uuid4().hex[:8]}"
        self.per_call = usd(per_call_limit_usd)
        self.limit = usd(run_limit_usd)
        self._reserved = Decimal("0.0000")
        self._committed = Decimal("0.0000")
        self._settled: set[str] = set()
        self._lock = threading.Lock()

    @property
    def reserved(self) -> Decimal:
        return self._reserved

    @property
    def committed(self) -> Decimal:
        return self._committed

    def reserve(self, amount_usd: Decimal | str) -> Reservation:
        amount = usd(amount_usd)
        if amount <= 0:
            raise BudgetExceeded("reservation must be positive")
        if amount > self.per_call:
            raise BudgetExceeded(f"estimate {amount} exceeds per-call limit {self.per_call}")
        with self._lock:
            if self._committed + self._reserved + amount > self.limit:
                raise BudgetExceeded(
                    f"reservation {amount} would cross run limit {self.limit} "
                    f"(committed={self._committed}, reserved={self._reserved})"
                )
            self._reserved += amount
            return Reservation(
                reservation_id=f"rsv-{uuid.uuid4().hex[:8]}",
                ledger_id=self.ledger_id,
                amount_usd=amount,
            )

    def _claim(self, reservation: Reservation) -> None:
        """Caller holds the lock."""
        if reservation.ledger_id != self.ledger_id:
            raise BudgetExceeded("reservation belongs to another ledger; refusing to settle it here")
        if reservation.reservation_id in self._settled:
            raise BudgetExceeded("reservation is already settled; a second settle would release funds twice")
        self._settled.add(reservation.reservation_id)

    def commit(self, reservation: Reservation, actual_usd: Decimal | str) -> None:
        actual = usd(actual_usd)
        if actual > reservation.amount_usd:
            raise BudgetExceeded("actual cost exceeded the reserved upper bound; this is a bug, not a bill")
        with self._lock:
            self._claim(reservation)
            self._reserved -= reservation.amount_usd
            self._committed += actual

    def rollback(self, reservation: Reservation) -> None:
        with self._lock:
            self._claim(reservation)
            self._reserved -= reservation.amount_usd
