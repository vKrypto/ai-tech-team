from ....memory import context_builder
from ....persistence import task_repository as tasks


def load_context(state: dict) -> dict:
    task = tasks.get(state["task_id"])
    ctx = context_builder.build(task, state.get("turn", 1))
    return {"history": ctx["history"], "project_memory": ctx["project_memory"],
            "project_info": ctx["project_info"], "sessions": task.get("sessions") or {}}
