import sqlite3

from langchain_core.tools import tool

from ...guardrails.tool_permissions import resolve_path
from ..base import ToolContext, guarded


def make(ctx: ToolContext):
    g = guarded(ctx)

    @tool
    @g
    def sql_schema(database: str) -> str:
        """Show the tables and CREATE statements of a SQLite database file in the workspace."""
        con = sqlite3.connect(resolve_path(database, ctx.cwd))
        try:
            rows = con.execute("SELECT name, sql FROM sqlite_master WHERE type IN ('table','view')").fetchall()
            return "\n\n".join(f"-- {n}\n{s}" for n, s in rows) or "(no tables)"
        finally:
            con.close()

    return [sql_schema]
