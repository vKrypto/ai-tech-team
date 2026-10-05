"""Channel interface. A channel turns a notification into a message on some medium.

To add one (say, Discord): create discord.py with a Channel subclass setting `type = "discord"` and
`required = (...)`, implement send(), register it in registry.TYPES, and add an entry to
configs/notifications.yaml.
"""
from abc import ABC, abstractmethod


class Channel(ABC):
    type: str = ""
    required: tuple[str, ...] = ()          # settings that must be filled in for enabled: auto

    def __init__(self, name: str, config: dict, defaults: dict):
        self.name = name
        self.config = config
        self.events = _list(config.get("events")) or _list(defaults.get("events"))
        self.levels = _list(config.get("levels"))
        self.projects = _list(config.get("projects"))
        self.retries = int(config.get("retries") or defaults.get("retries") or 3)

    @property
    def configured(self) -> bool:
        return all(str(self.config.get(k) or "").strip() for k in self.required)

    @property
    def enabled(self) -> bool:
        flag = str(self.config.get("enabled", "auto")).lower()
        if flag in ("false", "no", "off", "0"):
            return False
        return self.configured

    def accepts(self, n: dict) -> bool:
        return ((not self.events or n.get("event") in self.events)
                and (not self.levels or n.get("level") in self.levels)
                and (not self.projects or n.get("project") in self.projects))

    @abstractmethod
    def send(self, n: dict) -> None:
        """Deliver one notification; raise on failure (the registry retries)."""

    def describe(self) -> dict:
        return {"name": self.name, "type": self.type, "enabled": self.enabled, "configured": self.configured,
                "events": self.events, "levels": self.levels, "projects": self.projects}


def _list(v) -> list[str]:
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return list(v or [])


def as_list(v) -> list[str]:
    return _list(v)
