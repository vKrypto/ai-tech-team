import re

from ...common.context import run_agent


def pr_verdict(text: str) -> str:
    m = re.findall(r"PR_VERDICT:\s*(APPROVE|REQUEST_CHANGES|COMMENT)", text or "")
    return m[-1] if m else "COMMENT"


def review_pr(state: dict) -> dict:
    updates = run_agent(state, "review_pr", "pr_reviewer",
                        "Write the review of this PR as it should appear on GitHub (Markdown): a short summary, then "
                        "**Blocking** issues and **Suggestions**, each specific (file:line) and actionable, plus what "
                        "the verification found. Do not post it yet. End with exactly one line: "
                        "PR_VERDICT: APPROVE, PR_VERDICT: REQUEST_CHANGES or PR_VERDICT: COMMENT",
                        include=["inspect_pr", "verify_pr"])
    updates["approved"] = pr_verdict(updates["outputs"]["review_pr"]) == "APPROVE"
    return updates
