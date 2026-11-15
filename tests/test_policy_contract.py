"""Contract 30 — precedence, single-use approvals, and reservations that cannot overshoot."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest

from csef_contracts.common import Decision, Refused
from csef_contracts.policy import (
    Authorization,
    AuthorizationStore,
    BudgetExceeded,
    BudgetLedger,
    Budgets,
    decide,
    resolve,
)
from support import NOW, make_policy, sha


def test_deny_beats_allow_regardless_of_order() -> None:
    assert resolve(Decision.ALLOW, Decision.DENY) is Decision.DENY
    assert resolve(Decision.DENY, Decision.ASK, Decision.ALLOW) is Decision.DENY


def test_unknown_capability_is_denied_by_default() -> None:
    policy = make_policy()
    assert decide(policy, "deploy_production") is Decision.DENY


def test_immutable_path_cannot_be_softened_by_an_allow_rule() -> None:
    policy = make_policy()
    allowed = policy.model_copy(
        update={
            "tools": {
                **policy.tools,
                "edit_project_files": policy.tools["edit_project_files"].model_copy(
                    update={"paths": (".csef/acceptance/**",)}
                ),
            }
        }
    )
    assert decide(allowed, "edit_project_files", path=".csef/acceptance/auth.yaml") is Decision.DENY


def test_write_outside_declared_scope_is_denied() -> None:
    policy = make_policy()
    assert decide(policy, "edit_project_files", path="infra/prod.tf") is Decision.DENY
    assert decide(policy, "edit_project_files", path="src/auth/login.py") is Decision.ALLOW


def test_approval_is_single_use() -> None:
    store = AuthorizationStore()
    store.grant(
        Authorization(
            approval_id="apr-0001",
            invocation_hash=sha("inv-hash-1"),
            capability="install_dependencies",
            scope_task_id="T-0042",
            granted_by="human:kp",
            granted_at=NOW,
            expires_at=NOW + timedelta(minutes=30),
            max_uses=1,
        )
    )
    store.consume("apr-0001", sha("inv-hash-1"), NOW, "T-0042")
    with pytest.raises(Refused, match="replay rejected"):
        store.consume("apr-0001", sha("inv-hash-1"), NOW, "T-0042")


def test_approval_is_bound_to_the_exact_invocation() -> None:
    store = AuthorizationStore()
    store.grant(
        Authorization(
            approval_id="apr-0002",
            invocation_hash=sha("inv-hash-1"),
            capability="install_dependencies",
            scope_task_id="T-0042",
            granted_by="human:kp",
            granted_at=NOW,
        )
    )
    with pytest.raises(Refused, match="hash mismatch"):
        store.consume("apr-0002", sha("inv-hash-2"), NOW, "T-0042")


def test_expired_approval_is_refused() -> None:
    store = AuthorizationStore()
    store.grant(
        Authorization(
            approval_id="apr-0003",
            invocation_hash=sha("inv-hash-1"),
            capability="install_dependencies",
            scope_task_id="T-0042",
            granted_by="human:kp",
            granted_at=NOW,
            expires_at=NOW + timedelta(seconds=1),
        )
    )
    with pytest.raises(Refused, match="expired"):
        store.consume("apr-0003", sha("inv-hash-1"), NOW + timedelta(minutes=1), "T-0042")


def test_parallel_reservations_cannot_cross_the_run_limit() -> None:
    ledger = BudgetLedger(per_call_limit_usd="0.60", run_limit_usd="1.00")

    def attempt(_: int) -> bool:
        try:
            ledger.reserve("0.60")
            return True
        except BudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(attempt, range(24)))

    assert sum(results) == 1, "exactly one 0.60 reservation fits under a 1.00 cap"
    assert ledger.reserved == Decimal("0.6000")


def test_actual_cost_may_not_exceed_reservation() -> None:
    ledger = BudgetLedger(per_call_limit_usd="0.50", run_limit_usd="1.00")
    reservation = ledger.reserve("0.50")
    with pytest.raises(BudgetExceeded, match="reserved upper bound"):
        ledger.commit(reservation, "0.75")


def test_unset_budget_does_not_start() -> None:
    with pytest.raises(Refused, match="unset"):
        Budgets().assert_startable()
