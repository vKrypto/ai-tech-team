"""All tool groups by name; orchestration.tool_selector decides which groups a role gets."""
from ..settings import settings
from . import skills
from .base import ToolContext
from .browser import playwright
from .database import query, schema
from .filesystem import read, search, write
from .git import commit, diff, status
from .github import gh
from .shell import execute
from .web import fetch
from .web import search as web_search

GROUPS = {
    "filesystem": [read, write, search],
    "shell": [execute],
    "git": [status, diff, commit],
    "github": [gh],
    "web": [web_search, fetch],
    "database": [query, schema],
    "browser": [playwright],
    "skills": [skills],
}


def available_groups() -> list[str]:
    off = set()
    if not settings.git_enabled:
        off.add("git")
    if not settings.browser_enabled:
        off.add("browser")
    if not settings.github_enabled:
        off.add("github")
    return [g for g in GROUPS if g not in off]


def build(ctx: ToolContext, groups: list[str]) -> list:
    tools = []
    for gname in groups:
        for module in GROUPS.get(gname, []):
            tools += module.make(ctx)
    return tools
