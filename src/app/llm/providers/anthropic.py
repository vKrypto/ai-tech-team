"""Anthropic API (token-billed). For the Claude subscription use the claude_code provider."""
from functools import cache

from .base import ChatModelProvider


class AnthropicProvider(ChatModelProvider):
    type = "anthropic"

    @cache
    def chat_model(self, model: str):
        from langchain_anthropic import ChatAnthropic
        kw = {"api_key": self.config["api_key"]} if self.config.get("api_key") else {}
        if self.config.get("base_url"):
            kw["base_url"] = self.config["base_url"]
        return ChatAnthropic(model=model, max_tokens=8192, timeout=300, max_retries=2, **kw)
