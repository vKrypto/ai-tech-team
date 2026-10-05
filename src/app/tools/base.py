"""Shared plumbing for tools: the per-job context and the error/log wrapper."""
import functools
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..guardrails.output import redact
from ..guardrails.tool_permissions import PermissionDenied
from ..settings import settings

MAX_OUTPUT = 30_000


@dataclass
class ToolContext:
    cwd: Path                                  # the project folder (or workspace root)
    log: Callable[[str, str], None] = lambda kind, msg: None
    changed: set = field(default_factory=set)  # workspace-relative paths written during the job

    def rel(self, p: Path) -> str:
        try:
            return str(p.resolve().relative_to(settings.workspace_root)) or "."
        except ValueError:
            return str(p)


def guarded(ctx: ToolContext):
    """Log every call; turn exceptions into text the model can react to instead of crashing the job."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            args = [repr(v)[:100] for v in a] + [f"{k}={str(v)[:100]!r}" for k, v in kw.items()]
            ctx.log("tool", f"{fn.__name__}({', '.join(args)})")
            t0 = time.monotonic()
            try:
                out = redact(str(fn(*a, **kw)))[:MAX_OUTPUT]
            except PermissionDenied as e:
                out = f"DENIED: {e}"
            except Exception as e:
                out = f"ERROR: {type(e).__name__}: {e}"
            first = out.strip().splitlines()[0][:160] if out.strip() else "(empty)"
            ctx.log("tool_result", f"{fn.__name__} → {len(out)} chars in {time.monotonic() - t0:.1f}s: {first}")
            return out
        return wrapper
    return deco
