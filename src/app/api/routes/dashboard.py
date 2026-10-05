"""Home dashboard: status counts, what's running right now, what waits for you, what just finished."""
from fastapi import APIRouter
from pymongo import DESCENDING

from ... import constants as C
from ...domain.enums import TaskStatus
from ...persistence import task_repository as tasks
from ...persistence.store import db
from ...services.common import live_services

router = APIRouter(prefix="/api", tags=["dashboard"])
FIELDS = {"text": 1, "title": 1, "status": 1, "project": 1, "workflow": 1, "task_type": 1, "turn": 1, "run_id": 1,
          "source": 1, "hold": 1, "error": 1, "created_at": 1, "updated_at": 1, "started_at": 1, "finished_at": 1}


def _out(d: dict) -> dict:
    d = dict(d)
    d["id"] = d.pop("_id")
    return d


def _with_steps(items: list[dict]) -> list[dict]:
    """Attach each task's current step(s) from its run."""
    runs = {r["_id"]: r for r in db()[C.C_RUNS].find({"_id": {"$in": [t["run_id"] for t in items if t.get("run_id")]}},
                                                     {"nodes": 1})}
    for t in items:
        nodes = (runs.get(t.get("run_id")) or {}).get("nodes") or {}
        t["steps_done"] = sum(1 for n in nodes.values() if n.get("status") == "done")
        t["current"] = [k for k, n in nodes.items() if n.get("status") in ("running", "waiting")]
    return items


@router.get("/dashboard")
def dashboard(limit: int = 5):
    col = db()[C.C_TASKS]
    find = lambda flt, sort, n=limit: [_out(d) for d in col.find(flt, FIELDS).sort(sort, DESCENDING).limit(n)]
    counts = tasks.counts()
    services = live_services()
    return {
        "counts": counts,
        "total": sum(counts.values()),
        "running": _with_steps(find({"status": TaskStatus.PROCESSING.value}, "started_at")),
        "queued": find({"status": {"$in": [TaskStatus.CREATED.value, TaskStatus.QUEUED.value]}}, "created_at"),
        "waiting": _with_steps(find({"status": TaskStatus.HOLD.value}, "updated_at")),
        "recent": find({"status": {"$in": [TaskStatus.DONE.value, TaskStatus.FAILED.value,
                                           TaskStatus.CANCELLED.value]}}, "finished_at"),
        "services": {k: sum(1 for s in services if s["kind"] == k) for k in C.SERVICE_KINDS},
        "busy_agents": sum(1 for s in services if s["kind"] == "agent" and s.get("busy")),
        "unread": db()[C.C_NOTIFICATIONS].count_documents({"read": False}),
    }
