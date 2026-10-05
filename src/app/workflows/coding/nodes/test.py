from ...common.context import run_agent


def test(state: dict) -> dict:
    return run_agent(state, "test", "tester",
                     "Cross-verify that the change works as expected, independently of the developer: derive "
                     "scenarios from the request and the plan's acceptance criteria (happy path, edge cases, invalid "
                     "input, nearby regressions), exercise the real thing (run the app/CLI, call the API, use the "
                     "browser) and run the existing suites. Report each scenario with evidence. Do not fix code. "
                     "End with exactly one line: TESTS: PASS, TESTS: FAIL or TESTS: NONE (nothing runnable).",
                     include=["plan_changes", "implement"])
