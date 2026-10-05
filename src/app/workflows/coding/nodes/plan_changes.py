from ...common.context import run_agent


def plan_changes(state: dict) -> dict:
    return run_agent(state, "plan_changes", "architect",
                     "Write the implementation plan: numbered steps naming the files to touch, risks, and the "
                     "acceptance criteria the reviewer will check. Do not change files.",
                     include=["inspect_repo"])
