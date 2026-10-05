from ..base import Agent
from .prompt import PERSONA


class ArchitectAgent(Agent):
    role = "architect"
    persona = PERSONA
