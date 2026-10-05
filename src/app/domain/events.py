"""Envelopes carried on the Redis streams (serialised as JSON in a `data` field)."""
from typing import Literal

from pydantic import BaseModel


class TaskMessage(BaseModel):          # ait:tasks
    kind: Literal["new", "followup", "retry"]
    task_id: int
    turn: int = 1


class WorkflowCommand(BaseModel):      # ait:workflows
    kind: Literal["start", "resume", "rerun"]
    task_id: int
    run_id: str | None = None
    node: str | None = None            # rerun
    answer: dict | None = None         # resume: {"option": ..., "text": ...}


class AgentJob(BaseModel):             # ait:agent-jobs
    job_id: str
    task_id: int
    run_id: str
    node: str
    role: str
    brief: str
    project: str | None = None
    tier: str = "balanced"
    sessions: dict[str, str] = {}      # "<role>@<provider>" -> session id
    request: str = ""                  # original request (mock provider + logging)


class EngineEvent(BaseModel):          # ait:engine-events
    task_id: int
    run_id: str
    status: Literal["done", "failed", "hold", "cancelled"]
    error: str | None = None
    retryable: bool = False


class Notification(BaseModel):         # ait:notifications
    event: str = "info"                # hold | failed | done | component_down | test (channel filters)
    task_id: int | None = None
    project: str | None = None
    level: Literal["info", "action", "error"] = "info"
    title: str
    message: str
    options: list[dict] = []
    link: str | None = None
