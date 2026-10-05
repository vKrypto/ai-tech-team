"""An agent node: consumes agent jobs and runs them with the role's provider chain (full-access tools,
skills, browser). Several replicas share the consumer group; a crashed replica's job is taken over."""
import logging
import time

from ... import constants as C
from ...domain.events import AgentJob
from ...llm import registry as llm_registry
from ...orchestration.dispatcher import Consumer
from ...runtime import executor
from ...settings import settings
from ..common import Service

log = logging.getLogger(__name__)


CURRENT: dict[str, dict] = {}   # job id -> what this replica is doing right now (reported in its heartbeat)


def handle_job(payload: dict) -> None:
    job = AgentJob(**payload)
    if executor.existing_result(job.job_id):   # finished before a crash, just not acked
        return
    CURRENT[job.job_id] = {"role": job.role, "task_id": job.task_id, "node": job.node, "since": time.time()}
    try:
        executor.deliver(executor.execute(job))
    finally:
        CURRENT.pop(job.job_id, None)


class AgentService(Service):
    kind = "agent"

    def setup(self):
        if settings.github_enabled and settings.git_push_enabled:
            import subprocess
            r = subprocess.run(["gh", "auth", "setup-git"], capture_output=True, text=True)
            log.info("git push via gh credential helper: %s", "on" if r.returncode == 0 else r.stderr.strip())
        self.consumer = Consumer(C.STREAM_AGENT_JOBS, C.GROUP_AGENTS, handle_job,
                                 name=self.name, concurrency=settings.cfg("agents.concurrency", 1))
        log.info("providers enabled: %s", ", ".join(p.name for p in llm_registry.enabled()) or "none")

    def status(self):
        return {"busy": self.consumer.busy, "capacity": self.consumer.concurrency,
                "providers": [p.name for p in llm_registry.enabled()], "jobs": list(CURRENT.values())}

    def run(self):
        self.consumer.run(self.stop)
