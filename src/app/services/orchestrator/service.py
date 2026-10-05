"""The orchestrator (architestrator): consumes tasks from the broker, understands them (type, project,
workflow), and hands them to the workflow engine (status: queued). It also monitors run outcomes from the
engine: notifies on hold/failure/done and applies the auto-retry policy to crashed runs."""
import logging

from ... import constants as C
from ...domain.enums import TaskStatus
from ...domain.events import EngineEvent, Notification, TaskMessage, WorkflowCommand
from ...memory import short_term
from ...observability import events, metrics
from ...orchestration import planner
from ...orchestration.dispatcher import Consumer, publish
from ...orchestration.execution_policy import policy
from ...persistence import task_repository as tasks
from ...runtime import cancellation
from ...settings import settings
from ..common import Service

log = logging.getLogger(__name__)
SRC = "orchestrator"


def handle_task(payload: dict) -> None:
    msg = TaskMessage(**payload)
    task = tasks.get(msg.task_id)
    if task is None or task["status"] != TaskStatus.CREATED:
        log.info("skip %s for task %s (status %s)", msg.kind, msg.task_id, task and task["status"])
        return
    try:
        if msg.kind == "retry":
            fields = {"attempt": task["attempt"] + 1}
            events.emit(task["id"], SRC, "status", f"retry: attempt {fields['attempt']} of turn {task['turn']}")
        else:
            request = short_term.request_for_turn(task, task["turn"])
            meta, used = planner.understand_task(
                task, task["turn"], request,
                on_fallback=lambda p, e: events.emit(task["id"], SRC, "error",
                                                     f"{getattr(p, 'name', 'all providers')} failed: {e}"))
            if task["turn"] > 1:   # keep the first turn's title; record this turn's routing
                meta = {**(task.get("metadata") or {}), **{k: meta[k] for k in
                        ("workflow", "task_type", "model_tier", "complexity", "rationale", "project",
                         "project_is_new", "understood_by")}}
            fields = {"metadata": meta, "title": meta["title"], "project": meta["project"],
                      "task_type": meta["task_type"], "workflow": meta["workflow"]}
            if msg.kind == "followup":
                fields["attempt"] = 1
            events.emit(task["id"], SRC, "status",
                        f"understood by {used}: {meta['task_type']} · project {meta['project']}"
                        f"{' (new)' if meta.get('project_is_new') else ''} · workflow {meta['workflow']} · "
                        f"{meta['model_tier']} — {meta.get('rationale', '')}")
        if not tasks.transition(task["id"], [TaskStatus.CREATED], TaskStatus.QUEUED, **fields):
            return  # cancelled meanwhile
        publish(C.STREAM_WORKFLOWS, WorkflowCommand(kind="start", task_id=task["id"]))
        events.emit(task["id"], SRC, "status", f"queued for the workflow engine ({fields.get('workflow') or task.get('workflow')})")
        metrics.incr("orchestrator.tasks.queued")
    except Exception as e:
        log.exception("could not route task %s", task["id"])
        tasks.set_status(task["id"], TaskStatus.FAILED, error=f"orchestrator: {type(e).__name__}: {e}")
        events.emit(task["id"], SRC, "error", f"{type(e).__name__}: {e}")
        notify_failed(tasks.get(task["id"]), str(e))


def _link(task_id: int) -> str:
    return f"{settings.public_url.rstrip('/')}/#task={task_id}"


def notify_failed(task: dict, error: str) -> None:
    if "failed" in settings.cfg("notifications.events", []):
        publish(C.STREAM_NOTIFICATIONS, Notification(
            event="failed", task_id=task["id"], project=task.get("project"), level="error",
            title=f"Task #{task['id']} failed: {task.get('title') or task['text'][:60]}",
            message=error[:1500], link=_link(task["id"])))


def handle_engine_event(payload: dict) -> None:
    ev = EngineEvent(**payload)
    task = tasks.get(ev.task_id)
    if task is None:
        return
    on = settings.cfg("notifications.events", [])
    title = task.get("title") or task["text"][:60]
    if ev.status == "hold":
        hold = task.get("hold") or {}
        if "hold" in on:
            publish(C.STREAM_NOTIFICATIONS, Notification(
                event="hold", task_id=task["id"], project=task.get("project"), level="action",
                title=f"Human required · task #{task['id']}: {title}",
                message=f"Project: {task.get('project')}\nStep: {hold.get('node')}\nProblem: {hold.get('problem')}",
                options=hold.get("options") or [], link=_link(task["id"])))
    elif ev.status == "failed":
        allowed = int(policy(task.get("workflow")).get("auto_retries", 1))
        if ev.retryable and task["attempt"] <= allowed and not cancellation.is_cancelled(task["id"]):
            events.emit(task["id"], SRC, "status", f"run crashed ({ev.error}); auto-retrying "
                                                   f"(attempt {task['attempt'] + 1})")
            if tasks.transition(task["id"], [TaskStatus.FAILED], TaskStatus.CREATED, published=True, error=None):
                handle_task({"kind": "retry", "task_id": task["id"], "turn": task["turn"]})
            return
        notify_failed(task, ev.error or task.get("error") or "failed")
    elif ev.status == "done" and "done" in on:
        publish(C.STREAM_NOTIFICATIONS, Notification(
            event="done", task_id=task["id"], project=task.get("project"), level="info", title=f"Done · task #{task['id']}: {title}",
            message=(task.get("result") or "")[:1500], link=_link(task["id"])))


class OrchestratorService(Service):
    kind = "orchestrator"

    def setup(self):
        self.tasks = Consumer(C.STREAM_TASKS, C.GROUP_ORCHESTRATOR, handle_task, name=self.name, concurrency=4)
        self.monitor = Consumer(C.STREAM_ENGINE_EVENTS, C.GROUP_ORCHESTRATOR_MONITOR, handle_engine_event,
                                name=self.name)

    def status(self):
        return {"busy": self.tasks.busy}

    def run(self):
        self.spawn(lambda: self.monitor.run(self.stop), "engine-events")
        self.tasks.run(self.stop)
