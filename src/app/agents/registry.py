"""The pre-built agents (roster in configs/agents.yaml, personas in agents/<role>/prompt.py)."""
from ..settings import settings
from .architect.agent import ArchitectAgent
from .base import Agent
from .pr_reviewer.agent import PRReviewerAgent
from .researcher.agent import ResearcherAgent
from .scrum_master.agent import ScrumMasterAgent
from .senior_engineer.agent import SeniorEngineerAgent
from .team_lead.agent import TeamLeadAgent
from .tester.agent import TesterAgent

AGENTS: dict[str, Agent] = {a.role: a for a in (
    ArchitectAgent(), SeniorEngineerAgent(), TeamLeadAgent(), TesterAgent(), PRReviewerAgent(),
    ScrumMasterAgent(), ResearcherAgent())}
ROLES = tuple(AGENTS)


def get(role: str) -> Agent:
    if role not in AGENTS:
        raise KeyError(f"unknown agent role {role!r} (known: {', '.join(AGENTS)})")
    return AGENTS[role]


def roster() -> list[dict]:
    cfg = settings.agents.get("roles") or {}
    return [{"role": r, **{k: v for k, v in (cfg.get(r) or {}).items()}}
            for r in ("orchestrator", *ROLES)]
