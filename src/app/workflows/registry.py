"""Workflow name -> compiled graph (with the Redis checkpointer)."""
from functools import cache

from ..persistence import checkpoints
from ..settings import settings
from .factory import mermaid
from .coding import graph as coding
from .pr_review import graph as pr_review
from .research import graph as research
from .scrum import graph as scrum
from .task_execution import graph as task_execution

BUILDERS = {"task_execution": task_execution.build, "research": research.build, "coding": coding.build,
            "pr_review": pr_review.build, "scrum": scrum.build}
CONTROL_NODES = {"__start__", "__end__", "approval", "handle_error"}


@cache
def compiled(name: str):
    return BUILDERS[name](checkpointer=checkpoints.get())


def names() -> list[str]:
    return list(BUILDERS)


def describe(name: str) -> dict:
    g = compiled(name)
    return {"name": name, "description": ((settings.workflows.get("workflows") or {}).get(name) or {})
            .get("description", ""),
            "mermaid": mermaid(g.ait_spec),
            "rerunnable": [n for n in g.get_graph().nodes if n not in CONTROL_NODES]}
