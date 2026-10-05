"""Timing spans recorded as metrics; LangSmith tracing turns on by itself when LANGSMITH_* env vars are set."""
import logging
import time
from contextlib import contextmanager

from . import metrics

log = logging.getLogger("ai_team.trace")


@contextmanager
def span(name: str, **attrs):
    t0 = time.monotonic()
    try:
        yield
    finally:
        dt = time.monotonic() - t0
        metrics.incr(f"{name}.count")
        metrics.incr(f"{name}.seconds", dt)
        log.debug("%s %.2fs %s", name, dt, attrs)
