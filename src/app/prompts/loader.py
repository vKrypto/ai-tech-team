"""Prompt templates live as Markdown next to this file: common/ (shared fragments) and templates/."""
from functools import cache
from pathlib import Path

DIR = Path(__file__).parent


@cache
def _read(rel: str) -> str:
    return (DIR / rel).read_text().strip()


def common(name: str) -> str:
    return _read(f"common/{name}.md")


def render(name: str, **values) -> str:
    return _read(f"templates/{name}.md").format(**values)
