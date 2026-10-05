from ..base import Agent
from .prompt import PERSONA


class ScrumMasterAgent(Agent):
    role = "scrum_master"
    persona = PERSONA
