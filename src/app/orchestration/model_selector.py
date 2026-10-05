"""Tier per job: the task's tier (from the orchestrator), but never below the role's configured floor."""
from ..settings import settings

ORDER = ["fast", "balanced", "deep"]


def tier_for(role: str, task_tier: str | None) -> str:
    role_tier = ((settings.agents.get("roles") or {}).get(role) or {}).get("tier", "balanced")
    tiers = [t for t in (role_tier, task_tier) if t in ORDER]
    return max(tiers, key=ORDER.index) if tiers else "balanced"
