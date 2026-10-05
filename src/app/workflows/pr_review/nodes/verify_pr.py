from ...common.context import run_agent


def verify_pr(state: dict) -> dict:
    return run_agent(state, "verify_pr", "tester",
                     "Verify the PR actually works, without touching the user's working copy: fetch it into a "
                     "temporary worktree (`git fetch origin pull/<n>/head:ai-pr-<n> && git worktree add "
                     "/tmp/ai-pr-<n> ai-pr-<n>`), install what is needed there, run the tests/build and exercise the "
                     "changed behaviour. Afterwards ALWAYS clean up (`git worktree remove --force /tmp/ai-pr-<n>; "
                     "git branch -D ai-pr-<n>`). Report scenarios with evidence. End with exactly one line: "
                     "TESTS: PASS, TESTS: FAIL or TESTS: NONE.", include=["inspect_pr"])
