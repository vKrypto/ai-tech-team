from app.domain.events import WorkflowCommand
from app.persistence import run_repository as runs, task_repository as tasks
from app.runtime import graph_runner


def test_coding_runs_every_step(make_task):
    tid = make_task("fix the thing", "coding")
    graph_runner.handle(WorkflowCommand(kind="start", task_id=tid))
    t = tasks.get(tid)
    assert t["status"] == "done", t["error"]
    nodes = runs.get(t["run_id"])["nodes"]
    assert all(nodes[n]["status"] == "done" for n in ("inspect_repo", "plan_changes", "implement", "test", "review"))
    assert "VERDICT: APPROVED" in t["result"]
    assert [m["role"] for m in tasks.list_messages(tid)] == ["user", "assistant"]


def test_human_in_the_loop_resumes_same_node(make_task):
    from app.domain.enums import TaskStatus
    tid = make_task("fix the thing [ask]", "coding")
    graph_runner.handle(WorkflowCommand(kind="start", task_id=tid))
    t = tasks.get(tid)
    assert t["status"] == "hold:human_required" and t["hold"]["node"] == "plan_changes"
    tasks.transition(tid, [TaskStatus.HOLD], TaskStatus.QUEUED)
    graph_runner.handle(WorkflowCommand(kind="resume", task_id=tid, answer={"option": "A"}))
    t = tasks.get(tid)
    assert t["status"] == "done"
    assert runs.get(t["run_id"])["nodes"]["plan_changes"]["attempts"] == 2   # asked, then continued


def test_failure_then_human_abort(make_task):
    from app.domain.enums import TaskStatus
    tid = make_task("fix the thing [fail]", "coding")
    graph_runner.handle(WorkflowCommand(kind="start", task_id=tid))
    t = tasks.get(tid)
    assert t["status"] == "hold:human_required" and t["hold"]["kind"] == "error"
    tasks.transition(tid, [TaskStatus.HOLD], TaskStatus.QUEUED)
    graph_runner.handle(WorkflowCommand(kind="resume", task_id=tid, answer={"option": "abort"}))
    assert tasks.get(tid)["status"] == "failed"


def test_unknown_project_asks_instead_of_inventing_one(make_task):
    from app.domain.enums import TaskStatus
    tid = make_task("change the alert routing in job-seeker", "coding", project="job-seeker", exists=False)
    graph_runner.handle(WorkflowCommand(kind="start", task_id=tid))
    t = tasks.get(tid)
    assert t["status"] == "hold:human_required" and t["hold"]["node"] == "load_context"
    assert {o["id"] for o in t["hold"]["options"]} == {"abort", "create"}
    assert "inspect_repo" not in runs.get(t["run_id"])["nodes"]          # nothing was built
    tasks.transition(tid, [TaskStatus.HOLD], TaskStatus.QUEUED)
    graph_runner.handle(WorkflowCommand(kind="resume", task_id=tid, answer={"option": "abort"}))
    assert tasks.get(tid)["status"] == "failed"


def test_unknown_project_created_when_human_says_so(make_task):
    from app.domain.enums import TaskStatus
    tid = make_task("change the alert routing in job-seeker", "coding", project="job-seeker", exists=False)
    graph_runner.handle(WorkflowCommand(kind="start", task_id=tid))
    tasks.transition(tid, [TaskStatus.HOLD], TaskStatus.QUEUED)
    graph_runner.handle(WorkflowCommand(kind="resume", task_id=tid, answer={"option": "create"}))
    assert tasks.get(tid)["status"] == "done"
