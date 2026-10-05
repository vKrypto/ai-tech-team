#!/usr/bin/env python3
"""Seed the task store.

    python scripts/seed.py --from-sqlite data/tasks.db   import the v1 (single-container) task history
    python scripts/seed.py --demo                         add a demo cron schedule (paused)

Run with the same AI_TEAM_MONGO_URL/REDIS_URL as the platform (in the stack:
docker exec -it $(docker ps -qf name=ai_team_scheduler) python /app/scripts/seed.py ...).
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app import constants as C  # noqa: E402
from app.persistence import store  # noqa: E402

STATUS = {"done": "done", "failed": "failed", "cancelled": "cancelled"}


def ts(v):
    return datetime.fromisoformat(v) if v else None


def import_sqlite(path: str) -> None:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    db = store.db()
    n = 0
    for r in con.execute("SELECT * FROM tasks ORDER BY id"):
        r = dict(r)
        tid = store.next_id("tasks")
        meta = json.loads(r["metadata"]) if r.get("metadata") else {}
        db[C.C_TASKS].insert_one({
            "_id": tid, "text": r["text"], "title": meta.get("title"), "status": STATUS.get(r["status"], "failed"),
            "source": "import", "source_ref": f"v1:{r['id']}", "metadata": meta or None, "project": r.get("project"),
            "task_type": r.get("task_type"), "workflow": None, "turn": r.get("turn") or 1, "attempt": 1,
            "run_id": None, "hold": None, "result": r.get("result") or r.get("plan"), "error": r.get("error"),
            "sessions": {}, "changed_files": [], "published": True, "created_at": ts(r["created_at"]),
            "updated_at": ts(r.get("finished_at") or r["created_at"]), "finished_at": ts(r.get("finished_at"))})
        for m in con.execute("SELECT * FROM messages WHERE task_id = ? ORDER BY id", (r["id"],)):
            db[C.C_MESSAGES].insert_one({"task_id": tid, "turn": m["turn"], "role": m["role"],
                                         "content": m["content"], "ts": ts(m["ts"])})
        n += 1
    print(f"imported {n} task(s) from {path}")


def demo() -> None:
    from app.services.scheduler import cron
    s = cron.create("weekday repo digest", "0 9 * * 1-5", "Summarise yesterday's commits across all projects")
    store.db()[C.C_SCHEDULES].update_one({"_id": s["_id"]}, {"$set": {"enabled": False}})
    print(f"added paused schedule #{s['_id']}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--from-sqlite")
    p.add_argument("--demo", action="store_true")
    a = p.parse_args()
    store.wait_ready(30)
    store.ensure_indexes()
    if a.from_sqlite:
        import_sqlite(a.from_sqlite)
    if a.demo:
        demo()
    if not (a.from_sqlite or a.demo):
        p.print_help()
