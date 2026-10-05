from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .enums import Source, TaskStatus


class HoldInfo(BaseModel):
    """Why a task waits for a human, and what the human can choose."""
    kind: str = "human_required"            # human_required | error | approval
    node: str | None = None
    problem: str
    options: list[dict] = Field(default_factory=list)   # [{"id", "label", "details"}]
    run_id: str | None = None


class TaskMetadata(BaseModel):
    """The orchestrator's understanding of a task."""
    title: str
    summary: str = ""
    project: str = "general"
    project_is_new: bool = False
    task_type: str
    workflow: str
    complexity: str = "medium"
    model_tier: str = "balanced"
    rationale: str = ""


class Task(BaseModel):
    id: int
    text: str
    title: str | None = None
    status: TaskStatus = TaskStatus.CREATED
    source: Source = Source.DASHBOARD
    source_ref: str | None = None
    metadata: dict[str, Any] | None = None
    project: str | None = None
    task_type: str | None = None
    workflow: str | None = None
    turn: int = 1
    attempt: int = 1
    run_id: str | None = None
    hold: dict | None = None
    result: str | None = None
    error: str | None = None
    sessions: dict[str, str] = Field(default_factory=dict)
    changed_files: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    finished_at: datetime | None = None
