"""Recovery wiring: every graph gets the approval gate and the error handler, routed back to whichever
node raised the question or failed. (Automatic node retries happen in context.tracked; engine-level
crash recovery comes from the Redis checkpointer; run-level auto-retry is the orchestrator's policy.)"""
from langgraph.graph import END

from .approval import approval, route_after_approval
from ..nodes.handle_error import handle_error, route_after_error


def add_recovery(g, work_nodes: list[str]) -> None:
    g.add_node("approval", approval)
    g.add_node("handle_error", handle_error)
    g.add_conditional_edges("approval", route_after_approval, [*work_nodes, END])
    g.add_conditional_edges("handle_error", route_after_error, [*work_nodes, END])
