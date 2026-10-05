import httpx

from . import formatting
from .base import Channel


class NtfyChannel(Channel):
    type = "ntfy"
    required = ("url",)

    def send(self, n: dict) -> None:
        headers = {"Title": n["title"].encode("ascii", "replace").decode(),
                   "Priority": {"action": "high", "error": "high"}.get(n.get("level"), "default"),
                   "Tags": {"action": "raising_hand", "error": "x"}.get(n.get("level"), "white_check_mark")}
        if n.get("link"):
            headers["Click"] = n["link"]
        if self.config.get("token"):
            headers["Authorization"] = f"Bearer {self.config['token']}"
        httpx.post(self.config["url"], content=formatting.text(n, with_title=False).encode(), headers=headers,
                   timeout=15).raise_for_status()
