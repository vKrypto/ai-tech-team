from ...common.context import run_agent


def synthesize(state: dict) -> dict:
    return run_agent(state, "synthesize", "researcher",
                     "Write the final research report for the requester: answer first, then the supporting "
                     "evidence, trade-offs and a recommendation. Cite sources inline as links.",
                     include=["analyze"])
