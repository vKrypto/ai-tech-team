"""Map a planned step to who executes it: a single agent role or a whole sub-workflow."""
from ..agents.registry import ROLES

SUBWORKFLOWS = {"coding", "research", "validation"}


def route_for(step: dict) -> str:
    """Graph node to run for a plan step: a subgraph name or "execute_agent"."""
    agent = (step or {}).get("agent", "")
    return agent if agent in SUBWORKFLOWS else "execute_agent"


def role_for(step: dict) -> str:
    agent = (step or {}).get("agent", "")
    return agent if agent in ROLES else "architect"
