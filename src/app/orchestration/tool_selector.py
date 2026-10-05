"""Tool groups per role, from configs/agents.yaml (`tools: all` = every enabled group = full access)."""
from ..settings import settings
from ..tools import registry


def groups_for(role: str) -> list[str]:
    wanted = ((settings.agents.get("roles") or {}).get(role) or {}).get("tools", "all")
    available = registry.available_groups()
    if wanted == "all":
        return available
    return [g for g in wanted or [] if g in available]
