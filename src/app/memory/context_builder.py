"""Everything an agent should know before starting on a task turn."""
from ..settings import settings
from ..tools.filesystem.read import list_projects
from . import long_term, short_term

SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next"}


def project_info(project: str | None, is_new: bool) -> str:
    if not project or project == "general":
        return "No single target project; work from the workspace root."
    path = settings.workspace_root / project
    if not path.is_dir():
        return f"New project: create the folder `{project}/` in the workspace root." if is_new else \
            f"Project folder `{project}/` does not exist yet."
    entries = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir() if p.name not in SKIP)
    return f"Project `{project}/` top level: " + ", ".join(entries[:80])


def build(task: dict, turn: int) -> dict:
    meta = task.get("metadata") or {}
    project = task.get("project") or meta.get("project")
    return {
        "history": short_term.history(task["id"], turn),
        "project_memory": long_term.recall(project, exclude_task=task["id"]),
        "project_info": project_info(project, bool(meta.get("project_is_new"))),
        "projects": list_projects(),
    }
