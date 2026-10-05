MAX_TASK_CHARS = 20_000


class InvalidTask(ValueError):
    pass


def clean_task_text(text: str) -> str:
    text = (text or "").strip()
    if len(text) < 3:
        raise InvalidTask("task text is empty or too short")
    if len(text) > MAX_TASK_CHARS:
        raise InvalidTask(f"task text is longer than {MAX_TASK_CHARS} characters")
    return text
