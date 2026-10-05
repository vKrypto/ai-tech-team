from ...common.context import run_agent


def apply_actions(state: dict) -> dict:
    return run_agent(state, "apply_actions", "scrum_master",
                     "Execute the planned actions with `gh`, in order. Skip any that are no longer valid and say why. "
                     "Never delete issues, repos, branches or projects. List every change with its link.",
                     include=["plan_actions"])
