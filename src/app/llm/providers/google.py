"""Google Gemini (pip install 'ai-team[google]')."""
from functools import cache

from .base import ChatModelProvider, ProviderError


class GoogleProvider(ChatModelProvider):
    type = "google"

    @cache
    def chat_model(self, model: str):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as e:
            raise ProviderError("google provider needs langchain-google-genai installed") from e
        kw = {"google_api_key": self.config["api_key"]} if self.config.get("api_key") else {}
        return ChatGoogleGenerativeAI(model=model, max_output_tokens=8192, timeout=300, **kw)
