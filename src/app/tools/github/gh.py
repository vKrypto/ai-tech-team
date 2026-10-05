import shlex
import subprocess

from langchain_core.tools import tool

from ...guardrails.tool_permissions import check_command, resolve_path
from ...settings import settings
from ..base import ToolContext, guarded


def make(ctx: ToolContext):
    g = guarded(ctx)

    @tool
    @g
    def gh(args: str, cwd: str = ".") -> str:
        """Run the GitHub CLI: `gh <args>` in `cwd` (a repo folder, so `gh` infers the repo; or pass -R owner/repo).
        Examples: "pr view 12 --json title,body,files", "pr diff 12", "pr checks 12",
        "pr review 12 --comment --body-file /tmp/r.md", "issue list --state open --json number,title,labels",
        "issue create --title T --body B --label bug", "project item-list 3 --owner @me"."""
        check_command("gh " + args)
        r = subprocess.run(["gh", *shlex.split(args)], cwd=resolve_path(cwd, ctx.cwd), capture_output=True,
                           text=True, timeout=settings.cfg("agents.command_timeout_seconds", 600))
        return f"exit={r.returncode}\n{(r.stdout + (chr(10) + '[stderr]' + chr(10) + r.stderr if r.stderr else ''))[-15000:]}"

    return [gh]
