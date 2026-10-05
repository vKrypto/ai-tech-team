from app.services.notifier.channels import formatting, registry
from app.services.notifier.channels.base import Channel


class Flaky(Channel):
    type = "flaky"
    required = ("url",)

    def __init__(self, *a, fail_times=0, **kw):
        super().__init__(*a, **kw)
        self.fail_times, self.sent = fail_times, []

    def send(self, n):
        if self.fail_times:
            self.fail_times -= 1
            raise RuntimeError("boom")
        self.sent.append(n)


def test_enabled_auto_and_filters():
    assert not Flaky("x", {"url": ""}, {}).enabled
    assert not Flaky("x", {"url": "u", "enabled": "false"}, {}).enabled
    ch = Flaky("x", {"url": "u", "events": ["hold"], "projects": "shop"}, {"events": ["done"]})
    assert ch.enabled and ch.events == ["hold"]
    assert ch.accepts({"event": "hold", "project": "shop"})
    assert not ch.accepts({"event": "done", "project": "shop"}) and not ch.accepts({"event": "hold", "project": "x"})


def test_deliver_retries_then_reports(monkeypatch):
    good, bad = Flaky("good", {"url": "u"}, {}, fail_times=2), Flaky("bad", {"url": "u", "retries": 2}, {}, fail_times=9)
    monkeypatch.setattr(registry, "enabled", lambda: [good, bad])
    rep = registry.deliver({"event": "hold", "level": "action", "title": "t", "message": "m"}, sleep=lambda s: None)
    assert rep["good"] == {"status": "ok", "attempts": 3} and len(good.sent) == 1
    assert rep["bad"]["status"] == "error" and rep["bad"]["attempts"] == 2


def test_all_configured_types_load_and_are_off_without_settings():
    chs = {c.name: c for c in registry.channels()}
    assert {"webhook", "ntfy", "slack", "telegram", "email", "whatsapp"} <= set(chs)


def test_formatting_includes_options_and_escapes_html():
    n = {"level": "action", "title": "Need <you>", "message": "pick", "options": [{"id": "A", "label": "x"}],
         "link": "http://h/#task=1"}
    assert "[A] x" in formatting.text(n) and "&lt;you&gt;" in formatting.html_text(n)
