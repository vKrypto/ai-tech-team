"""Local models through Ollama (pip install 'ai-team[ollama]'), or use type: openai with Ollama's /v1."""
from functools import cache

from .base import ChatModelProvider, ProviderError


class OllamaProvider(ChatModelProvider):
    type = "ollama"

    @cache
    def chat_model(self, model: str):
        try:
            from langchain_ollama import ChatOllama
        except ImportError as e:
            raise ProviderError("ollama provider needs langchain-ollama installed") from e
        return ChatOllama(model=model, base_url=self.config.get("base_url") or "http://localhost:11434")
