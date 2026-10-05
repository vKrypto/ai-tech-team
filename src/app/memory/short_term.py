"""Short-term memory: the task's own conversation (turns), compacted for agents joining mid-way."""
from ..persistence import task_repository as tasks


def history(task_id: int, before_turn: int, limit: int = 2000) -> str:
    lines = []
    for m in tasks.list_messages(task_id):
        if m["turn"] < before_turn and m["role"] in ("user", "assistant"):
            text = m["content"] if len(m["content"]) <= limit else m["content"][:limit] + " ..."
            lines.append(f"[turn {m['turn']} - {m['role']}] {text}")
    return "\n\n".join(lines)


def request_for_turn(task: dict, turn: int) -> str:
    for m in reversed(tasks.list_messages(task["id"])):
        if m["turn"] == turn and m["role"] == "user":
            return m["content"]
    return task["text"]
