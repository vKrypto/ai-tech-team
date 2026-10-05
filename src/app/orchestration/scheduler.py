"""Cron schedule maths for the cron scheduler (schedules collection)."""
from datetime import datetime

from croniter import croniter


def valid(expr: str) -> bool:
    return croniter.is_valid(expr)


def next_run(expr: str, after: datetime) -> datetime:
    return croniter(expr, after).get_next(datetime)
