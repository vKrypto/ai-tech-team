from ...common.context import run_agent


def understand_task(state: dict) -> dict:
    return run_agent(state, "understand_task", "architect",
                     "Restate the goal, the constraints, the expected deliverable and what 'done' means. "
                     "Look at the project if that helps. Do not do the work yet. Be brief.", tier="fast")
