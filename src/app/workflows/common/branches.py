"""Git branch names per task, decided by the engine (not by an agent) so every step, turn and engine replica
agrees on them:

    task      feat/<task_id>-<short-name>                      e.g. feat/12-login-page
    sub-task  feat/<task_id>-<short-name>--<short-sub-name>    e.g. feat/12-login-page--api

Sub-tasks use "--" because git can't have both feat/12-x and feat/12-x/<sub> (a ref can't be a file and a
folder at once).
"""
import re

STOP = {"a", "an", "the", "to", "for", "of", "in", "on", "and", "with", "please", "add", "implement", "create",
        "make", "build", "fix", "update", "write", "new"}


def slug(text: str, words: int = 4, limit: int = 32) -> str:
    tokens = [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in STOP] or ["task"]
    out = "-".join(tokens[:words])[:limit].strip("-")
    return out or "task"


def task_branch(task_id: int, title: str) -> str:
    return f"feat/{task_id}-{slug(title)}"


def subtask_branch(task_id: int, title: str, sub: str) -> str:
    return f"{task_branch(task_id, title)}--{slug(sub, words=3, limit=24)}"


def for_state(state: dict) -> tuple[str, str | None]:
    """(task branch, sub-task branch or None) for the current step."""
    base = task_branch(state["task_id"], state.get("title") or state.get("request", ""))
    step = state.get("step")
    sub = subtask_branch(state["task_id"], state.get("title") or state.get("request", ""), step["instruction"]) \
        if step and state.get("workflow") == "task_execution" else None
    return base, sub


def uses_git(state: dict) -> bool:
    return bool(state.get("project")) and state.get("project") != "general"
