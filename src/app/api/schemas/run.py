from pydantic import BaseModel


class RunSummary(BaseModel):
    id: str
    task_id: int
    turn: int
    attempt: int
    workflow: str
    status: str
