from ....guardrails.input import InvalidTask, clean_task_text


def validate_task(state: dict) -> dict:
    try:
        return {"request": clean_task_text(state.get("request", ""))}
    except InvalidTask as e:
        return {"failed": True, "error": {"node": "validate_task", "message": str(e)}}
