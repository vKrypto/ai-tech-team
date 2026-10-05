from ..base import Agent
from .prompt import PERSONA


class TesterAgent(Agent):
    role = "tester"
    persona = PERSONA
