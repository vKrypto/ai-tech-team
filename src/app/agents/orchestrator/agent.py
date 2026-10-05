"""The orchestrator's brain: understand a task (type, project, workflow, tier) with a structured LLM call."""
import logging

from ...llm import fallback, router
from ...prompts.loader import render
from .policies import normalize
from .prompt import PERSONA
from .schemas import TaskUnderstanding

log = logging.getLogger(__name__)


def understand(text: str, projects: list[str], context: str = "", hint: str | None = None,
               on_fallback=lambda p, e: None) -> tuple[TaskUnderstanding, str]:
    """Returns (understanding, provider name). Falls back to keyword heuristics if every provider fails."""
    prompt = PERSONA + "\n\n" + render("triage", projects="\n".join(f"- {p}" for p in projects) or "(none)",
                                       context=context, text=text)
    try:
        data, provider = fallback.run(router.chain("orchestrator"),
                                      lambda p, i: p.structured(prompt, TaskUnderstanding, "fast"),
                                      on_fallback=on_fallback)
        u, used = TaskUnderstanding.model_validate(data), provider.name
    except Exception as e:
        log.warning("understanding failed on every provider, using heuristics: %s", e)
        on_fallback(None, e)
        u, used = TaskUnderstanding.heuristic(prompt), "heuristic"
    return normalize(u, projects, hint, text), used
