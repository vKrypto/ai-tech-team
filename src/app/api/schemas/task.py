from pydantic import BaseModel, Field


class NewTask(BaseModel):
    text: str = Field(min_length=3, max_length=20_000)
    project: str | None = None      # optional hint; the orchestrator decides otherwise


class FollowUp(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)


class Answer(BaseModel):
    option: str | None = None       # id of the chosen option
    text: str | None = Field(default=None, max_length=10_000)


class NewSchedule(BaseModel):
    name: str = ""
    cron: str = Field(min_length=5, description="cron expression, e.g. '0 9 * * 1-5' (UTC)")
    text: str = Field(min_length=3, max_length=20_000)
    project: str | None = None
