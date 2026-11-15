"""Representation adapter only; preserves v1 decisions and errors."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from csef_contracts.common import Decision, ExecutionStatus, Idempotency
from csef_contracts.policy import resolve
from csef_contracts.failure import classify_failure, plan_recovery
from csef_contracts.tool import ErrorClass, Invocation


def evaluate(r):
    if r["op"] == "resolve":
        return resolve(*(Decision(d) for d in r["decisions"])).value
    if r["op"] == "classify":
        return classify_failure(ErrorClass(r["error"]), ExecutionStatus(r["outcome"])).value
    if r["op"] == "recover":
        invocation = Invocation(invocation_id="inv-000001", task_id="T-0042", tool="run_tests",
            tool_version=1, attempt=1, idempotency_key="sha256:" + "1"*64,
            input_hash="sha256:" + "2"*64, effects={"process"},
            idempotency=Idempotency(r["idempotency"]))
        return plan_recovery(invocation, ExecutionStatus(r["outcome"]), ErrorClass(r["error"])).value
    raise ValueError("unsupported operation")


if __name__ == "__main__":
    print(json.dumps(evaluate(json.load(sys.stdin))))
