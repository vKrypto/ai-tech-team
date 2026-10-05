from app.agents.orchestrator.policies import heuristic, normalize
from app.agents.orchestrator.schemas import TaskUnderstanding


def u(**kw):
    base = dict(title="t", summary="s", project="general", project_is_new=False, task_type="development",
                workflow="coding", complexity="low", model_tier="fast", rationale="r")
    return TaskUnderstanding(**{**base, **kw})


def test_heuristic_routes_by_keywords():
    assert heuristic("fix the crash in shop when cart is empty", ["shop"]).workflow == "coding"
    assert heuristic("research vector databases", []).workflow == "research"
    r = heuristic("what does shop do?", ["shop"])
    assert (r.workflow, r.task_type, r.project) == ("task_execution", "enquiry", "shop")


def test_unknown_project_keeps_its_name_and_coding_needs_a_project():
    out = normalize(u(project="nope"), ["shop"])
    assert out.project == "nope" and out.project_is_new is False        # kept: the workflow asks the human
    out = normalize(u(project="Not A Valid Name!"), ["shop"])
    assert out.project == "general" and out.workflow == "task_execution"  # coding needs a real project


def test_new_project_kept_and_hint_wins():
    assert normalize(u(project="new-thing", project_is_new=True), ["shop"]).project == "new-thing"
    assert normalize(u(project="other"), ["shop", "other"], hint="shop").project == "shop"


def test_heuristic_parses_triage_prompt():
    from app.prompts.loader import render
    prompt = render("triage", projects="- shop\n- blog", context="", text="add search to blog")
    r = TaskUnderstanding.heuristic(prompt)
    assert r.project == "blog" and r.workflow == "coding"


def test_named_but_missing_project_is_not_new_unless_asked():
    out = normalize(u(project="job-seeker", project_is_new=True), ["shop"], text="In project job-seeker, change the alerts")
    assert out.project == "job-seeker" and out.project_is_new is False
    out = normalize(u(project="todo-app", project_is_new=False), ["shop"], text="Create a new project todo-app with FastAPI")
    assert out.project_is_new is True
    out = normalize(u(project="todo-app"), ["shop"], text="build a todo app from scratch")
    assert out.project_is_new is True
