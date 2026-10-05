from ....prompts.loader import render
from ...common.context import run_agent
from ..policies import limits, parse_steps


def plan_task(state: dict) -> dict:
    max_steps = limits().get("max_plan_steps", 6)
    updates = run_agent(state, "plan_task", "architect", render("plan_steps", max_steps=max_steps),
                        include=["understand_task"])
    if updates.get("human"):
        return updates
    updates.update(steps=parse_steps(updates["outputs"]["plan_task"], max_steps), step_index=0, replans=0)
    return updates
