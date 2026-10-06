"""Provider interface. A provider is a named, configured LLM source (configs/models.yaml) that can
(a) run an agent job end-to-end with tools and (b) answer one structured (JSON) question.

Two families:
- CLI providers (claude_code, codex) bring their own agent loop, tools and sessions.
- Chat-model providers (openai, anthropic, google, ollama, bedrock) run our LangChain agent loop with
  src/app/tools, keeping the conversation in the Redis checkpointer so sessions resume on any replica.
"""
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pydantic import BaseModel

from ...settings import settings


class Cancelled(Exception):
    pass


class ProviderError(Exception):
    pass


@dataclass
class AgentRequest:
    job_id: str
    task_id: int
    node: str
    role: str
    system_prompt: str
    brief: str
    tier: str
    cwd: Path
    session: str | None = None                   # this provider's session for this role, if any
    tool_groups: list[str] = field(default_factory=list)
    request: str = ""                            # original task text (mock + logs)
    log: Callable[..., None] = lambda kind, msg, data=None: None
    cancelled: Callable[[], bool] = lambda: False
    changed: set = field(default_factory=set)
    human_approved: bool = False


@dataclass
class AgentResponse:
    text: str
    session: str | None = None
    model: str | None = None
    cost_usd: float | None = None


class Provider(ABC):
    type: str = ""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    def model_for(self, tier: str) -> str:
        models = self.config.get("models") or {}
        return models.get(tier) or models.get("balanced") or ""

    @property
    def enabled(self) -> bool:
        return self.name in settings.providers

    @abstractmethod
    def run_agent(self, req: AgentRequest) -> AgentResponse: ...

    @abstractmethod
    def structured(self, prompt: str, schema: type[BaseModel], tier: str = "fast") -> dict: ...

    def describe(self) -> dict:
        return {"name": self.name, "type": self.type, "enabled": self.enabled,
                "models": self.config.get("models") or {}}


class ChatModelProvider(Provider):
    """Our LangChain tool-calling loop on top of any LangChain chat model."""

    @abstractmethod
    def chat_model(self, model: str): ...

    def run_agent(self, req: AgentRequest) -> AgentResponse:
        from langchain.agents import create_agent
        from langchain_core.messages import AIMessage

        from ...persistence import checkpoints
        from ...tools import registry
        from ...tools.base import ToolContext
        from ..pricing.calculator import estimate

        model = self.model_for(req.tier)
        thread = req.session or f"lc:{self.name}:{req.task_id}:{req.role}:{uuid.uuid4().hex[:8]}"
        if req.session:
            req.log("status", f"resuming conversation {thread}")
        ctx = ToolContext(cwd=req.cwd, log=req.log, changed=req.changed, external_writes_approved=req.human_approved)
        agent = create_agent(self.chat_model(model), registry.build(ctx, req.tool_groups),
                             system_prompt=req.system_prompt, name=req.role, checkpointer=checkpoints.get())
        final, tin, tout = "", 0, 0
        steps = settings.cfg("agents.max_steps", 60)
        for update in agent.stream({"messages": [("user", req.brief)]}, stream_mode="updates",
                                   config={"recursion_limit": steps * 2 + 1,
                                           "configurable": {"thread_id": thread}}):
            if req.cancelled():
                raise Cancelled()
            for node in update.values():
                for m in (node or {}).get("messages", []) if isinstance(node, dict) else []:
                    if isinstance(m, AIMessage):
                        usage = m.usage_metadata or {}
                        tin += usage.get("input_tokens", 0)
                        tout += usage.get("output_tokens", 0)
                        if m.text:
                            final = m.text
                            if m.tool_calls:
                                req.log("message", m.text)
        req.log("message", final)
        cost = estimate(model, tin, tout)
        req.log("status", f"{self.name}/{model}: {tin} tokens in, {tout} out"
                          + (f", ~${cost:.3f}" if cost else ""))
        return AgentResponse(final, thread, model, cost)

    def structured(self, prompt: str, schema: type[BaseModel], tier: str = "fast") -> dict:
        model = self.chat_model(self.model_for(tier))
        # function calling works across gateway-routed models, unlike json_schema mode
        out = model.with_structured_output(schema, method="function_calling").invoke(prompt)
        return out.model_dump() if isinstance(out, BaseModel) else dict(out)
