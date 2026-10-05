from app.domain.events import WorkflowCommand
from app.persistence import artifacts, run_repository as runs, task_repository as tasks
from app.runtime import graph_runner


def test_pr_review_inspects_verifies_reviews_and_posts(make_task):
    tid = make_task("review PR #12 in shop", "pr_review", "shop")
    graph_runner.handle(WorkflowCommand(kind="start", task_id=tid))
    t = tasks.get(tid)
    assert t["status"] == "done", t["error"]
    nodes = runs.get(t["run_id"])["nodes"]
    assert [nodes[n]["status"] for n in ("inspect_pr", "verify_pr", "review_pr", "post_review")] == ["done"] * 4
    roles = {n: artifacts.for_node(t["run_id"], n)[0]["meta"]["role"] for n in ("inspect_pr", "verify_pr", "post_review")}
    assert roles == {"inspect_pr": "pr_reviewer", "verify_pr": "tester", "post_review": "pr_reviewer"}


def test_pr_review_without_posting(make_task, monkeypatch):
    from app.workflows.pr_review import routes
    monkeypatch.setattr(routes, "policy", lambda wf: {"post_mode": "none"})
    tid = make_task("review PR #12 in shop", "pr_review", "shop")
    graph_runner.handle(WorkflowCommand(kind="start", task_id=tid))
    t = tasks.get(tid)
    assert t["status"] == "done" and "post_review" not in runs.get(t["run_id"])["nodes"]


def test_scrum_runs_all_steps_as_scrum_master(make_task):
    tid = make_task("groom the backlog of shop", "scrum", "shop")
    graph_runner.handle(WorkflowCommand(kind="start", task_id=tid))
    t = tasks.get(tid)
    assert t["status"] == "done"
    for n in ("collect_status", "plan_actions", "apply_actions", "report"):
        assert artifacts.for_node(t["run_id"], n)[0]["meta"]["role"] == "scrum_master"


def test_coding_uses_the_roster(make_task):
    tid = make_task("fix the thing", "coding")
    graph_runner.handle(WorkflowCommand(kind="start", task_id=tid))
    run_id = tasks.get(tid)["run_id"]
    role = lambda n: artifacts.for_node(run_id, n)[0]["meta"]["role"]
    assert (role("plan_changes"), role("implement"), role("test"), role("review")) == \
        ("architect", "senior_engineer", "tester", "team_lead")
