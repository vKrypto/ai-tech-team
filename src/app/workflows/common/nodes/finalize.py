"""Compose the turn's answer, store it on the task and in the conversation, and remember it per project."""
from ....memory import long_term
from ....persistence import task_repository as tasks

# which outputs make up the final answer, per workflow
FINAL_FROM = {
    "coding": [("implement", "What changed"), ("test", "Tests"), ("review", "Review")],
    "research": [("synthesize", None)],
    "task_execution": [("complete", None)],
    "pr_review": [("review_pr", None), ("post_review", "Posted")],
    "scrum": [("report", None)],
}


def compose(state: dict) -> str:
    outputs = state.get("outputs") or {}
    parts = []
    for node, title in FINAL_FROM.get(state.get("workflow", ""), []):
        if outputs.get(node):
            parts.append(f"## {title}\n{outputs[node]}" if title else outputs[node])
    if state.get("workflow") == "coding" and not state.get("approved", True):
        parts.append("> Note: the reviewer did not approve within the allowed review rounds.")
    return "\n\n".join(parts) or "(no output)"


def finalize(state: dict) -> dict:
    final = compose(state)
    tid = state["task_id"]
    tasks.update(tid, result=final)
    tasks.add_message(tid, state.get("turn", 1), "assistant", final)
    long_term.remember(state.get("project"), tid, state.get("title") or state["request"][:80], final[:2000])
    return {"final": final, "outputs": {"finalize": final}}
