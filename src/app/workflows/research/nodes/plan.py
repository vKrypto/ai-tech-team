from ...common.context import run_agent


def plan(state: dict) -> dict:
    return run_agent(state, "plan", "researcher",
                     "Plan the research: the key questions to answer, what sources to consult (official docs, "
                     "repos, papers, benchmarks), and search queries. Do not research yet.")
