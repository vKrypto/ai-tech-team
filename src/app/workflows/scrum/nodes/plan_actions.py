from ...common.context import run_agent


def plan_actions(state: dict) -> dict:
    return run_agent(state, "plan_actions", "scrum_master",
                     "Decide the concrete GitHub actions the request needs (create/update/close/label/assign issues, "
                     "milestones, board moves, comments) as a numbered list, each with the exact `gh` command you "
                     "will run and why. Search for duplicates first. If the request is only a report, say "
                     "'No actions'. Do not run mutating commands yet.", include=["collect_status"])
