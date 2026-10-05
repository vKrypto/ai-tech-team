from ....observability import events
from ....orchestration.agent_selector import role_for, route_for


def select_agent(state: dict) -> dict:
    i, steps = state.get("step_index", 0), state.get("steps") or []
    step = steps[i]
    events.emit(state["task_id"], "engine/select_agent", "status",
                f"step {i + 1}/{len(steps)} -> {route_for(step)} ({role_for(step)}): {step['instruction'][:200]}",
                state["run_id"])
    return {"step": step, "outputs": {"select_agent": f"step {i + 1}/{len(steps)}: {step.get('agent')}"}}
