import html
import re
import urllib.parse

import httpx
from langchain_core.tools import tool

from ...settings import settings
from ..base import ToolContext, guarded

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) ai-team/2"}


def web_search(query: str, n: int = 8) -> str:
    if settings.web_search_url:  # SearXNG JSON API
        r = httpx.get(settings.web_search_url.rstrip("/") + "/search",
                      params={"q": query, "format": "json"}, timeout=20, headers=UA)
        r.raise_for_status()
        return "\n\n".join(f"{x.get('title')}\n{x.get('url')}\n{x.get('content', '')}"
                           for x in r.json().get("results", [])[:n]) or "no results"
    r = httpx.post("https://html.duckduckgo.com/html/", data={"q": query}, timeout=20, headers=UA,
                   follow_redirects=True)
    r.raise_for_status()
    out = []
    for m in re.finditer(r'class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</',
                         r.text, re.S):
        url = m.group(1)
        if "uddg=" in url:
            url = urllib.parse.unquote(url.split("uddg=")[1].split("&")[0])
        strip = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
        out.append(f"{strip(m.group(2))}\n{url}\n{strip(m.group(3))}")
        if len(out) >= n:
            break
    return "\n\n".join(out) or "no results"


def make(ctx: ToolContext):
    g = guarded(ctx)

    @tool("web_search")
    @g
    def web_search_tool(query: str) -> str:
        """Search the web. Returns titles, URLs and snippets."""
        return web_search(query)

    return [web_search_tool]
