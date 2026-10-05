from ....orchestration.execution_policy import policy
from ...common.context import run_agent
from .review_pr import pr_verdict

FLAG = {"APPROVE": "--approve", "REQUEST_CHANGES": "--request-changes", "COMMENT": "--comment"}


def post_review(state: dict) -> dict:
    review = (state.get("outputs") or {}).get("review_pr", "")
    mode = policy("pr_review").get("post_mode", "comment")
    flag = FLAG[pr_verdict(review)] if mode == "verdict" else "--comment"
    return run_agent(state, "post_review", "pr_reviewer",
                     f"Post the review below on the PR with `gh pr review <number> -R <owner/repo> {flag} "
                     "--body-file <file>` (write the body to a temp file first; drop the PR_VERDICT line from the body, "
                     "state the verdict in the summary instead). Reply with the review URL.\n\n"
                     f"Review to post:\n{review}", include=["inspect_pr"])
