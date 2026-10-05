import httpx

from . import formatting
from .base import Channel


class SlackChannel(Channel):
    """Slack incoming webhook."""
    type = "slack"
    required = ("url",)

    def send(self, n: dict) -> None:
        httpx.post(self.config["url"], json={"text": formatting.text(n)}, timeout=15).raise_for_status()
