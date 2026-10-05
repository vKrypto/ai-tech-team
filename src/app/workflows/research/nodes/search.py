from ...common.context import run_agent


def search(state: dict) -> dict:
    return run_agent(state, "search", "researcher",
                     "Execute the research plan: search the web, fetch and read the primary sources (use the "
                     "browser for pages that need JavaScript). Collect findings with their URLs and dates.",
                     include=["plan"])
