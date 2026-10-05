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


def test_unknown_project_becomes_general_and_coding_needs_a_project():
    out = normalize(u(project="nope"), ["shop"])
    assert out.project == "general" and out.workflow == "task_execution"


def test_new_project_kept_and_hint_wins():
    assert normalize(u(project="new-thing", project_is_new=True), ["shop"]).project == "new-thing"
    assert normalize(u(project="other"), ["shop", "other"], hint="shop").project == "shop"


def test_heuristic_parses_triage_prompt():
    from app.prompts.loader import render
    prompt = render("triage", projects="- shop\n- blog", context="", text="add search to blog")
    r = TaskUnderstanding.heuristic(prompt)
    assert r.project == "blog" and r.workflow == "coding"
