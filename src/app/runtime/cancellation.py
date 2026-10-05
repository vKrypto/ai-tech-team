"""Cancellation flags in Redis, checked by the engine between nodes and by agents while they work."""
from .. import constants as C
from ..llm.providers.base import Cancelled
from ..persistence.store import redis

__all__ = ["Cancelled", "cancel", "clear", "is_cancelled", "check"]


def cancel(task_id: int) -> None:
    redis().set(C.KEY_CANCEL.format(task_id=task_id), "1", ex=7 * 24 * 3600)


def clear(task_id: int) -> None:
    redis().delete(C.KEY_CANCEL.format(task_id=task_id))


def is_cancelled(task_id: int) -> bool:
    return bool(redis().exists(C.KEY_CANCEL.format(task_id=task_id)))


def check(task_id: int) -> None:
    if is_cancelled(task_id):
        raise Cancelled()
