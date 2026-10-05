"""Runtime settings: env vars prefixed AI_TEAM_ (or .env) for infra/secrets, YAML in configs/ for behaviour."""
import os
import re
import socket
from functools import cached_property
from pathlib import Path
from typing import Annotated

import yaml
from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]      # repo root (/app in the image)
CONFIG_DIR = ROOT / "configs"
load_dotenv(ROOT / ".env", override=False)   # so ${VAR} in configs/*.yaml sees .env too
_ENV_REF = re.compile(r"\$\{(\w+)(?::-([^}]*))?\}")


def _interpolate(value):
    if isinstance(value, str):
        return _ENV_REF.sub(lambda m: os.environ.get(m.group(1)) or (m.group(2) or ""), value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v) for v in value]
    return value


def load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    return _interpolate(yaml.safe_load(path.read_text()) or {}) if path.is_file() else {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_TEAM_", env_file=ROOT / ".env", extra="ignore")

    host: str = socket.gethostname()           # consumer name; "<kind>-<slot>" in the stack
    redis_url: str = "redis://localhost:6379/0"
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "ai_team"

    workspace_root: Path = ROOT.parent         # every top-level folder is a project
    hidden_dirs: list[Path] = [ROOT]           # never visible to agents (ai-team itself)
    data_dir: Path = ROOT / "data"             # claude-home, codex, skills (mounted at /data)

    # LLM providers switched on (names from configs/models.yaml). "mock" alone = no LLM calls.
    providers: Annotated[list[str], NoDecode] = ["mock"]
    claude_bin: str = "claude"
    claude_token_file: Path = Path("/run/secrets/claude_oauth_token")
    codex_bin: str = "codex"
    playwright_mcp: str = "playwright-mcp"  # browser for CLI providers ("" disables)

    git_enabled: bool = True
    git_push_enabled: bool = False             # let agents push branches (via gh's credential helper)
    browser_enabled: bool = True
    github_enabled: bool = False               # gh CLI logged in (deploy.sh does the login)
    github_watch_repos: Annotated[list[str], NoDecode] = []   # owner/repo: new PRs become pr_review tasks
    github_watch_filter: str = "review-requested"             # review-requested (to you) | all (every open PR)
    github_poll_seconds: int = 300
    web_search_url: str = ""                   # SearXNG base URL; empty = DuckDuckGo HTML

    http_port: int = 8765
    public_url: str = "http://localhost:8765"  # used in notification links

    gcal_ics_urls: Annotated[list[str], NoDecode] = []              # Google Calendar "secret address in iCal format"
    gcal_tag: str = "[ai]"                     # only events whose title contains this ("" = all)
    gcal_poll_seconds: int = 300

    @field_validator("providers", "gcal_ics_urls", "github_watch_repos", mode="before")
    @classmethod
    def _comma_list(cls, v):
        """Accept `a,b` as well as a JSON list."""
        if isinstance(v, str):
            v = v.strip()
            return yaml.safe_load(v) if v.startswith("[") else [x.strip() for x in v.split(",") if x.strip()]
        return v

    @property
    def claude_config_dir(self) -> Path:
        return self.data_dir / "claude-home"   # shared by agent replicas, so sessions resume anywhere

    @property
    def codex_home(self) -> Path:
        return self.data_dir / "codex"

    @property
    def skills_dir(self) -> Path:
        return self.data_dir / "skills"

    @cached_property
    def app(self) -> dict:
        return load_yaml("app.yaml")

    @cached_property
    def models(self) -> dict:
        return load_yaml("models.yaml")

    @cached_property
    def agents(self) -> dict:
        return load_yaml("agents.yaml")

    @cached_property
    def workflows(self) -> dict:
        return load_yaml("workflows.yaml")

    def cfg(self, path: str, default=None):
        """settings.cfg("agents.job_timeout_seconds") reads configs/app.yaml."""
        node = self.app
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node


settings = Settings()
settings.workspace_root = settings.workspace_root.resolve()
settings.hidden_dirs = [p.resolve() for p in settings.hidden_dirs]
