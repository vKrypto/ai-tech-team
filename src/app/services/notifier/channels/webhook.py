import httpx

from .base import Channel


class WebhookChannel(Channel):
    """POSTs the whole notification as JSON (for n8n, Zapier, your own service...)."""
    type = "webhook"
    required = ("url",)

    def send(self, n: dict) -> None:
        httpx.post(self.config["url"], json=n, timeout=15).raise_for_status()
