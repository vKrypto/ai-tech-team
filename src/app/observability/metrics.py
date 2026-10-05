"""Tiny counters in a Redis hash (tasks created, jobs run, failures, provider fallbacks...)."""
from .. import constants as C
from ..persistence.store import redis


def incr(name: str, n: float = 1) -> None:
    try:
        redis().hincrbyfloat(C.KEY_METRICS, name, n)
    except Exception:
        pass


def snapshot() -> dict:
    return {k: float(v) for k, v in redis().hgetall(C.KEY_METRICS).items()}


def prometheus() -> str:
    return "".join(f"ai_team_{k.replace('.', '_').replace('-', '_')} {v}\n" for k, v in sorted(snapshot().items()))
