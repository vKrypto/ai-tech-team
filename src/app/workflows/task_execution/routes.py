from ...orchestration.agent_selector import route_for
from .policies import limits

# which node holds a step's output, by how the step was executed
_OUTPUT = {"execute_agent": "execute_agent", "coding": "implement", "research": "synthesize",
           "validation": "judge"}


def step_output_node(state: dict) -> str:
    return _OUTPUT[route_for(state.get("step") or {})]


def after_select(state: dict) -> str:
    return route_for(state["step"])


def after_validate(state: dict) -> str:
    if state.get("validation_passed"):
        return "select_agent" if state.get("step_index", 0) < len(state.get("steps") or []) else "complete"
    return "replan" if state.get("replans", 0) < limits().get("max_replans", 2) else "complete"
