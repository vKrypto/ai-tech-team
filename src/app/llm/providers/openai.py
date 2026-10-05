"""OpenAI or any OpenAI-compatible endpoint (OmniRoute, vLLM, LiteLLM, ...) via `base_url`."""
from functools import cache

from .base import ChatModelProvider


class OpenAIProvider(ChatModelProvider):
    type = "openai"

    @cache
    def chat_model(self, model: str):
        from langchain_openai import ChatOpenAI
        kw = {}
        if self.config.get("base_url"):
            kw["base_url"] = self.config["base_url"]
        # the client insists on a key; keyless gateways ignore it
        kw["api_key"] = self.config.get("api_key") or ("unused" if kw.get("base_url") else None)
        return ChatOpenAI(model=model, max_tokens=8192, timeout=300, max_retries=2, **kw)
