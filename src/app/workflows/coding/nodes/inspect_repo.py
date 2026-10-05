from ...common.context import run_agent


def inspect_repo(state: dict) -> dict:
    new = state.get("project_is_new")
    instruction = (
        f"The project `{state.get('project')}` is NEW: create its folder in the workspace root and set up a "
        "minimal skeleton suited to the request (README, package/project file, git init). Then describe it."
        if new else
        "Inspect the project for this task: structure, stack, how to build/test/run it, conventions, and the "
        "files and functions relevant to the request. Report concisely; change nothing.")
    return run_agent(state, "inspect_repo", "architect", instruction)
