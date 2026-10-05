from app.domain.events import WorkflowCommand
from app.persistence import run_repository as runs, task_repository as tasks
from app.runtime import graph_runner


def test_plan_steps_and_coding_subgraph(make_task):
    tid = make_task("how should tests be structured? [code]", "task_execution")
    graph_runner.handle(WorkflowCommand(kind="start", task_id=tid))
    t = tasks.get(tid)
    assert t["status"] == "done", t["error"]
    nodes = runs.get(t["run_id"])["nodes"]
    for n in ("receive_task", "plan_task", "select_agent", "execute_agent", "implement", "review",
              "validate_result", "complete", "finalize"):
        assert nodes[n]["status"] == "done", n
    assert nodes["select_agent"]["attempts"] == 3   # three planned steps


def test_cancel_stops_the_run(make_task):
    from app.runtime import cancellation
    tid = make_task("research it", "research")
    cancellation.cancel(tid)
    graph_runner.handle(WorkflowCommand(kind="start", task_id=tid))
    assert tasks.get(tid)["status"] == "cancelled"
