from ...common.context import run_agent
from ..policies import validation_passed
from ..routes import step_output_node


def validate_result(state: dict) -> dict:
    node = step_output_node(state)
    updates = run_agent(state, "validate_result", "team_lead",
                        "Check whether the output of the current step satisfies its instruction and moves the "
                        "request forward. Verify claims against the files/sources where cheap. End with exactly "
                        "one line: VALIDATION: PASS or VALIDATION: FAIL (then say what is missing).",
                        include=[node], tier="fast")
    if updates.get("human"):
        return updates
    ok = validation_passed(updates["outputs"]["validate_result"])
    i = state.get("step_index", 0)
    updates["validation_passed"] = ok
    if ok:
        text = (state.get("outputs") or {}).get(node, "")
        updates["step_results"] = {str(i): text}
        updates["outputs"][f"step:{i}"] = text
        updates["step_index"] = i + 1
    return updates
