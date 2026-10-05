"""Deterministic fake agents: the whole platform runs end-to-end with no LLM calls.

Markers in the task text drive test scenarios:
  [ask]   the first planning step asks a human (NEEDS_HUMAN) until it gets an answer
  [fail]  the implement/search/execute step raises, which lands in error handling (retry/abort)
  [slow]  every step takes ~6s (to try cancel / watch progress)
  [code]  task_execution plans a coding sub-workflow step
"""
import json
import time

from pydantic import BaseModel

from .base import AgentRequest, AgentResponse, Cancelled, Provider, ProviderError

ASK_NODES = {"plan_changes", "plan", "plan_task"}
FAIL_NODES = {"implement", "search", "execute_agent"}


class MockProvider(Provider):
    type = "mock"

    def run_agent(self, req: AgentRequest) -> AgentResponse:
        text = req.request.lower()
        if "[slow]" in text:
            for _ in range(12):
                if req.cancelled():
                    raise Cancelled()
                time.sleep(0.5)
        if "[fail]" in text and req.node in FAIL_NODES:
            raise ProviderError(f"mock failure in {req.node}")
        if "[ask]" in text and req.node in ASK_NODES and "human decision" not in req.brief.lower():
            out = ("[mock] I need a decision before planning.\nNEEDS_HUMAN: " + json.dumps({
                "problem": "Which approach should the team take?",
                "options": [{"id": "A", "label": "Minimal change", "details": "Smallest diff"},
                            {"id": "B", "label": "Full rewrite", "details": "Cleaner, more work"}]}))
        else:
            out = self._answer(req, text)
        req.log("message", out)
        return AgentResponse(out, req.session or f"mock-{req.role}-{req.task_id}", "mock")

    def _answer(self, req: AgentRequest, text: str) -> str:
        node = req.node
        if node in ("plan_task", "replan"):
            steps = [{"agent": "researcher", "instruction": "Collect the facts needed"}]
            if "[code]" in text:
                steps.append({"agent": "coding", "instruction": "Make the code change"})
            steps.append({"agent": "architect", "instruction": "Write up the answer"})
            return "[mock] Plan:\n```json\n" + json.dumps(steps) + "\n```"
        if node == "review":
            return "[mock] Looks consistent with the plan.\nVERDICT: APPROVED"
        if node in ("validate_result", "judge"):
            return "[mock] Step output satisfies the instruction.\nVALIDATION: PASS"
        if node == "test":
            return "[mock] No tests to run.\nTESTS: PASS"
        return f"[mock] {req.role} did `{node}` for: {req.request[:120]}"

    def structured(self, prompt: str, schema: type[BaseModel], tier: str = "fast") -> dict:
        heuristic = getattr(schema, "heuristic", None)
        if heuristic is None:
            raise ProviderError(f"mock provider cannot produce {schema.__name__}")
        return heuristic(prompt).model_dump()
