from ...orchestration.execution_policy import policy


def after_review(state: dict) -> str:
    """"exit" when approved or out of review rounds, else back to "implement"."""
    if state.get("approved") or state.get("rounds", 0) >= policy(state.get("workflow")).get("max_review_rounds", 2):
        return "exit"
    return "implement"
