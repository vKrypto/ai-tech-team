import re

from ...common.context import run_agent


def verdict(text: str) -> bool:
    m = re.findall(r"VERDICT:\s*(APPROVED|CHANGES_REQUESTED)", text or "")
    return bool(m) and m[-1] == "APPROVED"


def review(state: dict) -> dict:
    updates = run_agent(state, "review", "team_lead",
                        "Review the change against the request and the plan's acceptance criteria: read every "
                        "changed file, check correctness, edge cases, security and consistency. Be specific "
                        "(file:line). End with exactly one line: VERDICT: APPROVED or VERDICT: CHANGES_REQUESTED",
                        include=["plan_changes", "implement", "test"])
    updates["approved"] = verdict(updates["outputs"]["review"])
    return updates
