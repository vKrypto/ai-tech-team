from ...common.context import run_agent


def report(state: dict) -> dict:
    return run_agent(state, "report", "scrum_master",
                     "Write the final report for the requester: what you changed (with links), then the status "
                     "overview (done / in progress / blocked / next up), and risks or decisions needed.",
                     include=["collect_status", "apply_actions"])
