from langchain_core.tools import tool

from ...guardrails.tool_permissions import resolve_path
from ..base import ToolContext, guarded
from ._common import git


def make(ctx: ToolContext):
    g = guarded(ctx)

    @tool
    @g
    def git_status(path: str = ".") -> str:
        """Branch, working-tree status and the last 10 commits of the repository at `path`."""
        cwd = resolve_path(path, ctx.cwd)
        return "\n".join([git(["status", "-sb"], cwd), "--- log ---", git(["log", "--oneline", "-10"], cwd)])

    return [git_status]
