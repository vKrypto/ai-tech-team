from fastapi import HTTPException

from ..persistence import run_repository as runs, task_repository as tasks


def task_or_404(task_id: int) -> dict:
    t = tasks.get(task_id)
    if not t:
        raise HTTPException(404, "task not found")
    return t


def run_or_404(run_id: str) -> dict:
    r = runs.get(run_id)
    if not r:
        raise HTTPException(404, "run not found")
    return r
