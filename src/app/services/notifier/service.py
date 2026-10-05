"""Notification service: every notification is stored (dashboard bell) and forwarded to each enabled channel
whose filters accept it (configs/notifications.yaml: webhook, ntfy, slack, telegram, email, whatsapp, ...).
Delivery results are recorded per channel and logged on the task's activity."""
import logging

from ... import constants as C
from ...domain.events import Notification
from ...guardrails.output import redact
from ...observability import events, metrics
from ...orchestration.dispatcher import Consumer
from ...persistence.store import db, next_id, now
from ..common import Service
from .channels import registry

log = logging.getLogger(__name__)


def handle(payload: dict) -> None:
    n = Notification(**payload).model_dump()
    n["message"] = redact(n["message"])
    nid = next_id("notifications")
    report = registry.deliver({**n, "id": nid})
    db()[C.C_NOTIFICATIONS].insert_one({"_id": nid, **n, "read": False, "created_at": now(), "delivered": report})
    sent = [k for k, v in report.items() if v["status"] == "ok"]
    failed = [f"{k} ({v.get('error')})" for k, v in report.items() if v["status"] != "ok"]
    for k in sent:
        metrics.incr(f"notifications.{k}.ok")
    for k in report:
        if report[k]["status"] != "ok":
            metrics.incr(f"notifications.{k}.failed")
    summary = (f"notification [{n['event']}] '{n['title']}': dashboard"
               + (f", sent via {', '.join(sent)}" if sent else "")
               + (f"; FAILED: {'; '.join(failed)}" if failed else ""))
    log.info(summary)
    if n.get("task_id"):
        events.emit(n["task_id"], "notifier", "error" if failed else "status", summary)


class NotifierService(Service):
    kind = "notifier"

    def setup(self):
        self.consumer = Consumer(C.STREAM_NOTIFICATIONS, C.GROUP_NOTIFIER, handle, name=self.name, concurrency=2)
        log.info("notification channels enabled: %s", ", ".join(c.name for c in registry.enabled()) or "none")

    def status(self):
        return {"channels": [c.name for c in registry.enabled()]}

    def run(self):
        self.consumer.run(self.stop)
