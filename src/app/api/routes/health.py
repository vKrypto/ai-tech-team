from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from ...domain.enums import TaskStatus
from ...llm import registry as llm_registry, router as llm_router
from ...llm.capabilities import for_type
from ...observability import metrics
from ...persistence import store, task_repository as tasks
from ...services.common import live_services
from ...services.notifier.channels import registry as channels
from ...settings import settings
from ...tools.filesystem.read import list_projects
from ...workflows import registry

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health():
    store.ping()
    return {"ok": True}


def _routes() -> dict:
    out = {}
    from ...agents.registry import ROLES
    for role in ("orchestrator", *ROLES):
        try:
            out[role] = [p.name for p in llm_router.chain(role)]
        except Exception as e:
            out[role] = [f"error: {e}"]
    return out


@router.get("/api/meta")
def meta():
    return {
        "counts": tasks.counts(),
        "statuses": [s.value for s in TaskStatus],
        "projects": list_projects(),
        "task_types": tasks.distinct("task_type"),
        "workflows": registry.names(),
        "services": live_services(),
        "providers": [{**p.describe(), **for_type(p.type)} for p in llm_registry.providers().values()],
        "routes": _routes(),
        "agents": __import__("app.agents.registry", fromlist=["roster"]).roster(),
        "github": {"enabled": settings.github_enabled, "watch": settings.github_watch_repos,
                   "push": settings.git_push_enabled},
        "workspace_root": str(settings.workspace_root),
        "notification_channels": [c.name for c in channels.enabled()],
        "calendars": len(settings.gcal_ics_urls),
    }


@router.get("/api/metrics", response_class=PlainTextResponse)
def prom():
    return metrics.prometheus()
