"""Workflow runs and per-node status (what the UI graph is coloured from)."""
from pymongo import DESCENDING

from .. import constants as C
from ..domain.enums import NodeStatus, RunStatus
from .store import db, now

PREVIEW = 4000


def _out(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return doc


def create(run_id: str, task_id: int, turn: int, attempt: int, workflow: str, mermaid: str,
           rerunnable: list[str]) -> None:
    db()[C.C_RUNS].update_one({"_id": run_id}, {"$setOnInsert": {
        "task_id": task_id, "turn": turn, "attempt": attempt, "workflow": workflow, "mermaid": mermaid,
        "rerunnable": rerunnable, "status": RunStatus.RUNNING.value, "nodes": {}, "timeline": [],
        "started_at": now(), "finished_at": None, "error": None}}, upsert=True)


def get(run_id: str) -> dict | None:
    return _out(db()[C.C_RUNS].find_one({"_id": run_id}))


def list_for_task(task_id: int) -> list[dict]:
    return [_out(d) for d in db()[C.C_RUNS].find({"task_id": int(task_id)}, {"mermaid": 0})
            .sort("started_at", DESCENDING)]


def set_status(run_id: str, status: RunStatus, error: str | None = None) -> None:
    fields = {"status": status.value, "error": error}
    if status in (RunStatus.DONE, RunStatus.FAILED, RunStatus.CANCELLED):
        fields["finished_at"] = now()
    db()[C.C_RUNS].update_one({"_id": run_id}, {"$set": fields})


def _node(run_id: str, node: str, status: NodeStatus, extra: dict | None = None, inc: bool = False) -> None:
    ts = now()
    sets = {f"nodes.{node}.status": status.value, **{f"nodes.{node}.{k}": v for k, v in (extra or {}).items()}}
    update = {"$set": sets, "$push": {"timeline": {"node": node, "status": status.value, "ts": ts}}}
    if inc:
        update["$inc"] = {f"nodes.{node}.attempts": 1}
    db()[C.C_RUNS].update_one({"_id": run_id}, update)


def node_start(run_id: str, node: str) -> None:
    _node(run_id, node, NodeStatus.RUNNING, {"started_at": now(), "finished_at": None, "error": None}, inc=True)


def node_done(run_id: str, node: str, output: str | None = None, agent: str | None = None) -> None:
    extra = {"finished_at": now()}
    if output is not None:
        extra["output"] = output[:PREVIEW]
    if agent:
        extra["agent"] = agent
    _node(run_id, node, NodeStatus.DONE, extra)


def node_wait(run_id: str, node: str, problem: str) -> None:
    _node(run_id, node, NodeStatus.WAITING, {"error": problem[:PREVIEW]})


def node_fail(run_id: str, node: str, error: str) -> None:
    _node(run_id, node, NodeStatus.FAILED, {"finished_at": now(), "error": error[:PREVIEW]})


def reset_from(run_id: str, node: str) -> None:
    """Re-run: the node and every node that started after it go back to pending."""
    run = get(run_id) or {}
    nodes = run.get("nodes") or {}
    since = (nodes.get(node) or {}).get("started_at")
    later = [n for n, s in nodes.items() if n == node or (since and s.get("started_at") and s["started_at"] >= since)]
    if later:
        db()[C.C_RUNS].update_one({"_id": run_id}, {"$set": {
            "status": RunStatus.RUNNING.value, "finished_at": None,
            **{f"nodes.{n}.status": NodeStatus.PENDING.value for n in later}}})
