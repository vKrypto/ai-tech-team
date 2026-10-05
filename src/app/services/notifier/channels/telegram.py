import httpx

from . import formatting
from .base import Channel, as_list


class TelegramChannel(Channel):
    """Telegram Bot API sendMessage. chat_id may list several chats (comma separated)."""
    type = "telegram"
    required = ("bot_token", "chat_id")

    def send(self, n: dict) -> None:
        url = f"https://api.telegram.org/bot{self.config['bot_token']}/sendMessage"
        for chat in as_list(self.config["chat_id"]):
            r = httpx.post(url, json={"chat_id": chat, "text": formatting.html_text(n)[:4000], "parse_mode": "HTML",
                                      "disable_web_page_preview": True}, timeout=15)
            if r.status_code != 200:   # never echo the URL: it contains the bot token
                raise RuntimeError(f"telegram HTTP {r.status_code}: {r.text[:300]}")
