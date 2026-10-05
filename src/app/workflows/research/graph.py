"""Research workflow: validate_task -> load_context -> plan -> search -> analyze -> synthesize -> finalize"""
from langgraph.graph import END

from ..factory import GraphBuilder
from .nodes.analyze import analyze
from .nodes.plan import plan
from .nodes.search import search
from .nodes.synthesize import synthesize
from .routes import ORDER, next_of


def build(checkpointer=None, standalone: bool = True):
    b = GraphBuilder()
    if standalone:
        b.head()
    for name, fn in zip(ORDER, (plan, search, analyze, synthesize)):
        b.node(name, fn)
    if standalone:
        b.then("load_context", "plan")
    else:
        b.start("plan")
    exit_to = "finalize" if standalone else END
    for name in ORDER:
        b.then(name, next_of(name, exit_to))
    if standalone:
        b.finalize()
    return b.build(checkpointer, name="research")


graph = build()
