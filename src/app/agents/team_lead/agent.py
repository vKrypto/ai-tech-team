from ..base import Agent
from .prompt import PERSONA


class TeamLeadAgent(Agent):
    role = "team_lead"
    persona = PERSONA
