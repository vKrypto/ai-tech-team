"""AWS Bedrock (pip install 'ai-team[bedrock]'); credentials from the usual AWS env/config."""
from functools import cache

from .base import ChatModelProvider, ProviderError


class BedrockProvider(ChatModelProvider):
    type = "bedrock"

    @cache
    def chat_model(self, model: str):
        try:
            from langchain_aws import ChatBedrockConverse
        except ImportError as e:
            raise ProviderError("bedrock provider needs langchain-aws installed") from e
        return ChatBedrockConverse(model=model, region_name=self.config.get("region"), max_tokens=8192)
