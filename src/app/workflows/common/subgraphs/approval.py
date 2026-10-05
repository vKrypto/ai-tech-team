"""Human-in-the-loop gate. A node that needs a human puts the question in state["human"]; this node pauses
the run (LangGraph interrupt, checkpointed in Redis) until the answer arrives, then routes back to the node
that asked, which continues with the answer (same agent session)."""
from langgraph.graph import END
from langgraph.types import interrupt

from ....observability import events
from ....persistence import run_repository as runs

REJECT = {"abort", "reject"}


def approval(state: dict) -> dict:
    h = dict(state["human"])
    runs.node_wait(state["run_id"], "approval", h.get("problem", ""))
    answer = interrupt({**h, "run_id": state["run_id"]}) or {}
    label = next((o.get("label") for o in h.get("options") or [] if o.get("id") == answer.get("option")), None)
    events.emit(state["task_id"], "human", "human",
                f"answered `{h['node']}`: {answer.get('option') or ''} {label or ''} {answer.get('text') or ''}".strip(),
                state["run_id"])
    if answer.get("option") in REJECT:
        runs.node_done(state["run_id"], "approval", "rejected")
        return {"human": None, "failed": True, "error": {"node": h["node"], "message": "rejected by human"}}
    runs.node_done(state["run_id"], "approval", f"answered: {answer.get('option') or answer.get('text')}")
    upd = {"human": None, "human_answer": {"node": h["node"], "label": label, **answer}}
    if h.get("kind") == "approval":
        upd["approvals"] = [h["node"]]
    return upd


def route_after_approval(state: dict) -> str:
    return END if state.get("failed") else state["human_answer"]["node"]
