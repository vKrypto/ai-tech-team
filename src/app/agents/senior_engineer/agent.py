from ..base import Agent
from .prompt import PERSONA


class SeniorEngineerAgent(Agent):
    role = "senior_engineer"
    persona = PERSONA
