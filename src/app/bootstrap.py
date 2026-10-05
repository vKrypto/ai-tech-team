"""Process start-up shared by every service."""
import os

from .observability import logging as obs_logging
from .persistence import store
from .settings import settings


def init(service: str) -> None:
    obs_logging.setup(service, os.environ.get("AI_TEAM_LOG_LEVEL", "INFO"))
    for d in (settings.data_dir, settings.claude_config_dir):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass


def services() -> dict:
    from .services.agent.service import AgentService
    from .services.engine.service import EngineService
    from .services.notifier.service import NotifierService
    from .services.orchestrator.service import OrchestratorService
    from .services.scheduler.service import SchedulerService
    return {"scheduler": SchedulerService, "orchestrator": OrchestratorService, "engine": EngineService,
            "agent": AgentService, "notifier": NotifierService}


def ready() -> None:
    store.wait_ready()
    store.ensure_indexes()
