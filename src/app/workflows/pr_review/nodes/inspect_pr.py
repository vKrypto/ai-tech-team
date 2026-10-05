from ...common.context import run_agent


def inspect_pr(state: dict) -> dict:
    return run_agent(state, "inspect_pr", "pr_reviewer",
                     "Identify the pull request from the request (number, URL or branch; repo from the project's git "
                     "remote or the URL). With `gh`, gather: title, description, author, base/head, linked issues, "
                     "CI status (`gh pr checks`), existing reviews/comments, the full diff (`gh pr diff`), and the "
                     "surrounding code of the changed parts. Summarise what the PR does and what to look at closely. "
                     "Start your answer with a line `PR: <owner/repo>#<number>`. Change nothing.")
