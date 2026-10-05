"""The research workflow as a step of task_execution (no validate/load/finalize of its own)."""
from ...research.graph import build


def subgraph():
    return build(standalone=False)
