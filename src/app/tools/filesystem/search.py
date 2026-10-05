import fnmatch
import os
import re
from pathlib import Path

from langchain_core.tools import tool

from ...guardrails.tool_permissions import is_hidden, resolve_path
from ..base import ToolContext, guarded
from .read import SKIP_DIRS


def make(ctx: ToolContext):
    g = guarded(ctx)

    @tool
    @g
    def search(pattern: str, path: str = ".", glob: str = "*") -> str:
        """Regex-search file contents under `path`; `glob` filters file names (e.g. '*.py')."""
        base, rx, hits = resolve_path(path, ctx.cwd), re.compile(pattern), []
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [n for n in dirnames if n not in SKIP_DIRS and not is_hidden(Path(dirpath) / n)]
            for f in filenames:
                if not fnmatch.fnmatch(f, glob):
                    continue
                fp = Path(dirpath) / f
                try:
                    for i, line in enumerate(fp.read_text(errors="ignore").splitlines(), 1):
                        if rx.search(line):
                            hits.append(f"{ctx.rel(fp)}:{i}: {line.strip()[:200]}")
                except OSError:
                    continue
                if len(hits) >= 300:
                    return "\n".join(hits) + "\n... (truncated)"
        return "\n".join(hits) or "no matches"

    return [search]
