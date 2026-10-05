from ....prompts.loader import render
from ...common.context import run_agent
from ..policies import limits, parse_steps
from ..routes import step_output_node


def replan(state: dict) -> dict:
    i, steps = state.get("step_index", 0), state.get("steps") or []
    max_steps = limits().get("max_plan_steps", 6)
    updates = run_agent(state, "replan", "architect",
                        f"Step {i + 1} did not pass validation (see its output and the validation). Revise the "
                        f"REMAINING plan from this step on so the request still gets done.\n"
                        + render("plan_steps", max_steps=max(1, max_steps - i)),
                        include=[step_output_node(state), "validate_result"])
    if updates.get("human"):
        return updates
    new = parse_steps(updates["outputs"]["replan"], max(1, max_steps - i))
    updates.update(steps=steps[:i] + new, replans=state.get("replans", 0) + 1)
    return updates
