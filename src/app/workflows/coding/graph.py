"""Coding workflow:

  validate_task -> load_context -> inspect_repo -> plan_changes -> implement -> test -> review
                                                                       ^                  |
                                                                       +-- changes -------+--> finalize
"""
from langgraph.graph import END

from ..factory import GraphBuilder
from .nodes.implement import implement
from .nodes.inspect_repo import inspect_repo
from .nodes.plan_changes import plan_changes
from .nodes.review import review
from .nodes.test import test
from .routes import after_review


def build(checkpointer=None, standalone: bool = True):
    b = GraphBuilder()
    if standalone:
        b.head()
    b.node("inspect_repo", inspect_repo).node("plan_changes", plan_changes).node("implement", implement) \
        .node("test", test).node("review", review)
    if standalone:
        b.then("load_context", "inspect_repo")
    else:
        b.start("inspect_repo")
    b.then("inspect_repo", "plan_changes").then("plan_changes", "implement").then("implement", "test") \
        .then("test", "review")
    exit_to = "finalize" if standalone else END
    b.then("review", lambda s: exit_to if after_review(s) == "exit" else "implement", [exit_to, "implement"])
    if standalone:
        b.finalize()
    return b.build(checkpointer, name="coding")


graph = build()
