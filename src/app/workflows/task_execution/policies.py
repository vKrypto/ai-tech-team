import json
import re

from ...orchestration.execution_policy import policy

VALID_AGENTS = {"architect", "senior_engineer", "team_lead", "tester", "pr_reviewer", "scrum_master", "researcher",
                "coding", "research", "validation"}


def limits() -> dict:
    return policy("task_execution")


def parse_steps(text: str, max_steps: int) -> list[dict]:
    """The last fenced JSON array in the planner's answer; one generic step if it is missing or broken."""
    blocks = re.findall(r"```(?:json)?\s*(\[.*?\])\s*```", text or "", re.S)
    for raw in reversed(blocks):
        try:
            steps = [s for s in json.loads(raw) if isinstance(s, dict) and s.get("instruction")]
        except json.JSONDecodeError:
            continue
        for s in steps:
            if s.get("agent") not in VALID_AGENTS:
                s["agent"] = "architect"
        if steps:
            return steps[:max_steps]
    return [{"agent": "architect", "instruction": "Carry out the request and report the result."}]


def validation_passed(text: str) -> bool:
    m = re.findall(r"VALIDATION:\s*(PASS|FAIL)", text or "")
    return not m or m[-1] == "PASS"   # no verdict line = don't block on a formatting slip
