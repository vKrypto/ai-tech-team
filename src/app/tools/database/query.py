import sqlite3

from langchain_core.tools import tool

from ...guardrails.tool_permissions import resolve_path
from ..base import ToolContext, guarded


def make(ctx: ToolContext):
    g = guarded(ctx)

    @tool
    @g
    def sql_query(database: str, sql: str, max_rows: int = 200) -> str:
        """Run SQL against a SQLite database file in the workspace. Returns rows as tab-separated text.
        (For other databases use their CLI through run_command.)"""
        con = sqlite3.connect(resolve_path(database, ctx.cwd))
        try:
            cur = con.execute(sql)
            if cur.description is None:
                con.commit()
                return f"ok, {cur.rowcount} row(s) affected"
            cols = [c[0] for c in cur.description]
            rows = cur.fetchmany(max_rows)
            return "\n".join(["\t".join(cols)] + ["\t".join(map(str, r)) for r in rows])
        finally:
            con.close()

    return [sql_query]
