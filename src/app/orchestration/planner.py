"""Task understanding as the orchestrator service uses it (first turn and follow-ups)."""
from ..agents.orchestrator.agent import understand
from ..memory import short_term
from ..tools.filesystem.read import list_projects


def understand_task(task: dict, turn: int, request: str, on_fallback=lambda p, e: None) -> tuple[dict, str]:
    context = ""
    if turn > 1:
        meta = task.get("metadata") or {}
        context = (f"This is a follow-up (turn {turn}) on an existing task.\n"
                   f"Earlier task: {meta.get('title') or task['text'][:200]} "
                   f"(project: {task.get('project')}, workflow: {task.get('workflow')})\n"
                   f"Conversation so far:\n{short_term.history(task['id'], turn, limit=600)}\n\n"
                   "Keep the same project unless the follow-up clearly targets another one.\n\n")
    hint = task.get("project_hint") or (task.get("project") if turn > 1 else None)
    u, provider = understand(request, list_projects(), context, hint, on_fallback)
    meta = u.model_dump()
    meta["understood_by"] = provider
    return meta, provider
