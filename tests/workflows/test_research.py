from app.domain.enums import TaskStatus
from app.domain.events import WorkflowCommand
from app.persistence import run_repository as runs, task_repository as tasks
from app.runtime import graph_runner


def test_research_and_rerun_from_node(make_task):
    tid = make_task("research brokers", "research")
    graph_runner.handle(WorkflowCommand(kind="start", task_id=tid))
    t = tasks.get(tid)
    assert t["status"] == "done"
    tasks.set_status(tid, TaskStatus.QUEUED)
    graph_runner.handle(WorkflowCommand(kind="rerun", task_id=tid, run_id=t["run_id"], node="analyze"))
    nodes = runs.get(t["run_id"])["nodes"]
    assert tasks.get(tid)["status"] == "done"
    assert nodes["plan"]["attempts"] == 1 and nodes["search"]["attempts"] == 1
    assert nodes["analyze"]["attempts"] == 2 and nodes["synthesize"]["attempts"] == 2
