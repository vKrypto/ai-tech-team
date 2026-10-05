"""Named providers from configs/models.yaml."""
from functools import cache

from ..settings import settings
from . import factory
from .providers.base import Provider


@cache
def providers() -> dict[str, Provider]:
    return {name: factory.create(name, cfg or {}) for name, cfg in (settings.models.get("providers") or {}).items()}


def get(name: str) -> Provider:
    return providers()[name]


def enabled() -> list[Provider]:
    return [p for p in providers().values() if p.enabled]
