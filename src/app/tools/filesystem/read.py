import os
from pathlib import Path

from langchain_core.tools import tool

from ...guardrails.tool_permissions import is_hidden, resolve_path
from ...settings import settings
from ..base import ToolContext, guarded

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".cache"}


def list_projects() -> list[str]:
    root = settings.workspace_root
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and not p.name.startswith(".") and not is_hidden(p) and p.name not in SKIP_DIRS)


def make(ctx: ToolContext):
    g = guarded(ctx)

    @tool
    @g
    def list_dir(path: str = ".", depth: int = 2) -> str:
        """List files and folders under `path` (relative to the project folder), up to `depth` levels."""
        base = resolve_path(path, ctx.cwd)
        out = []
        for dirpath, dirnames, filenames in os.walk(base):
            d = Path(dirpath)
            dirnames[:] = sorted(n for n in dirnames if n not in SKIP_DIRS and not is_hidden(d / n))
            if len(d.relative_to(base).parts) >= depth:
                dirnames[:] = []
            out += [ctx.rel(d / n) + "/" for n in dirnames] + [ctx.rel(d / f) for f in sorted(filenames)]
            if len(out) > 600:
                out.append("... (truncated)")
                break
        return "\n".join(out) or "(empty)"

    @tool
    @g
    def read_file(path: str, start_line: int = 1, max_lines: int = 500) -> str:
        """Read a text file (path relative to the project folder). Returns numbered lines."""
        lines = resolve_path(path, ctx.cwd).read_text(errors="replace").splitlines()
        chunk = lines[start_line - 1:start_line - 1 + max_lines]
        more = f"\n... ({len(lines)} lines total)" if start_line - 1 + max_lines < len(lines) else ""
        return "\n".join(f"{i}\t{l}" for i, l in enumerate(chunk, start_line)) + more

    return [list_dir, read_file]
