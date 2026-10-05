"""An agent = a role persona + the provider chain that serves it.

Agent.run executes one job (one workflow step): it builds the system prompt, picks the first enabled
provider for the role, resumes that provider's session for this role if there is one, and falls back to
the next provider if it fails. It also extracts the NEEDS_HUMAN protocol line from the answer.
"""
import json
import re
from dataclasses import dataclass

from ..domain.events import AgentJob
from ..llm import fallback, router
from ..llm.providers.base import AgentRequest, Provider
from ..orchestration import model_selector, tool_selector
from ..prompts.loader import common
from ..settings import settings

NEEDS_HUMAN = re.compile(r"^\s*NEEDS_HUMAN:\s*(\{.*\})\s*$", re.M)


def parse_needs_human(text: str) -> tuple[str, dict | None]:
    """Split the answer into (text without the protocol line, {"problem", "options"} or None)."""
    matches = list(NEEDS_HUMAN.finditer(text or ""))
    if not matches:
        return text, None
    m = matches[-1]
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        data = {"problem": m.group(1)}
    data.setdefault("problem", "The agent needs a human decision.")
    data["options"] = [o if isinstance(o, dict) else {"id": str(o), "label": str(o)}
                       for o in data.get("options") or []]
    return (text[:m.start()] + text[m.end():]).strip(), data


def git_rule() -> str:
    rule = ("git: work for a task happens on its own branch (named in your brief), never on main/master; only the "
            "Senior Engineer commits, other roles inspect; never rewrite published history; ")
    rule += ("you may push a feature branch and open a PR with `gh pr create` when the task asks for it, never push "
             "to the default branch." if settings.git_push_enabled else "never push (no push access).")
    if settings.github_enabled:
        rule += " GitHub: the `gh` CLI is authenticated (issues, PRs, reviews, projects)."
    return rule


def project_dir(project: str | None):
    p = settings.workspace_root / (project or "")
    return p if project and project != "general" and p.is_dir() else settings.workspace_root


@dataclass
class AgentRun:
    text: str
    session_key: str
    session: str | None
    provider: str
    model: str | None
    needs_human: dict | None
    changed: set
    cost_usd: float | None


class Agent:
    role: str = ""
    persona: str = ""

    def system_prompt(self, project: str | None) -> str:
        team = common("team").format(workspace=settings.workspace_root, project=project or "general",
                                     skills_dir=settings.skills_dir, git_rule=git_rule())
        return f"{team}\n\n{self.persona}\n\n{common('needs_human')}"

    def run(self, job: AgentJob, log, cancelled) -> AgentRun:
        system = self.system_prompt(job.project)
        cwd = project_dir(job.project)
        changed: set = set()
        tier = model_selector.tier_for(self.role, job.tier)

        def attempt(provider: Provider, i: int):
            brief = job.brief
            if i > 0:
                brief = ("Note: a previous attempt at this step by another agent failed part-way; check the "
                         "current state of the files before continuing.\n\n" + brief)
            log("status", f"{self.role} on {provider.name} ({provider.model_for(tier) or 'default'}, {tier})",
                {"phase": "provider", "role": self.role, "provider": provider.name, "model": provider.model_for(tier), "tier": tier})
            req = AgentRequest(job_id=job.job_id, task_id=job.task_id, node=job.node, role=self.role,
                               system_prompt=system, brief=brief, tier=tier, cwd=cwd,
                               session=job.sessions.get(f"{self.role}@{provider.name}"),
                               tool_groups=tool_selector.groups_for(self.role), request=job.request,
                               log=log, cancelled=cancelled, changed=changed)
            return provider.run_agent(req)

        resp, provider = fallback.run(
            router.chain(self.role), attempt,
            on_fallback=lambda p, e: log("error", f"{p.name} failed ({type(e).__name__}: {str(e)[:300]}); "
                                                  "falling back to the next provider"))
        text, human = parse_needs_human(resp.text)
        return AgentRun(text, f"{self.role}@{provider.name}", resp.session, provider.name, resp.model, human,
                        changed, resp.cost_usd)
