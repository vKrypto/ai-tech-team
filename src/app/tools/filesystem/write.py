from langchain_core.tools import tool

from ...guardrails.tool_permissions import resolve_path
from ..base import ToolContext, guarded


def make(ctx: ToolContext):
    g = guarded(ctx)

    @tool
    @g
    def write_file(path: str, content: str) -> str:
        """Create or overwrite a file (path relative to the project folder)."""
        p = resolve_path(path, ctx.cwd)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        ctx.changed.add(ctx.rel(p))
        return f"wrote {ctx.rel(p)} ({len(content)} chars)"

    @tool
    @g
    def edit_file(path: str, old: str, new: str) -> str:
        """Replace the single exact occurrence of `old` with `new` in a file."""
        p = resolve_path(path, ctx.cwd)
        text = p.read_text()
        n = text.count(old)
        if n != 1:
            return f"ERROR: `old` found {n} times; it must match exactly once"
        p.write_text(text.replace(old, new, 1))
        ctx.changed.add(ctx.rel(p))
        return f"edited {ctx.rel(p)}"

    return [write_file, edit_file]
