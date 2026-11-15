"""Shared primitives.

Every contract model is *closed* (``extra="forbid"``) and *immutable* (``frozen``).
An open model is a contract that accepts amendments from whoever writes it.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Sha256 = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
GitSha = Annotated[str, StringConstraints(pattern=r"^git:[0-9a-f]{7,40}$")]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]


class Contract(BaseModel):
    """Base class: closed schema, immutable instance, validated on construction."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Producer(StrEnum):
    HARNESS = "harness"
    AGENT = "agent"
    HUMAN = "human"


class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    REVIEW = "review"
    BLOCKED = "blocked"
    STALE = "stale"
    TAMPER_SUSPECTED = "tamper_suspected"


class Decision(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class Idempotency(StrEnum):
    READ_ONLY = "read_only"
    IDEMPOTENT = "idempotent"
    NON_IDEMPOTENT = "non_idempotent"


class ExecutionStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    UNKNOWN = "unknown"
    CANCELLED = "cancelled"
    DENIED = "denied"


class ContractViolation(Exception):
    """Raised when a rule from the contract documents is exercised illegally."""


class Refused(ContractViolation):
    """A legal-looking operation that the contract forbids in this context."""


def usd(value: str | float | Decimal) -> Decimal:
    """Money is Decimal; floats are accepted only at the boundary, never stored."""
    amount = Decimal(str(value))
    if amount < 0:
        raise ValueError("amount must be non-negative")
    return amount.quantize(Decimal("0.0001"))
