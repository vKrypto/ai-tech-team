import logging
import time
from typing import Callable, TypeVar

log = logging.getLogger(__name__)
T = TypeVar("T")


def backoff(attempt: int, base: float = 2.0, cap: float = 60.0) -> float:
    return min(cap, base * (2 ** attempt))


def call(fn: Callable[[int], T], attempts: int, retry_on: tuple[type[Exception], ...] = (Exception,),
         no_retry: tuple[type[Exception], ...] = (), sleep: Callable[[float], None] = time.sleep) -> T:
    """fn(attempt) with exponential backoff; exceptions in `no_retry` propagate immediately."""
    for i in range(attempts):
        try:
            return fn(i)
        except no_retry:
            raise
        except retry_on as e:
            if i + 1 >= attempts:
                raise
            log.warning("attempt %s failed (%s); retrying", i + 1, e)
            sleep(backoff(i))
    raise RuntimeError("unreachable")
