import httpx

from . import formatting
from .base import Channel, as_list

API = "https://graph.facebook.com/v21.0/{phone_number_id}/messages"


class WhatsAppChannel(Channel):
    """WhatsApp Business Cloud API text message. Note: Meta only delivers free-form text inside a 24h
    window after the recipient last messaged the business number; outside it you need an approved
    template (set `template` in the channel config to send that template instead)."""
    type = "whatsapp"
    required = ("phone_number_id", "token", "to")

    def send(self, n: dict) -> None:
        url = API.format(phone_number_id=self.config["phone_number_id"])
        headers = {"Authorization": f"Bearer {self.config['token']}"}
        for to in as_list(self.config["to"]):
            if self.config.get("template"):
                body = {"messaging_product": "whatsapp", "to": to, "type": "template",
                        "template": {"name": self.config["template"], "language": {"code": "en"}}}
            else:
                body = {"messaging_product": "whatsapp", "to": to, "type": "text",
                        "text": {"body": formatting.text(n)[:4000], "preview_url": False}}
            r = httpx.post(url, json=body, headers=headers, timeout=15)
            if r.status_code >= 300:
                raise RuntimeError(f"whatsapp HTTP {r.status_code}: {r.text[:300]}")
