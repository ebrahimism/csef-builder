"""Small document-derived reference. No production/test imports.

Author has seen v1: algorithmic separation only, NOT clean-room provenance.
Scope: policy precedence, classification subset, unknown-outcome recovery.
"""
import json
import sys


def evaluate(r):
    if r["op"] == "resolve":
        rank = {"allow": 1, "ask": 2, "deny": 3}
        return max(r["decisions"], key=rank.__getitem__, default="deny")
    if r["op"] == "classify":
        # 60-failure section 1: named classes remain distinct.
        supported = {"bad_input", "transient", "policy_denied", "environment",
                     "product_bug", "budget_exhausted", "sandbox_violation", "unknown"}
        if r["error"] not in supported:
            return "UNRESOLVED"  # no invented timeout/cancelled mapping
        return r["error"]
    if r["op"] == "recover":
        # PROPOSED conflict precedence: section 4 quarantine/stop before replay.
        if r["error"] == "sandbox_violation":
            return "quarantine"
        if r["error"] == "policy_denied":
            return "escalate"
        if r["outcome"] == "unknown":
            return "stop_unknown" if r["idempotency"] == "non_idempotent" else "replay"
        return "UNRESOLVED"
    raise ValueError("unsupported operation")


if __name__ == "__main__":
    print(json.dumps(evaluate(json.load(sys.stdin))))
