from langchain_core.tools import tool

from ...guardrails.tool_permissions import resolve_path
from ..base import ToolContext, guarded
from ._common import git


def make(ctx: ToolContext):
    g = guarded(ctx)

    @tool
    @g
    def git_diff(path: str = ".", staged: bool = False, ref: str = "") -> str:
        """Diff of the repository at `path`: working tree (default), `staged`, or against `ref`."""
        args = ["diff", "--stat", "-p"] + (["--cached"] if staged else []) + ([ref] if ref else [])
        return git(args, resolve_path(path, ctx.cwd)) or "(no changes)"

    return [git_diff]
