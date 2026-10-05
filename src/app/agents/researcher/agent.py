from ..base import Agent
from .prompt import PERSONA


class ResearcherAgent(Agent):
    role = "researcher"
    persona = PERSONA
