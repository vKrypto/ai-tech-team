from ...common.context import run_agent


def analyze(state: dict) -> dict:
    return run_agent(state, "analyze", "researcher",
                     "Analyze the findings: compare options, check claims against each other, note trade-offs, "
                     "gaps and confidence. If something important is missing, look it up now.",
                     include=["search"])
