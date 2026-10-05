import pytest

from app.llm import fallback, registry, router
from app.llm.providers.base import Cancelled, ProviderError
from app.settings import settings


def test_chain_filters_to_enabled(monkeypatch):
    monkeypatch.setattr(settings, "providers", ["omniroute", "mock"])
    assert [p.name for p in router.chain("senior_engineer")] == ["omniroute", "mock"]
    assert router.chain("orchestrator")[0].name == "omniroute"


def test_no_enabled_provider(monkeypatch):
    monkeypatch.setattr(settings, "providers", [])
    with pytest.raises(ProviderError):
        router.chain("senior_engineer")


def test_all_provider_types_known():
    assert {p.type for p in registry.providers().values()} >= {"claude_code", "openai", "codex", "mock"}


def test_fallback_moves_on_but_not_on_cancel():
    a, b = registry.get("omniroute"), registry.get("mock")
    seen = []

    def fn(p, i):
        seen.append(p.name)
        if p is a:
            raise RuntimeError("down")
        return "ok"
    assert fallback.run([a, b], fn) == ("ok", b) and seen == ["omniroute", "mock"]
    with pytest.raises(Cancelled):
        fallback.run([a, b], lambda p, i: (_ for _ in ()).throw(Cancelled()))
    with pytest.raises(ProviderError):
        fallback.run([a], fn)
