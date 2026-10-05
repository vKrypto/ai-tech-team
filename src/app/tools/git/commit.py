from langchain_core.tools import tool

from ...guardrails.tool_permissions import resolve_path
from ..base import ToolContext, guarded
from ._common import git


def make(ctx: ToolContext):
    g = guarded(ctx)

    @tool
    @g
    def git_commit(message: str, files: list[str] | None = None, path: str = ".") -> str:
        """Stage `files` (default: all changes) and commit them with `message` in the repo at `path`.
        Local commit only; never pushes."""
        cwd = resolve_path(path, ctx.cwd)
        add = git(["add", "--", *files] if files else ["add", "-A"], cwd)
        if add.startswith("git exited"):
            return add
        return git(["commit", "-m", message], cwd)

    return [git_commit]
