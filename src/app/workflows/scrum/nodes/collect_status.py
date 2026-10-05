from ...common.context import run_agent


def collect_status(state: dict) -> dict:
    return run_agent(state, "collect_status", "scrum_master",
                     "Collect the real current state relevant to the request with `gh` and git: the repo(s), open "
                     "issues and PRs (with labels, assignees, milestones), project boards (`gh project list` / "
                     "`item-list`), recently merged PRs and commits. Summarise it compactly. Change nothing.")
