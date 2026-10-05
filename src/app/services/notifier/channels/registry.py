"""Channels from configs/notifications.yaml, and delivery with retries."""
import logging
import time
from functools import cache

from ....settings import load_yaml
from .base import Channel
from .email import EmailChannel
from .ntfy import NtfyChannel
from .slack import SlackChannel
from .telegram import TelegramChannel
from .webhook import WebhookChannel
from .whatsapp import WhatsAppChannel

log = logging.getLogger(__name__)
TYPES: dict[str, type[Channel]] = {c.type: c for c in (
    WebhookChannel, NtfyChannel, SlackChannel, TelegramChannel, EmailChannel, WhatsAppChannel)}


@cache
def channels() -> list[Channel]:
    cfg = load_yaml("notifications.yaml")
    out = []
    for name, c in (cfg.get("channels") or {}).items():
        c = c or {}
        if c.get("type") not in TYPES:
            log.error("notification channel %s: unknown type %r (known: %s)", name, c.get("type"), ", ".join(TYPES))
            continue
        out.append(TYPES[c["type"]](name, c, cfg.get("defaults") or {}))
    return out


def enabled() -> list[Channel]:
    return [c for c in channels() if c.enabled]


def deliver(n: dict, sleep=time.sleep) -> dict:
    """Send to every enabled channel that accepts it. Returns {channel: {status, attempts, error?}}."""
    report = {}
    for ch in enabled():
        if not ch.accepts(n):
            continue
        for attempt in range(1, ch.retries + 1):
            try:
                ch.send(n)
                report[ch.name] = {"status": "ok", "attempts": attempt}
                break
            except Exception as e:
                err = f"{type(e).__name__}: {e}"[:300]
                log.warning("channel %s attempt %s failed: %s", ch.name, attempt, err)
                report[ch.name] = {"status": "error", "attempts": attempt, "error": err}
                if attempt < ch.retries:
                    sleep(2 ** (attempt - 1))
    return report
