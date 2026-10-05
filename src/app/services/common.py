"""What every service process shares: startup, heartbeat (Redis + health file), graceful stop."""
import json
import logging
import pathlib
import signal
import threading
import time

from .. import constants as C
from ..persistence import store
from ..persistence.store import now, redis
from ..settings import settings

log = logging.getLogger(__name__)


class Service:
    kind = ""

    def __init__(self, name: str | None = None):
        self.name = name or settings.host       # consumer name + heartbeat identity
        self.stop = threading.Event()
        self.started = now()
        self.threads: list[threading.Thread] = []

    def status(self) -> dict:
        """Extra fields for the heartbeat (busy jobs etc.)."""
        return {}

    def heartbeat(self) -> None:
        key = C.KEY_SERVICE.format(kind=self.kind, host=self.name)
        while not self.stop.is_set():
            try:
                store.ping()
                redis().set(key, json.dumps({"kind": self.kind, "host": self.name, "ts": time.time(),
                                             "started": self.started.isoformat(), **self.status()}), ex=30)
                pathlib.Path(C.HEALTH_FILE).touch()
            except Exception as e:
                log.warning("heartbeat failed: %s", e)
            self.stop.wait(10)

    def spawn(self, target, name: str) -> None:
        t = threading.Thread(target=target, name=name, daemon=True)
        t.start()
        self.threads.append(t)

    def setup(self) -> None:
        pass

    def run(self) -> None:
        """Main loop; returns when self.stop is set."""
        self.stop.wait()

    def start(self, install_signals: bool = True) -> None:
        store.wait_ready()
        self.setup()
        if install_signals:
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, lambda *_: self.stop.set())
        self.spawn(self.heartbeat, f"{self.kind}-heartbeat")
        log.info("%s service up as %s", self.kind, self.name)
        self.run()
        log.info("%s service stopping", self.kind)


def live_services() -> list[dict]:
    out = []
    for key in redis().scan_iter("ait:svc:*", count=200):
        raw = redis().get(key)
        if raw:
            out.append(json.loads(raw))
    return sorted(out, key=lambda s: (C.SERVICE_KINDS.index(s["kind"]) if s["kind"] in C.SERVICE_KINDS else 99,
                                      s["host"]))
