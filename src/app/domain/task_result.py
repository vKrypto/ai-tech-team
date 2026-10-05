from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    """What an agent job hands back to the engine."""
    job_id: str
    ok: bool = True
    text: str = ""
    session: str | None = None              # provider session id, resumed by the next job of this role
    session_key: str | None = None          # "<role>@<provider>" the session belongs to
    provider: str | None = None             # provider that actually answered (after fallbacks)
    model: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    needs_human: dict | None = None         # {"problem", "options"} when the agent is blocked on a human
    error: str | None = None
    cancelled: bool = False
    agent: str | None = None                # replica that ran it
    cost_usd: float | None = None
