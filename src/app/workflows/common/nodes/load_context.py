from ....memory import context_builder
from ....observability import events
from ....persistence import task_repository as tasks
from ....settings import settings


def missing_project(state: dict) -> str | None:
    project = state.get("project")
    if not project or project == "general" or state.get("project_is_new"):
        return None
    return None if (settings.workspace_root / project).is_dir() else project


def load_context(state: dict, node: str = "load_context") -> dict:
    task = tasks.get(state["task_id"])
    extra = {}
    if (project := missing_project(state)):
        answer = state.get("human_answer") or {}
        if answer.get("node") == node and answer.get("option") == "create":
            extra["project_is_new"] = True
            events.emit(state["task_id"], f"engine/{node}", "status", f"human chose: create `{project}` as a new project")
        else:   # never invent a project the human referred to as existing
            return {"human": {"kind": "human_required", "node": node,
                              "problem": f"Project `{project}` is not in the workspace ({settings.workspace_root}). "
                                         "If it already exists, clone the real repo into the workspace first, then "
                                         "retry this task. Or create it as a brand-new project.",
                              "options": [{"id": "abort", "label": "Stop: I'll add the real repo first",
                                           "details": "Fails this task; retry it after cloning"},
                                          {"id": "create", "label": f"Create `{project}` as a new project",
                                           "details": "The team scaffolds a new repo from scratch"}]}}
    ctx = context_builder.build(task, state.get("turn", 1))
    info = context_builder.project_info(state.get("project"), True) if extra.get("project_is_new") else ctx["project_info"]
    return {"history": ctx["history"], "project_memory": ctx["project_memory"], "project_info": info,
            "sessions": task.get("sessions") or {}, **extra}
