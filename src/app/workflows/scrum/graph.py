"""Scrum workflow (scrum_master): validate_task -> load_context -> collect_status -> plan_actions
-> apply_actions -> report -> finalize"""
from ..factory import GraphBuilder
from .nodes.apply_actions import apply_actions
from .nodes.collect_status import collect_status
from .nodes.plan_actions import plan_actions
from .nodes.report import report
from .routes import ORDER


def build(checkpointer=None):
    b = GraphBuilder().head()
    for name, fn in zip(ORDER, (collect_status, plan_actions, apply_actions, report)):
        b.node(name, fn)
    b.then("load_context", ORDER[0])
    for a, nxt in zip(ORDER, ORDER[1:] + ["finalize"]):
        b.then(a, nxt)
    b.finalize()
    return b.build(checkpointer, name="scrum")


graph = build()
