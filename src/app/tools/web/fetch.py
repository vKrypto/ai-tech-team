import html
import re

import httpx
from langchain_core.tools import tool

from ..base import ToolContext, guarded
from .search import UA


def to_text(body: str) -> str:
    body = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", body)
    body = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr)>", "\n", body)
    body = html.unescape(re.sub(r"<[^>]+>", " ", body))
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t]+", " ", body)).strip()


def make(ctx: ToolContext):
    g = guarded(ctx)

    @tool
    @g
    def http_fetch(url: str, method: str = "GET", body: str = "", headers: dict | None = None,
                   raw: bool = False) -> str:
        """HTTP request (like curl). HTML is converted to text unless raw=True."""
        r = httpx.request(method, url, content=body or None, headers={**UA, **(headers or {})},
                          timeout=30, follow_redirects=True)
        text = r.text
        if not raw and "html" in r.headers.get("content-type", ""):
            text = to_text(text)
        return f"HTTP {r.status_code} {r.headers.get('content-type', '')}\n\n{text}"

    return [http_fetch]
