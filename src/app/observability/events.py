"""Per-task activity log (what the dashboard shows as 'Activity'): Mongo for history, Redis pub/sub live."""
import json
import logging

from .. import constants as C
from ..guardrails.output import redact
from ..persistence.store import db, now, redis

log = logging.getLogger(__name__)
flow = logging.getLogger("ai_team.flow")   # one line per step in the service logs
MAX = 20_000
LOG_PREVIEW = 300


def emit(task_id: int, source: str, kind: str, content, run_id: str | None = None) -> None:
    """kind: status | message | tool | error | human"""
    text = redact(str(content))[:MAX]
    line = text if len(text) <= LOG_PREVIEW else text[:LOG_PREVIEW] + " ..."
    flow.log(logging.WARNING if kind == "error" else logging.INFO, "task=%s run=%s %s [%s] %s",
             task_id, run_id or "-", source, kind, line.replace("\n", " | "))
    try:
        seq = redis().incr(C.KEY_EVENT_SEQ)
        doc = {"seq": seq, "task_id": int(task_id), "run_id": run_id, "ts": now(), "source": source,
               "kind": kind, "content": text}
        db()[C.C_EVENTS].insert_one(doc)
        doc.pop("_id", None)
        redis().publish(f"ait:live:{task_id}", json.dumps(doc, default=str))
    except Exception:  # the activity log must never break the work it describes
        log.exception("could not record event for task %s", task_id)


def list_after(task_id: int, after: int = 0, limit: int = 2000) -> list[dict]:
    return [{k: v for k, v in d.items() if k != "_id"}
            for d in db()[C.C_EVENTS].find({"task_id": int(task_id), "seq": {"$gt": after}})
            .sort("seq", 1).limit(limit)]
