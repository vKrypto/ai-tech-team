"""dashboard-ui-scheduler: everything a person (or the API) can do to a task. Every scheduler funnels new
work through submit(): store the task (status: created) and push it to the broker for the orchestrator."""
from ... import constants as C
from ...domain.enums import FINISHED, TaskStatus
from ...domain.events import TaskMessage, WorkflowCommand
from ...guardrails.input import clean_task_text
from ...observability import events, metrics
from ...orchestration.dispatcher import publish
from ...persistence import run_repository as runs, task_repository as tasks
from ...runtime import cancellation


class Conflict(Exception):
    pass


def _push(task_id: int, kind: str, turn: int) -> None:
    publish(C.STREAM_TASKS, TaskMessage(kind=kind, task_id=task_id, turn=turn))
    tasks.update(task_id, published=True)


def submit(text: str, source: str, source_ref: str | None = None, project: str | None = None) -> dict:
    task = tasks.create(clean_task_text(text), source, source_ref, project or None)
    events.emit(task["id"], f"scheduler/{source}", "status", "created")
    metrics.incr(f"scheduler.tasks.{source}")
    _push(task["id"], "new", 1)
    return tasks.get(task["id"])


def follow_up(task_id: int, text: str) -> dict:
    """Continue the conversation on a finished task: a new turn, routed again by the orchestrator."""
    t = tasks.get(task_id)
    if t["status"] not in FINISHED:
        raise Conflict(f"task is {t['status']}; follow up once it has finished (answer a hold instead)")
    text = clean_task_text(text)
    turn = t["turn"] + 1
    cancellation.clear(task_id)
    tasks.add_message(task_id, turn, "user", text)
    tasks.set_status(task_id, TaskStatus.CREATED, turn=turn, attempt=1, error=None, result=None, published=False)
    events.emit(task_id, "user", "status", f"follow-up (turn {turn}): {text[:200]}")
    _push(task_id, "followup", turn)
    return tasks.get(task_id)


def retry(task_id: int) -> dict:
    """Run the latest turn again as a new attempt (fresh run, same routing)."""
    t = tasks.get(task_id)
    if t["status"] not in (TaskStatus.FAILED, TaskStatus.CANCELLED):
        raise Conflict(f"cannot retry a {t['status']} task")
    cancellation.clear(task_id)
    tasks.delete_messages(task_id, t["turn"], ("assistant", "system"))
    if not t.get("workflow"):   # never got routed: route it from scratch
        tasks.set_status(task_id, TaskStatus.CREATED, error=None, published=False)
        events.emit(task_id, "user", "status", "retry requested")
        _push(task_id, "new", t["turn"])
    else:
        tasks.set_status(task_id, TaskStatus.CREATED, error=None, published=False)
        events.emit(task_id, "user", "status", f"retry requested (turn {t['turn']})")
        _push(task_id, "retry", t["turn"])
    return tasks.get(task_id)


def cancel(task_id: int) -> dict:
    t = tasks.get(task_id)
    if t["status"] in FINISHED:
        raise Conflict(f"task is already {t['status']}")
    cancellation.cancel(task_id)
    tasks.set_status(task_id, TaskStatus.CANCELLED)
    tasks.add_message(task_id, t["turn"], "system", "cancelled")
    events.emit(task_id, "user", "status", "cancelled")
    return tasks.get(task_id)


def answer(task_id: int, option: str | None, text: str | None) -> dict:
    """The human's decision on a held task; the engine resumes the run where it paused."""
    t = tasks.get(task_id)
    if t["status"] != TaskStatus.HOLD:
        raise Conflict(f"task is {t['status']}, not waiting for a human")
    hold = t.get("hold") or {}
    if not option and not (text or "").strip():
        raise Conflict("choose an option or write an answer")
    if option and hold.get("options") and option not in {o.get("id") for o in hold["options"]}:
        raise Conflict(f"unknown option {option!r}")
    if not tasks.transition(task_id, [TaskStatus.HOLD], TaskStatus.QUEUED):
        raise Conflict("task is no longer on hold")
    events.emit(task_id, "user", "human", f"answer: {option or ''} {text or ''}".strip())
    tasks.add_message(task_id, t["turn"], "user", f"[decision on {hold.get('node')}] {option or ''} {text or ''}".strip())
    publish(C.STREAM_WORKFLOWS, WorkflowCommand(kind="resume", task_id=task_id, run_id=hold.get("run_id"),
                                                answer={"option": option, "text": text}))
    return tasks.get(task_id)


def rerun(run_id: str, node: str) -> dict:
    run = runs.get(run_id)
    if run is None:
        raise KeyError(run_id)
    if node not in (run.get("rerunnable") or []):
        raise Conflict(f"`{node}` is not a re-runnable step of this workflow")
    t = tasks.get(run["task_id"])
    if t["status"] not in (*FINISHED, TaskStatus.HOLD):
        raise Conflict(f"task is {t['status']}; wait until it finishes or is on hold")
    if t.get("run_id") != run_id:
        raise Conflict("only the task's latest run can be re-run")
    cancellation.clear(t["id"])
    tasks.set_status(t["id"], TaskStatus.QUEUED, error=None)
    events.emit(t["id"], "user", "status", f"re-run requested from `{node}`", run_id)
    publish(C.STREAM_WORKFLOWS, WorkflowCommand(kind="rerun", task_id=t["id"], run_id=run_id, node=node))
    return tasks.get(t["id"])
