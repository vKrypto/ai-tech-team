"""The scheduler node: dashboard-ui-scheduler (HTTP API + UI), cron-scheduler, google-calendar-scheduler and
the watchdog. All of them create tasks (status: created) and push them to the broker."""
import logging

import uvicorn

from ...persistence import store
from ...settings import settings
from ..common import Service
from . import cron, github, google_calendar, monitor

log = logging.getLogger(__name__)


class SchedulerService(Service):
    kind = "scheduler"

    def setup(self):
        store.ensure_indexes()

    def _loop(self, fn, every: float, name: str):
        def loop():
            while not self.stop.is_set():
                try:
                    fn()
                except Exception:
                    log.exception("%s failed", name)
                self.stop.wait(every)
        self.spawn(loop, name)

    def run(self):
        self._loop(cron.tick, settings.cfg("scheduler.cron_tick_seconds", 30), "cron")
        self._loop(monitor.tick, settings.cfg("scheduler.monitor_tick_seconds", 30), "monitor")
        if settings.github_enabled and settings.github_watch_repos:
            self._loop(github.poll, settings.github_poll_seconds, "github")
        if settings.gcal_ics_urls:
            self._loop(google_calendar.poll, settings.gcal_poll_seconds, "google-calendar")
        from ...api.app import app
        server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=settings.http_port, log_level="info"))
        server.install_signal_handlers = lambda: None
        self.spawn(server.run, "http")
        self.stop.wait()
        server.should_exit = True
