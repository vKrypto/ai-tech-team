"""Run something against a provider chain, falling back to the next provider when one fails."""
import logging
from typing import Callable, TypeVar

from ..observability import metrics
from .providers.base import Cancelled, Provider, ProviderError

log = logging.getLogger(__name__)
T = TypeVar("T")


def run(chain: list[Provider], fn: Callable[[Provider, int], T],
        on_fallback: Callable[[Provider, Exception], None] = lambda p, e: None) -> tuple[T, Provider]:
    """fn(provider, attempt_index). Cancellation is never retried on another provider."""
    errors = []
    for i, provider in enumerate(chain):
        try:
            return fn(provider, i), provider
        except Cancelled:
            raise
        except Exception as e:
            log.warning("provider %s failed: %s", provider.name, e)
            metrics.incr(f"provider.{provider.name}.failures")
            errors.append(f"{provider.name}: {type(e).__name__}: {e}")
            if i + 1 < len(chain):
                on_fallback(provider, e)
    raise ProviderError("all providers failed:\n" + "\n".join(errors))
