"""Validation sub-workflow: run_checks -> judge. Used for testing/review steps."""
from langgraph.graph import END

from ...common.context import run_agent
from ...factory import GraphBuilder


def run_checks(state: dict) -> dict:
    return run_agent(state, "run_checks", "tester",
                     "Validate what the current step asks: run the relevant tests, builds, linters or the program "
                     "itself, and inspect the code. Record each check with its command and result.")


def judge(state: dict) -> dict:
    return run_agent(state, "judge", "team_lead",
                     "From the checks, give the verdict for the current step: a checklist with [x]/[ ] and "
                     "evidence, then the gaps as concrete fixes. End with exactly one line: "
                     "VALIDATION: PASS or VALIDATION: FAIL", include=["run_checks"])


def subgraph():
    b = GraphBuilder().node("run_checks", run_checks).node("judge", judge).start("run_checks")
    b.then("run_checks", "judge").then("judge", END)
    return b.build(name="validation")
