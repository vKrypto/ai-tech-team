import re
from typing import Literal

from pydantic import BaseModel, Field

TaskTypeL = Literal["enquiry", "research", "development", "bugfix", "review", "testing", "planning", "docs", "ops",
                   "pr_review", "project_management"]
WorkflowL = Literal["task_execution", "research", "coding", "pr_review", "scrum"]


class TaskUnderstanding(BaseModel):
    title: str = Field(description="Short imperative title, max ~8 words")
    summary: str = Field(description="One or two sentences restating what is wanted")
    project: str = Field(description="Existing project folder, a new kebab-case folder name, or 'general'")
    project_is_new: bool = Field(description="True if the task asks to create a new project folder")
    task_type: TaskTypeL
    workflow: WorkflowL
    complexity: Literal["low", "medium", "high"]
    model_tier: Literal["fast", "balanced", "deep"]
    rationale: str = Field(description="One sentence on why these choices")

    @classmethod
    def heuristic(cls, prompt: str) -> "TaskUnderstanding":
        """Keyword routing (mock provider, and the fallback when every provider fails)."""
        from .policies import heuristic
        projects = re.findall(r"^- (\S+)$", prompt.split("Task:")[0], re.M)
        return heuristic(prompt.rsplit("Task:\n", 1)[-1].split("\n\nDecide:")[0], projects)
