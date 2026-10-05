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


GROUP_INFO = {
    "filesystem": "Read, write, edit and search files in the workspace",
    "shell": "Run any shell command (bash): tests, builds, scripts. Installed: python + pytest + uv, node + npm, git, gh, curl, jq, ripgrep, sqlite3",
    "git": "Status, diff and local commits (push only when enabled)",
    "github": "GitHub CLI: pull requests, reviews, issues, projects",
    "web": "Web search and HTTP requests",
    "database": "Query and inspect SQLite databases",
    "browser": "Headless Chromium: open pages, click, fill, run JS, screenshots",
    "skills": "List and load skills (packaged know-how) from the skills library",
}


def catalog() -> dict[str, list[dict]]:
    """Every tool per group, introspected from the tool code itself (names + first docstring line), so the
    dashboard always shows what agents can really call."""
    from pathlib import Path
    ctx = ToolContext(cwd=Path("."))
    out = {}
    for gname, modules in GROUPS.items():
        out[gname] = [{"name": t.name, "description": (t.description or "").strip().split("\n")[0]}
                      for m in modules for t in m.make(ctx)]
    return out
