from ...common.nodes.load_context import load_context
from ...common.nodes.validate_task import validate_task


def receive_task(state: dict) -> dict:
    updates = validate_task(state)
    if updates.get("failed"):
        return updates
    return {**updates, **load_context(state, node="receive_task")}
