import subprocess

from langchain_core.tools import tool

from ...guardrails.tool_permissions import check_command, resolve_path
from ...settings import settings
from ..base import ToolContext, guarded


def run(command: str, cwd, timeout: int | None = None) -> str:
    check_command(command)
    r = subprocess.run(["bash", "-lc", command], cwd=cwd, capture_output=True, text=True,
                       timeout=timeout or settings.cfg("agents.command_timeout_seconds", 600))
    out = (r.stdout + ("\n[stderr]\n" + r.stderr if r.stderr else ""))[-15_000:]
    return f"exit={r.returncode}\n{out}"


def make(ctx: ToolContext):
    g = guarded(ctx)

    @tool
    @g
    def run_command(command: str, cwd: str = ".") -> str:
        """Run any shell command (bash) in `cwd` (relative to the project folder): tests, builds,
        package managers, curl, git, scripts. Full access inside the workspace."""
        return run(command, resolve_path(cwd, ctx.cwd))

    return [run_command]
