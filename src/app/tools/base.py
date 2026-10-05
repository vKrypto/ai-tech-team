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
    log: Callable[..., None] = lambda kind, msg, data=None: None
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
            call_args = {**{f"arg{i}": v for i, v in enumerate(a)}, **kw}
            ctx.log("tool", f"{fn.__name__}({', '.join(args)})", {"tool": fn.__name__, "args": call_args})
            t0 = time.monotonic()
            try:
                out = redact(str(fn(*a, **kw)))[:MAX_OUTPUT]
            except PermissionDenied as e:
                out = f"DENIED: {e}"
            except Exception as e:
                out = f"ERROR: {type(e).__name__}: {e}"
            first = out.strip().splitlines()[0][:160] if out.strip() else "(empty)"
            took = time.monotonic() - t0
            if out.startswith("exit="):        # run_command / gh: success is exit code 0
                ok = out.startswith("exit=0")
            else:
                ok = not out.startswith(("ERROR:", "DENIED:"))
            ctx.log("tool_result", f"{fn.__name__} → {len(out)} chars in {took:.1f}s: {first}",
                    {"tool": fn.__name__, "output": out, "ok": ok, "seconds": round(took, 2)})
            return out
        return wrapper
    return deco
