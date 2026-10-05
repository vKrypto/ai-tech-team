from ...common.context import run_agent


def complete(state: dict) -> dict:
    results = sorted((state.get("step_results") or {}).keys(), key=int)
    note = "" if state.get("validation_passed", True) else \
        "\nNote: the last step did not pass validation after the allowed replans; say what is still open."
    return run_agent(state, "complete", "architect",
                     "Write the final answer for the requester from the step results: lead with the answer or "
                     "outcome, then key details, then anything left open." + note,
                     include=["understand_task", *[f"step:{k}" for k in results]])
