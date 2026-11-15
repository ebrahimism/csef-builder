"""Thin adapter for implemented v1 operations; no expected-result logic."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from csef_contracts.common import Decision, ExecutionStatus
from csef_contracts.policy import resolve
from csef_contracts.failure import classify_failure
from csef_contracts.tool import ErrorClass

request = json.load(sys.stdin)
if request["op"] == "resolve":
    result = resolve(*(Decision(x) for x in request["decisions"]))
elif request["op"] == "classify":
    result = classify_failure(ErrorClass(request["error"]), ExecutionStatus(request["outcome"]))
else:
    raise ValueError("unsupported operation")
print(json.dumps(result.value))
