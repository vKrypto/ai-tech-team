"""The workflow engine's core: drive LangGraph runs for tasks.

One run = one turn (or retry attempt) of a task; its LangGraph thread id is the run id and its state is
checkpointed in Redis after every node. That gives the engine its guarantees:
- crash recovery: a redelivered `start` finds the thread's checkpoint and continues from the last node
- human in the loop: a node that needs a human interrupts; `resume` continues it with the answer
- node re-execution: `rerun` forks the thread from the checkpoint just before that node
"""
import logging
import traceback

from langgraph.types import Command

from .. import constants as C
from ..domain.enums import RunStatus, TaskStatus
from ..domain.events import EngineEvent, WorkflowCommand
from ..domain.execution import run_id_for
from ..memory import short_term
from ..observability import events, metrics
from ..orchestration.dispatcher import publish
from ..persistence import run_repository as runs, task_repository as tasks
from ..settings import settings
from ..workflows import registry
from ..workflows.factory import mermaid
from . import cancellation
from .cancellation import Cancelled
from .run_context import bump_epoch

log = logging.getLogger(__name__)
SRC = "engine"


def _cfg(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def _interrupts(snap) -> list:
    found = list(getattr(snap, "interrupts", None) or [])
    if not found:
        for t in snap.tasks or ():
            found += list(t.interrupts or ())
            if not t.interrupts and getattr(t, "state", None) is not None:  # interrupted inside a subgraph
                found += list(getattr(t.state, "interrupts", None) or [])
    return found


def handle(cmd: WorkflowCommand) -> None:
    task = tasks.get(cmd.task_id)
    if task is None:
        log.warning("command for unknown task %s", cmd.task_id)
        return
    if task["status"] == TaskStatus.CANCELLED:
        events.emit(task["id"], SRC, "status", f"ignoring `{cmd.kind}`: task is cancelled")
        return
    {"start": _start, "resume": _resume, "rerun": _rerun}[cmd.kind](task, cmd)


def _start(task: dict, cmd: WorkflowCommand) -> None:
    run_id = run_id_for(task["id"], task["turn"], task["attempt"])
    wf = task["workflow"]
    g = registry.compiled(wf)
    snap = g.get_state(_cfg(run_id))
    if snap.values:  # redelivered after a crash, or a duplicate: continue, don't restart
        if _interrupts(snap):
            return _settle(task, run_id, g)
        if not snap.next:
            return _settle(task, run_id, g)
        events.emit(task["id"], SRC, "status", f"resuming run {run_id} after interruption at {list(snap.next)}",
                    run_id)
        return _drive(task, run_id, g, None, _cfg(run_id))
    runs.create(run_id, task["id"], task["turn"], task["attempt"], wf, mermaid(g.ait_spec),
                [n for n in g.ait_spec["nodes"]])
    tasks.update(task["id"], run_id=run_id)
    meta = task.get("metadata") or {}
    state = {
        "task_id": task["id"], "run_id": run_id, "turn": task["turn"], "workflow": wf,
        "request": short_term.request_for_turn(task, task["turn"]), "title": task.get("title") or "",
        "project": task.get("project") or "general", "project_is_new": bool(meta.get("project_is_new")),
        "task_type": task.get("task_type") or "", "tier": meta.get("model_tier", "balanced"),
        "outputs": {}, "sessions": {}, "changed_files": [], "seq": 0, "jobs": 0, "approvals": [],
        "human": None, "human_answer": None, "error": None, "failed": False, "step_results": {},
    }
    events.emit(task["id"], SRC, "status", f"started run {run_id} ({wf})", run_id)
    _drive(task, run_id, g, state, _cfg(run_id))


def _resume(task: dict, cmd: WorkflowCommand) -> None:
    hold = task.get("hold") or {}
    run_id = cmd.run_id or hold.get("run_id") or task["run_id"]
    run = runs.get(run_id)
    if run is None:
        events.emit(task["id"], SRC, "error", f"cannot resume: run {run_id} not found")
        return
    events.emit(task["id"], SRC, "status", f"resuming run {run_id} with the human's answer", run_id)
    _drive(task, run_id, registry.compiled(run["workflow"]), Command(resume=cmd.answer or {}), _cfg(run_id))


def _rerun(task: dict, cmd: WorkflowCommand) -> None:
    run_id = cmd.run_id or task["run_id"]
    run = runs.get(run_id)
    g = registry.compiled(run["workflow"])
    snap = next((s for s in g.get_state_history(_cfg(run_id)) if cmd.node in (s.next or ())), None)
    if snap is None:
        events.emit(task["id"], SRC, "error", f"cannot re-run `{cmd.node}`: it never ran in {run_id}", run_id)
        tasks.set_status(task["id"], TaskStatus.FAILED, error=f"re-run: `{cmd.node}` never ran in {run_id}")
        return
    bump_epoch(run_id)   # new job ids: the node and everything after it really run again
    runs.reset_from(run_id, cmd.node)
    events.emit(task["id"], SRC, "status", f"re-running from `{cmd.node}` in {run_id}", run_id)
    _drive(task, run_id, g, None, snap.config)


def _drive(task: dict, run_id: str, g, inp, cfg: dict) -> None:
    tid = task["id"]
    if not tasks.transition(tid, [TaskStatus.QUEUED, TaskStatus.PROCESSING, TaskStatus.HOLD],
                            TaskStatus.PROCESSING, run_id=run_id, error=None, hold=None):
        events.emit(tid, SRC, "status", f"not driving {run_id}: task is {tasks.get(tid)['status']}", run_id)
        return
    runs.set_status(run_id, RunStatus.RUNNING)
    metrics.incr("engine.runs.driven")
    try:
        g.invoke(inp, {**cfg, "recursion_limit": settings.cfg("engine.recursion_limit", 150)})
    except Cancelled:
        return _cancelled(tid, run_id)
    except Exception as e:
        log.exception("run %s crashed", run_id)
        events.emit(tid, SRC, "error", traceback.format_exc()[-4000:], run_id)
        return _failed(tid, run_id, f"engine: {type(e).__name__}: {e}", retryable=True)
    _settle(tasks.get(tid), run_id, g)


def _settle(task: dict, run_id: str, g) -> None:
    """Translate the run's checkpointed state into task/run status."""
    tid = task["id"]
    if cancellation.is_cancelled(tid):
        return _cancelled(tid, run_id)
    snap = g.get_state(_cfg(run_id))
    pending = _interrupts(snap)
    if pending:
        payload = dict(pending[0].value or {})
        payload["run_id"] = run_id
        tasks.set_status(tid, TaskStatus.HOLD, hold=payload)
        runs.set_status(run_id, RunStatus.HOLD)
        events.emit(tid, SRC, "human", f"waiting for a human: {payload.get('problem', '')}", run_id)
        metrics.incr("engine.runs.hold")
        publish(C.STREAM_ENGINE_EVENTS, EngineEvent(task_id=tid, run_id=run_id, status="hold"))
        return
    values = snap.values or {}
    if values.get("failed"):
        err = (values.get("error") or {}).get("message", "workflow failed")
        return _failed(tid, run_id, err, retryable=False)
    tasks.set_status(tid, TaskStatus.DONE, error=None)
    runs.set_status(run_id, RunStatus.DONE)
    events.emit(tid, SRC, "status", f"run {run_id} done", run_id)
    metrics.incr("engine.runs.done")
    publish(C.STREAM_ENGINE_EVENTS, EngineEvent(task_id=tid, run_id=run_id, status="done"))


def _failed(tid: int, run_id: str, error: str, retryable: bool) -> None:
    task = tasks.get(tid)
    tasks.set_status(tid, TaskStatus.FAILED, error=error[:4000])
    tasks.add_message(tid, task["turn"], "system", f"failed: {error[:2000]}")
    runs.set_status(run_id, RunStatus.FAILED, error=error[:4000])
    metrics.incr("engine.runs.failed")
    publish(C.STREAM_ENGINE_EVENTS, EngineEvent(task_id=tid, run_id=run_id, status="failed", error=error[:2000],
                                                retryable=retryable))


def _cancelled(tid: int, run_id: str) -> None:
    tasks.set_status(tid, TaskStatus.CANCELLED)
    runs.set_status(run_id, RunStatus.CANCELLED)
    events.emit(tid, SRC, "status", f"run {run_id} cancelled", run_id)
    publish(C.STREAM_ENGINE_EVENTS, EngineEvent(task_id=tid, run_id=run_id, status="cancelled"))
