"""Long-term memory: what the team learned per project, recalled into later tasks on that project."""
from pymongo import DESCENDING

from .. import constants as C
from ..persistence.store import db, now


def remember(project: str, task_id: int, title: str, summary: str) -> None:
    if not project or project == "general" or not summary.strip():
        return
    db()[C.C_MEMORIES].insert_one({"project": project, "task_id": task_id, "title": title,
                                   "summary": summary[:3000], "created_at": now()})


def recall(project: str, limit: int = 5, exclude_task: int | None = None) -> str:
    if not project or project == "general":
        return ""
    flt = {"project": project}
    if exclude_task is not None:
        flt["task_id"] = {"$ne": exclude_task}
    docs = db()[C.C_MEMORIES].find(flt).sort("created_at", DESCENDING).limit(limit)
    return "\n\n".join(f"- Task #{d['task_id']} ({d['title']}): {d['summary'][:800]}" for d in docs)
