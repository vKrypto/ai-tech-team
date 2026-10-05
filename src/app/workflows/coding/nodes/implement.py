from ...common.context import run_agent


def implement(state: dict) -> dict:
    rounds = state.get("rounds", 0)
    instruction = ("Implement the plan. Write unit tests for the new/changed behaviour and run them, plus the "
                   "linters/build. Keep changes focused and in the project's style.")
    include = ["plan_changes"]
    if rounds > 0 and state.get("outputs", {}).get("review"):
        instruction = ("The Team Lead and/or Tester found problems (below). Address every point, update the unit "
                       "tests, re-run them, then summarise what you changed.")
        include = ["plan_changes", "review", "test"]
    updates = run_agent(state, "implement", "senior_engineer", instruction, include=include)
    updates["rounds"] = rounds + 1
    return updates
