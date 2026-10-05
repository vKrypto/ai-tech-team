"""State shared by every workflow (and their subgraphs, which share these keys with the parent)."""
from typing import Annotated, TypedDict


def merge(a: dict | None, b: dict | None) -> dict:
    return {**(a or {}), **(b or {})}


def union(a: list | None, b: list | None) -> list:
    return sorted(set(a or []) | set(b or []))


def append(a: list | None, b: list | None) -> list:
    return [*(a or []), *(b or [])]


class WorkflowState(TypedDict, total=False):
    # identity
    task_id: int
    run_id: str
    turn: int
    workflow: str
    # the request and what we know
    request: str
    title: str
    project: str
    project_is_new: bool
    task_type: str
    tier: str
    history: str
    project_memory: str
    project_info: str
    # work products
    outputs: Annotated[dict, merge]          # node -> latest output text
    sessions: Annotated[dict, merge]         # "<role>@<provider>" -> session id
    changed_files: Annotated[list, union]
    seq: int                                 # agent jobs started in this run (part of job ids)
    jobs: int                                # budget counter
    # control
    human: dict | None                       # pending question for a human -> approval node
    human_answer: dict | None                # {"node", "option", "text"} -> consumed by that node
    approvals: Annotated[list, append]       # nodes a human approved (approval_before policy)
    error: dict | None                       # {"node", "message"} -> handle_error node
    failed: bool
    retry_node: str | None
    # task_execution
    steps: list
    step_index: int
    step: dict | None
    step_results: Annotated[dict, merge]
    replans: int
    validation_passed: bool
    # coding
    rounds: int
    approved: bool
    # result
    final: str
