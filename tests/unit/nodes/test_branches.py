from app.workflows.common import branches
from app.workflows.common.context import brief


def test_names_follow_the_convention():
    assert branches.task_branch(12, "Add a login page to the shop") == "feat/12-login-page-shop"
    assert branches.subtask_branch(12, "Add a login page to the shop", "Build the API endpoint") == \
        "feat/12-login-page-shop--api-endpoint"
    assert branches.task_branch(7, "!!!") == "feat/7-task"


def test_branch_is_in_the_brief_for_repo_tasks_only():
    state = {"task_id": 12, "title": "Add a login page", "request": "Add a login page", "project": "shop",
             "workflow": "coding"}
    assert "`feat/12-login-page`" in brief(state, "implement", "do it") and "Only if this step changes files" in brief(state, "implement", "do it")
    assert "Git branch" not in brief({**state, "project": "general"}, "implement", "do it")
    step = {**state, "workflow": "task_execution", "steps": [{}], "step": {"agent": "senior_engineer",
                                                                           "instruction": "Write the API"}}
    assert "`feat/12-login-page--api`" in brief(step, "execute_agent", "do it")
