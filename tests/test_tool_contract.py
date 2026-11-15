"""Contract 20 — nothing runs that was not registered, declared and schema-valid."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from csef_contracts.common import Refused
from csef_contracts.tool import (
    Effect,
    Idempotency,
    Invocation,
    SandboxProfile,
    ToolRegistry,
    ToolSpec,
    assert_effects_not_expanded,
)
from support import RunTestsInput, sha, tool_spec


def test_unregistered_tool_is_refused() -> None:
    registry = ToolRegistry()
    with pytest.raises(Refused, match="not registered"):
        registry.get("delete_project")


def test_duplicate_registration_is_refused() -> None:
    registry = ToolRegistry()
    registry.register(tool_spec())
    with pytest.raises(Refused, match="already registered"):
        registry.register(tool_spec())


def test_process_tool_requires_a_sandbox() -> None:
    unsafe = tool_spec(sandbox=SandboxProfile(required=False))
    with pytest.raises(Refused, match="without a sandbox"):
        ToolRegistry().register(unsafe)


def test_input_outside_schema_is_rejected() -> None:
    registry = ToolRegistry()
    registry.register(tool_spec())
    with pytest.raises(ValidationError):
        registry.validate_call("run_tests", {"target": 42})
    with pytest.raises(ValidationError):
        registry.validate_call("run_tests", {})


def test_valid_input_passes_through_the_gateway() -> None:
    registry = ToolRegistry()
    registry.register(tool_spec())
    parsed = registry.validate_call("run_tests", {"target": "tests/test_auth.py"})
    assert isinstance(parsed, RunTestsInput)
    assert parsed.timeout_s == 600


def test_runtime_effect_expansion_is_refused() -> None:
    spec = tool_spec()
    invocation = Invocation(
        invocation_id="inv-000001",
        task_id="T-0042",
        tool="run_tests",
        tool_version=1,
        attempt=1,
        idempotency_key=sha("idem-1"),
        input_hash=sha("input-1"),
        effects=frozenset({Effect.PROCESS, Effect.NETWORK}),
        idempotency=Idempotency.READ_ONLY,
    )
    with pytest.raises(Refused, match="runtime effects"):
        assert_effects_not_expanded(spec, invocation)


def test_network_inside_denied_sandbox_is_refused_at_registration() -> None:
    spec = ToolSpec(
        name="fetch_deps",
        version=1,
        description_for_model="download dependencies",
        effects=frozenset({Effect.NETWORK}),
        capabilities=("install_dependencies",),
        sandbox=SandboxProfile(required=True, network=True),
        input_model=RunTestsInput,
        idempotency=Idempotency.NON_IDEMPOTENT,
        timeout_s=300,
    )
    # network access is a *policy* decision, not a sandbox capability: declaring both
    # is a contract violation, not a convenience.
    with pytest.raises(Refused, match="network access inside a network-denied sandbox"):
        ToolRegistry().register(spec)


def test_invocation_requires_hashes_not_free_text() -> None:
    with pytest.raises(ValidationError):
        Invocation(
            invocation_id="inv-000001",
            task_id="T-0042",
            tool="run_tests",
            tool_version=1,
            attempt=1,
            idempotency_key="not-a-hash",
            input_hash="also-not",
            effects=frozenset({Effect.PROCESS}),
            idempotency=Idempotency.READ_ONLY,
        )
