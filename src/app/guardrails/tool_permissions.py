"""Full-access mode, with a few hard lines: the platform's own folder and mounted secrets stay out of reach,
and commands that would wreck the host/container are refused."""
import os
import re
from pathlib import Path

from ..settings import settings


class PermissionDenied(Exception):
    pass


SECRET_DIRS = [Path("/run/secrets")]
_DESTRUCTIVE = re.compile(
    r"\brm\s+-[a-z]*r[a-z]*\s+(/|~|\$HOME)(\s|$)|\bmkfs\b|\bdd\s+if=.*\bof=/dev/|\bshutdown\b|\breboot\b"
    r"|:\(\)\s*\{|/run/secrets|claude_oauth_token|\bsudo\b")


def is_hidden(p: Path) -> bool:
    p = p.resolve()
    return any(p == h or h in p.parents for h in [*settings.hidden_dirs, *SECRET_DIRS])


def resolve_path(path: str, base: Path | None = None) -> Path:
    """Paths are relative to the workspace root (or absolute inside it)."""
    root = settings.workspace_root
    p = Path(path) if os.path.isabs(path) else (base or root) / path
    p = p.resolve()
    if p != root and root not in p.parents:
        raise PermissionDenied(f"{path!r} is outside the workspace ({root})")
    if is_hidden(p):
        raise PermissionDenied(f"{path!r} is off-limits")
    return p


def check_command(command: str) -> None:
    if _DESTRUCTIVE.search(command):
        raise PermissionDenied("command refused: destructive to the host or touches platform secrets")
