"""Full node outputs (the run document keeps only previews)."""
from .. import constants as C
from .store import db, now


def save(run_id: str, task_id: int, node: str, text: str, meta: dict | None = None) -> None:
    db()[C.C_ARTIFACTS].insert_one({"run_id": run_id, "task_id": task_id, "node": node, "text": text,
                                    "meta": meta or {}, "ts": now()})


def for_node(run_id: str, node: str) -> list[dict]:
    return [{k: v for k, v in d.items() if k != "_id"}
            for d in db()[C.C_ARTIFACTS].find({"run_id": run_id, "node": node}).sort("_id", 1)]
