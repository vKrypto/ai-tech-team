"""A step failed (after its automatic retries): ask a human to retry or abort (or fail, per policy)."""
from langgraph.graph import END
from langgraph.types import interrupt

from ....observability import events
from ....orchestration.execution_policy import policy
from ....persistence import run_repository as runs
from ....runtime.run_context import bump_epoch


def handle_error(state: dict) -> dict:
    err = state.get("error") or {"node": "?", "message": "unknown error"}
    if policy(state.get("workflow")).get("on_error") == "fail":
        return {"failed": True}
    runs.node_wait(state["run_id"], "handle_error", err["message"])
    answer = interrupt({
        "kind": "error", "node": err["node"], "run_id": state["run_id"],
        "problem": f"Step `{err['node']}` failed: {err['message']}",
        "options": [{"id": "retry", "label": "Retry the step", "details": "Run the failed step again"},
                    {"id": "abort", "label": "Abort", "details": "Mark the task failed"}]})
    if (answer or {}).get("option") == "retry":
        bump_epoch(state["run_id"])
        events.emit(state["task_id"], "engine", "status", f"human chose to retry `{err['node']}`", state["run_id"])
        runs.node_done(state["run_id"], "handle_error", f"retry {err['node']}")
        return {"error": None, "retry_node": err["node"]}
    runs.node_done(state["run_id"], "handle_error", "aborted by human")
    return {"failed": True, "error": {**err, "message": f"aborted by human after: {err['message']}"}}


def route_after_error(state: dict) -> str:
    return END if state.get("failed") else state["retry_node"]
