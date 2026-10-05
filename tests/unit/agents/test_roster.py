from app.agents import registry
from app.agents.orchestrator.policies import heuristic
from app.orchestration import tool_selector


def test_prebuilt_agents():
    assert set(registry.ROLES) == {"architect", "senior_engineer", "team_lead", "tester", "pr_reviewer",
                                   "scrum_master", "researcher"}
    roster = {r["role"]: r for r in registry.roster()}
    assert roster["senior_engineer"]["title"] == "Senior Software Engineer" and "orchestrator" in roster
    for role in registry.ROLES:
        assert registry.get(role).persona and "NEEDS_HUMAN" in registry.get(role).system_prompt("shop")


def test_full_access_tools_and_orchestrator_none():
    assert "shell" in tool_selector.groups_for("tester") and tool_selector.groups_for("orchestrator") == []


def test_routes_pr_and_scrum_tasks():
    assert heuristic("please review PR #42 in shop", ["shop"]).workflow == "pr_review"
    assert heuristic("https://github.com/me/shop/pull/7 needs a look", ["shop"]).workflow == "pr_review"
    assert heuristic("groom the backlog and update the sprint board for shop", ["shop"]).workflow == "scrum"
    assert heuristic("fix the issue with login in shop", ["shop"]).workflow == "coding"
