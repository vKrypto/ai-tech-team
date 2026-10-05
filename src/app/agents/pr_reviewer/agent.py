from ..base import Agent
from .prompt import PERSONA


class PRReviewerAgent(Agent):
    role = "pr_reviewer"
    persona = PERSONA
