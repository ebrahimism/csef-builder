"""Contract 20: the tool gateway — the only surface through which the agent touches the world."""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated

from .common import Contract, ExecutionStatus, Idempotency, Refused, Sha256

ToolName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,48}$")]


class Effect(StrEnum):
    READ_FS = "read_fs"
    WRITE_FS = "write_fs"
    PROCESS = "process"
    NETWORK = "network"


class ErrorClass(StrEnum):
    TRANSIENT = "transient"
    POLICY_DENIED = "policy_denied"
    BAD_INPUT = "bad_input"
    ENVIRONMENT = "environment"
    PRODUCT_BUG = "product_bug"
    BUDGET_EXHAUSTED = "budget_exhausted"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    SANDBOX_VIOLATION = "sandbox_violation"
    UNKNOWN = "unknown"


class SandboxProfile(Contract):
    required: bool
    profile: str = "default"
    network: bool = False


class ToolSpec(Contract):
    """Static descriptor. There is no dynamic registration path (I7)."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", frozen=True)

    name: ToolName
    version: int = Field(ge=1)
    description_for_model: str
    effects: frozenset[Effect] = Field(min_length=1)
    capabilities: tuple[str, ...] = Field(min_length=1)
    sandbox: SandboxProfile
    input_model: type[BaseModel]
    idempotency: Idempotency
    timeout_s: int = Field(ge=1, le=900)


class ToolRegistry:
    """One registry per engine instance. Registration is explicit and validated."""

    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._specs:
            raise Refused(f"tool {spec.name!r} already registered")
        if Effect.PROCESS in spec.effects and not spec.sandbox.required:
            raise Refused(f"tool {spec.name!r} runs processes without a sandbox")
        if Effect.NETWORK in spec.effects and spec.sandbox.network:
            raise Refused(f"tool {spec.name!r} claims network access inside a network-denied sandbox")
        self._specs[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        try:
            return self._specs[name]
        except KeyError:
            raise Refused(f"tool {name!r} is not registered; unregistered tools cannot run (I1)") from None

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def validate_call(self, name: str, raw: dict[str, Any]) -> BaseModel:
        """Schema validation happens at the gateway, never inside the tool.

        Unknown keys are refused here rather than silently dropped by a permissive model
        (``a15``): a discarded parameter is a decision the caller did not make.
        """
        spec = self.get(name)
        unknown = sorted(set(raw) - set(spec.input_model.model_fields))
        if unknown:
            raise Refused(f"{name}: undeclared parameter(s) {unknown}; the schema is closed")
        return spec.input_model.model_validate(raw)


class Invocation(Contract):
    """Written to the journal *before* the effect (I8)."""

    invocation_id: Annotated[str, StringConstraints(pattern=r"^inv-[0-9]{6}$")]
    task_id: Annotated[str, StringConstraints(pattern=r"^T-[0-9]{4}$")]
    tool: ToolName
    tool_version: int = Field(ge=1)
    attempt: int = Field(ge=0)
    idempotency_key: Sha256
    input_hash: Sha256
    effects: frozenset[Effect]
    idempotency: Idempotency


class ToolResult(Contract):
    invocation_id: Annotated[str, StringConstraints(pattern=r"^inv-[0-9]{6}$")]
    outcome: ExecutionStatus
    exit_code: int | None = None
    stdout_hash: Sha256 | None = None
    stderr_hash: Sha256 | None = None
    duration_ms: int = Field(ge=0)
    sandbox_id: str
    error_class: ErrorClass | None = None


def assert_effects_not_expanded(spec: ToolSpec, invocation: Invocation) -> None:
    """A tool may not widen its declared effects at runtime."""
    extra = invocation.effects - spec.effects
    if extra:
        raise Refused(f"{spec.name}: runtime effects {sorted(extra)} were not declared in the spec")


def classify(result: ToolResult) -> ErrorClass:
    """Every failure must be classified; unclassified is its own (safe) answer."""
    if result.outcome is ExecutionStatus.OK:
        return ErrorClass.UNKNOWN  # not a failure; callers must check outcome first
    return result.error_class or ErrorClass.UNKNOWN
