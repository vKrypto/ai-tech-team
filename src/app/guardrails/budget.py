"""Per-run budget: how many agent jobs one workflow run may spend."""


class BudgetExceeded(Exception):
    pass


def check(state: dict, policy: dict) -> None:
    limit = int(policy.get("max_agent_jobs", 40))
    if state.get("jobs", 0) >= limit:
        raise BudgetExceeded(f"run used its budget of {limit} agent jobs")
