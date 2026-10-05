from datetime import datetime

from pydantic import BaseModel, Field

from .enums import NodeStatus, RunStatus


class NodeState(BaseModel):
    status: NodeStatus = NodeStatus.PENDING
    attempts: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    output: str | None = None               # preview; full text in artifacts
    error: str | None = None
    agent: str | None = None


class Run(BaseModel):
    """One execution of a workflow for one turn of a task (thread id = run id)."""
    id: str
    task_id: int
    turn: int
    attempt: int
    workflow: str
    status: RunStatus = RunStatus.RUNNING
    mermaid: str = ""
    rerunnable: list[str] = Field(default_factory=list)
    nodes: dict[str, NodeState] = Field(default_factory=dict)
    timeline: list[dict] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


def run_id_for(task_id: int, turn: int, attempt: int) -> str:
    return f"{task_id}-t{turn}-a{attempt}"
