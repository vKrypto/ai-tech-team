"""Provider type -> implementation. A new provider *type* is a class here; a new provider is YAML only."""
from .providers.anthropic import AnthropicProvider
from .providers.base import Provider, ProviderError
from .providers.bedrock import BedrockProvider
from .providers.claude_code import ClaudeCodeProvider
from .providers.codex import CodexProvider
from .providers.google import GoogleProvider
from .providers.mock import MockProvider
from .providers.ollama import OllamaProvider
from .providers.openai import OpenAIProvider

TYPES: dict[str, type[Provider]] = {cls.type: cls for cls in (
    ClaudeCodeProvider, CodexProvider, OpenAIProvider, AnthropicProvider, GoogleProvider, OllamaProvider,
    BedrockProvider, MockProvider)}


def create(name: str, config: dict) -> Provider:
    kind = config.get("type")
    if kind not in TYPES:
        raise ProviderError(f"provider {name!r}: unknown type {kind!r} (known: {', '.join(TYPES)})")
    return TYPES[kind](name, config)
