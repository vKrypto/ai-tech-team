"""Rules applied on top of the orchestrator's understanding."""
import re

from ...settings import settings
from .schemas import TaskUnderstanding

RULES = [  # (regex, task_type, workflow)
    (r"\bpull request|\bprs?\b|\bpr ?#\d+|/pull/\d+", "pr_review", "pr_review"),
    (r"\breview\b|\baudit\b", "review", "task_execution"),
    (r"\btest(s|ing)?\b|\bqa\b", "testing", "task_execution"),
    (r"\bbug\b|\bfix\b|\berror\b|\bcrash", "bugfix", "coding"),
    (r"\bbacklog\b|\bsprint|\bmilestones?\b|project board|\bscrum\b|stand-?up|\btriage\b|\bkanban\b"
     r"|\b(create|open|close|label|groom)\b.*\bissues?\b|\bissues?\b.*\b(board|labels?)\b",
     "project_management", "scrum"),
    (r"\bdocs?\b|\breadme\b|\bdocument", "docs", "coding"),
    (r"\bdeploy|\bdocker|\bci\b|\binfra", "ops", "coding"),
    (r"\bresearch|\bcompare\b|\binvestigate|\bevaluate\b|\br&d\b", "research", "research"),
    (r"\bplan\b|\bdesign\b|\barchitect", "planning", "task_execution"),
    (r"\bimplement|\badd\b|\bbuild\b|\bcreate\b|\brefactor|\bfeature\b|\bwrite (a|the) (script|function)",
     "development", "coding"),
    (r"\?\s*$|^(what|why|how|which|who|when)\b", "enquiry", "task_execution"),
]


def heuristic(text: str, projects: list[str]) -> TaskUnderstanding:
    t = text.lower().strip()
    project = next((p for p in projects if re.search(rf"\b{re.escape(p.lower())}\b", t)), "general")
    task_type, workflow = "enquiry", "task_execution"
    for rx, tt, wf in RULES:
        if re.search(rx, t):
            task_type, workflow = tt, wf
            break
    words = len(t.split())
    complexity = "low" if words < 12 else "high" if words > 60 else "medium"
    return TaskUnderstanding(
        title=" ".join(text.split()[:8]), summary=text[:200], project=project, project_is_new=False,
        task_type=task_type, workflow=workflow, complexity=complexity,
        model_tier={"low": "fast", "medium": "balanced", "high": "deep"}[complexity],
        rationale="keyword heuristic")


def normalize(u: TaskUnderstanding, projects: list[str], hint: str | None = None) -> TaskUnderstanding:
    if hint and hint in projects:
        u.project, u.project_is_new = hint, False
    if u.project in projects:
        u.project_is_new = False
    elif u.project_is_new and re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,60}", u.project or ""):
        pass  # new project folder, created by the workflow
    else:
        u.project, u.project_is_new = "general", False
    if u.workflow not in (settings.workflows.get("workflows") or {}):
        u.workflow = (settings.workflows.get("task_types") or {}).get(u.task_type, "task_execution")
    if u.workflow == "coding" and u.project == "general":
        u.workflow = "task_execution"  # code changes need a target project
    return u
