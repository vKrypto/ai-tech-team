"""Build the agent for a job (roles are stateless; per-task state travels in the job and the sessions)."""
from ..domain.events import AgentJob
from . import registry
from .base import Agent


def for_job(job: AgentJob) -> Agent:
    return registry.get(job.role)
