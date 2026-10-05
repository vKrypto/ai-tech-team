"""Watchdog: re-publishes tasks whose broker message was lost, and notifies when a component goes quiet."""
import logging
import time
from datetime import timedelta

from ... import constants as C
from ...domain.events import Notification, TaskMessage
from ...orchestration.dispatcher import publish
from ...persistence import task_repository as tasks
from ...persistence.store import now, redis
from ...settings import settings
from ..common import live_services

log = logging.getLogger(__name__)
_last_seen: dict[str, float] = {}
_alerted: set[str] = set()


def republish_lost() -> int:
    n = 0
    for t in tasks.unpublished(now() - timedelta(seconds=settings.cfg("scheduler.republish_after_seconds", 60))):
        kind = "new" if t["turn"] == 1 and not t.get("workflow") else ("followup" if t["turn"] > 1 else "retry")
        publish(C.STREAM_TASKS, TaskMessage(kind=kind, task_id=t["id"], turn=t["turn"]))
        tasks.update(t["id"], published=True)
        log.warning("re-published task %s (%s)", t["id"], kind)
        n += 1
    return n


def check_components() -> None:
    """Alert once when a whole component kind has no live instance for stale_service_seconds."""
    nowt = time.time()
    for s in live_services():
        _last_seen[s["kind"]] = nowt
    stale = settings.cfg("scheduler.stale_service_seconds", 300)
    for kind in C.SERVICE_KINDS:
        seen = _last_seen.setdefault(kind, nowt)
        if nowt - seen > stale and kind not in _alerted:
            _alerted.add(kind)
            publish(C.STREAM_NOTIFICATIONS, Notification(
                event="component_down", level="error", title=f"Component down: {kind}",
                message=f"No {kind} instance has sent a heartbeat for {int(nowt - seen)}s."))
        elif nowt - seen <= stale:
            _alerted.discard(kind)


def tick() -> None:
    if redis().set("ait:lock:monitor", settings.host, nx=True, ex=25):  # one scheduler replica at a time
        republish_lost()
        check_components()
