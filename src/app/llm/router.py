"""Which providers serve a role: the role's chain (or the default chain) filtered to enabled providers."""
from ..settings import settings
from . import registry
from .providers.base import Provider, ProviderError


def _names(value) -> list[str]:
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return list(value or [])


def chain(role: str) -> list[Provider]:
    routing = settings.models.get("routing") or {}
    names = _names((routing.get("roles") or {}).get(role)) or _names(routing.get("default"))
    known = registry.providers()
    out = [known[n] for n in names if n in known and known[n].enabled]
    if not out:  # an enabled provider missing from the chains still beats failing
        out = registry.enabled()
    if not out:
        raise ProviderError(f"no enabled provider for role {role!r}: set AI_TEAM_PROVIDERS "
                            f"(known: {', '.join(known)})")
    return out
