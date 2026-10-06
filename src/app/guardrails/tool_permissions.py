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


# A command (or the script it runs) that targets something outside the workspace AND changes state there.
_EXTERNAL = re.compile(
    r"(mongodb(\+srv)?://|postgres(ql)?://|mysql://|mariadb://|redis://|amqp://|\b192\.168\.\d+\.\d+|\b10\.\d+\.\d+\.\d+"
    r"|\b172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|\.local\.internal\b|\bssh\s|\bscp\s|\brsync\s.*:|docker\s+(-H|--host|--context)"
    r"|\bkubectl\b|\bpsql\b|\bmongosh\b|\bmysql\s|\bredis-cli\b)", re.I)
_WRITE = re.compile(
    r"(update_one|update_many|insert_one|insert_many|delete_one|delete_many|replace_one|find_one_and_(update|replace|delete)"
    r"|bulk_write|drop_database|drop_collection|\.drop\(|\$set\b|\$unset\b|\bupdateOne\b|\bupdateMany\b|\binsertOne\b|\bdeleteMany\b"
    r"|\bUPDATE\s+\S+\s+SET\b|\bINSERT\s+INTO\b|\bDELETE\s+FROM\b|\bDROP\s+(TABLE|DATABASE|SCHEMA)\b|\bTRUNCATE\b|\bALTER\s+TABLE\b"
    r"|\bFLUSH(ALL|DB)\b|\bdocker\s+(rm|stop|kill|restart|service|stack|exec)\b|\bsystemctl\s+(stop|restart|start|disable)\b"
    r"|\brm\s+-|\bcurl\b.*-X\s*(POST|PUT|PATCH|DELETE))", re.I)
_SCRIPT = re.compile(r"\b(?:python3?|node|bash|sh)\s+([\w./-]+\.(?:py|js|mjs|sh))")


def check_external_write(command: str, cwd: Path, approved: bool) -> None:
    """Writes to production / other machines need a human's approval first (NEEDS_HUMAN)."""
    if approved:
        return
    text = command
    for script in _SCRIPT.findall(command):   # look inside scripts the command runs
        try:
            path = resolve_path(script, cwd)
            if path.is_file() and path.stat().st_size < 500_000:
                text += "\n" + path.read_text(errors="ignore")
        except PermissionDenied:
            pass
    if _EXTERNAL.search(text) and _WRITE.search(text):
        raise PermissionDenied(
            "this writes to a system outside the workspace (production DB/server/network). Do not run it yet: stop "
            "and ask with NEEDS_HUMAN, showing the exact command/query, the target system, what it changes (counts "
            "from a read-only dry run) and how to undo it. It can run after the human approves.")
