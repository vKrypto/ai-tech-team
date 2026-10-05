"""cron-scheduler: recurring tasks defined on the dashboard (schedules collection)."""
import logging

from pymongo import ReturnDocument

from ... import constants as C
from ...domain.enums import Source
from ...orchestration.scheduler import next_run, valid
from ...persistence.store import db, next_id, now
from . import dashboard

log = logging.getLogger(__name__)


def create(name: str, cron: str, text: str, project: str | None = None) -> dict:
    if not valid(cron):
        raise ValueError(f"invalid cron expression: {cron!r}")
    doc = {"_id": next_id("schedules"), "name": name or text[:40], "cron": cron, "text": text,
           "project": project or None, "enabled": True, "next_run": next_run(cron, now()), "last_run": None,
           "last_task_id": None, "created_at": now()}
    db()[C.C_SCHEDULES].insert_one(doc)
    return doc


def tick() -> int:
    """Fire every due schedule once (claimed atomically, so several schedulers never double-fire)."""
    fired = 0
    while True:
        ts = now()
        doc = db()[C.C_SCHEDULES].find_one_and_update(
            {"enabled": True, "next_run": {"$lte": ts}}, {"$set": {"next_run": None}},
            return_document=ReturnDocument.BEFORE)
        if doc is None:
            return fired
        try:
            task = dashboard.submit(doc["text"], Source.CRON, f"schedule:{doc['_id']}", doc.get("project"))
            db()[C.C_SCHEDULES].update_one({"_id": doc["_id"]}, {"$set": {
                "last_run": ts, "last_task_id": task["id"], "next_run": next_run(doc["cron"], ts)}})
            fired += 1
        except Exception:
            log.exception("schedule %s failed to fire", doc["_id"])
            db()[C.C_SCHEDULES].update_one({"_id": doc["_id"]}, {"$set": {"next_run": next_run(doc["cron"], ts)}})
