from ...orchestration.execution_policy import policy


def after_review(state: dict, exit_to: str) -> str:
    return "post_review" if policy("pr_review").get("post_mode", "comment") != "none" else exit_to
