from fastapi import APIRouter, HTTPException

from ...domain.enums import Source
from ...guardrails.input import InvalidTask
from ...observability import events
from ...persistence import run_repository as runs, task_repository as tasks
from ...services.scheduler import dashboard
from ...services.scheduler.dashboard import Conflict
from ..dependencies import task_or_404
from ..schemas.task import Answer, FollowUp, NewTask

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _call(fn, *a):
    try:
        return fn(*a)
    except Conflict as e:
        raise HTTPException(409, str(e))
    except InvalidTask as e:
        raise HTTPException(422, str(e))


@router.post("", status_code=201)
def create(body: NewTask):
    return _call(dashboard.submit, body.text, Source.DASHBOARD, None, body.project)


@router.get("")
def find(status: str | None = None, task_type: str | None = None, project: str | None = None, q: str | None = None):
    return tasks.find(status, task_type, project, q)


@router.get("/{task_id}")
def get(task_id: int):
    return task_or_404(task_id)


@router.get("/{task_id}/events")
def task_events(task_id: int, after: int = 0):
    task_or_404(task_id)
    return events.list_after(task_id, after)


@router.get("/{task_id}/messages")
def messages(task_id: int):
    task_or_404(task_id)
    return tasks.list_messages(task_id)


@router.post("/{task_id}/messages", status_code=201)
def follow_up(task_id: int, body: FollowUp):
    task_or_404(task_id)
    return _call(dashboard.follow_up, task_id, body.text)


@router.post("/{task_id}/answer")
def answer(task_id: int, body: Answer):
    task_or_404(task_id)
    return _call(dashboard.answer, task_id, body.option, body.text)


@router.post("/{task_id}/cancel")
def cancel(task_id: int):
    task_or_404(task_id)
    return _call(dashboard.cancel, task_id)


@router.post("/{task_id}/retry")
def retry(task_id: int):
    task_or_404(task_id)
    return _call(dashboard.retry, task_id)


@router.get("/{task_id}/runs")
def task_runs(task_id: int):
    task_or_404(task_id)
    return runs.list_for_task(task_id)
