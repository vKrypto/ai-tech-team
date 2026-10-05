from ....orchestration.agent_selector import role_for
from ...common.context import run_agent


def execute_agent(state: dict) -> dict:
    step = state["step"]
    prior = [f"step:{k}" for k in sorted(state.get("step_results") or {})]
    return run_agent(state, "execute_agent", role_for(step),
                     f"Carry out the current step: {step['instruction']}\n"
                     "Use the outputs of earlier steps where relevant. Report the result.",
                     include=["understand_task", *prior])
