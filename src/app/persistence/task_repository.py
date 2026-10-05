"""Tasks, their conversation (messages) and status transitions."""
from pymongo import DESCENDING

from .. import constants as C
from ..domain.enums import FINISHED, TaskStatus
from .store import db, next_id, now

_TS_FIELD = {TaskStatus.QUEUED: "queued_at", TaskStatus.PROCESSING: "started_at"}


def _out(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return doc


def create(text: str, source: str, source_ref: str | None = None, project: str | None = None) -> dict:
    tid = next_id("tasks")
    ts = now()
    doc = {"_id": tid, "text": text, "title": None, "status": TaskStatus.CREATED.value, "source": source,
           "source_ref": source_ref, "metadata": None, "project": project, "project_hint": project,
           "task_type": None, "workflow": None, "turn": 1, "attempt": 1, "run_id": None, "hold": None,
           "result": None, "error": None, "sessions": {}, "changed_files": [], "published": False,
           "created_at": ts, "updated_at": ts, "finished_at": None}
    db()[C.C_TASKS].insert_one(doc)
    add_message(tid, 1, "user", text)
    return _out(doc)


def get(task_id: int) -> dict | None:
    return _out(db()[C.C_TASKS].find_one({"_id": int(task_id)}))


def find(status: str | None = None, task_type: str | None = None, project: str | None = None,
         q: str | None = None, limit: int = 300) -> list[dict]:
    flt: dict = {}
    if status:
        flt["status"] = status
    if task_type:
        flt["task_type"] = task_type
    if project:
        flt["project"] = project
    if q:
        flt["$or"] = [{"text": {"$regex": q, "$options": "i"}}, {"title": {"$regex": q, "$options": "i"}}]
    proj = {"text": 1, "title": 1, "status": 1, "source": 1, "project": 1, "task_type": 1, "workflow": 1,
            "turn": 1, "created_at": 1, "updated_at": 1, "error": 1, "hold": 1, "run_id": 1}
    return [_out(d) for d in db()[C.C_TASKS].find(flt, proj).sort("_id", DESCENDING).limit(limit)]


def update(task_id: int, **fields) -> None:
    fields["updated_at"] = now()
    db()[C.C_TASKS].update_one({"_id": int(task_id)}, {"$set": fields})


def set_status(task_id: int, status: TaskStatus, **fields) -> None:
    fields["status"] = status.value
    if status in _TS_FIELD:
        fields[_TS_FIELD[status]] = now()
    if status in FINISHED:
        fields["finished_at"] = now()
    if status != TaskStatus.HOLD:
        fields.setdefault("hold", None)
    update(task_id, **fields)


def transition(task_id: int, expected: list[TaskStatus], status: TaskStatus, **fields) -> bool:
    """Compare-and-set status change; False if the task is no longer in an expected state."""
    fields.update(status=status.value, updated_at=now())
    if status in _TS_FIELD:
        fields[_TS_FIELD[status]] = now()
    if status in FINISHED:
        fields["finished_at"] = now()
    r = db()[C.C_TASKS].update_one({"_id": int(task_id), "status": {"$in": [s.value for s in expected]}},
                                   {"$set": fields})
    return r.modified_count == 1


def save_sessions(task_id: int, sessions: dict) -> None:
    if sessions:
        db()[C.C_TASKS].update_one({"_id": int(task_id)},
                                   {"$set": {f"sessions.{k}": v for k, v in sessions.items() if v}})


def add_changed_files(task_id: int, files: list[str]) -> None:
    if files:
        db()[C.C_TASKS].update_one({"_id": int(task_id)}, {"$addToSet": {"changed_files": {"$each": files}}})


def add_message(task_id: int, turn: int, role: str, content: str) -> None:
    db()[C.C_MESSAGES].insert_one({"task_id": int(task_id), "turn": turn, "role": role, "content": content,
                                   "ts": now()})


def list_messages(task_id: int) -> list[dict]:
    return [{k: v for k, v in m.items() if k != "_id"}
            for m in db()[C.C_MESSAGES].find({"task_id": int(task_id)}).sort("_id", 1)]


def delete_messages(task_id: int, turn: int, roles: tuple[str, ...]) -> None:
    db()[C.C_MESSAGES].delete_many({"task_id": int(task_id), "turn": turn, "role": {"$in": [*roles]}})


def counts() -> dict:
    out = {s.value: 0 for s in TaskStatus}
    for r in db()[C.C_TASKS].aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
        out[r["_id"]] = r["n"]
    return out


def distinct(field: str) -> list[str]:
    assert field in ("project", "task_type", "workflow", "source")
    return sorted(v for v in db()[C.C_TASKS].distinct(field) if v)


def unpublished(older_than) -> list[dict]:
    return [_out(d) for d in db()[C.C_TASKS].find({"status": TaskStatus.CREATED.value, "published": False,
                                                    "updated_at": {"$lt": older_than}})]
