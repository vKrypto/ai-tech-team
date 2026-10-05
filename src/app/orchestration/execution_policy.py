"""Per-workflow limits and error behaviour (configs/workflows.yaml `policies`)."""
from ..settings import settings


def policy(workflow: str | None) -> dict:
    p = settings.workflows.get("policies") or {}
    return {**(p.get("default") or {}), **(p.get(workflow or "") or {})}
