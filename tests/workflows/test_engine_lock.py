from app import constants as C
from app.domain.events import WorkflowCommand
from app.persistence import task_repository as tasks
from app.persistence.store import redis
from app.runtime import graph_runner


def test_second_engine_defers_a_locked_task(make_task, monkeypatch):
    tid = make_task("research it", "research")
    monkeypatch.setattr(graph_runner.time, "sleep", lambda s: None)
    redis().set(graph_runner.LOCK.format(task_id=tid), "other-engine", ex=60)   # another engine drives it
    graph_runner.handle(WorkflowCommand(kind="start", task_id=tid))
    assert tasks.get(tid)["status"] == "queued"                               # untouched
    assert redis().xlen(C.STREAM_WORKFLOWS) == 1                               # command put back for later
    redis().delete(graph_runner.LOCK.format(task_id=tid))
    graph_runner.handle(WorkflowCommand(kind="start", task_id=tid))
    assert tasks.get(tid)["status"] == "done"
    assert not redis().exists(graph_runner.LOCK.format(task_id=tid))         # released after the run
