"""Headless Chromium through Playwright. Each call opens a fresh browser (tool calls may run on different
threads, which Playwright's sync API does not allow to share)."""
import json

from langchain_core.tools import tool

from ...guardrails.tool_permissions import resolve_path
from ..base import ToolContext, guarded
from ..web.fetch import to_text


def make(ctx: ToolContext):
    g = guarded(ctx)

    @tool
    @g
    def browser(url: str, actions: list[dict] | None = None, screenshot: str = "",
                wait_for: str = "") -> str:
        """Open `url` in a headless browser, run `actions` in order, and return the page title, URL and text.
        actions items: {"click": "<selector>"}, {"fill": ["<selector>", "<text>"]}, {"press": "Enter"},
        {"wait": 1000}, {"goto": "<url>"}, {"eval": "<js expression>"}.
        `screenshot`: optional path (relative to the project) to save a full-page PNG.
        `wait_for`: optional selector to wait for before reading."""
        from playwright.sync_api import sync_playwright
        notes = []
        with sync_playwright() as p:
            b = p.chromium.launch(args=["--no-sandbox"])
            try:
                page = b.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                for a in actions or []:
                    if "click" in a:
                        page.click(a["click"], timeout=15_000)
                    elif "fill" in a:
                        page.fill(a["fill"][0], a["fill"][1], timeout=15_000)
                    elif "press" in a:
                        page.keyboard.press(a["press"])
                    elif "wait" in a:
                        page.wait_for_timeout(int(a["wait"]))
                    elif "goto" in a:
                        page.goto(a["goto"], wait_until="domcontentloaded", timeout=45_000)
                    elif "eval" in a:
                        notes.append("eval -> " + json.dumps(page.evaluate(a["eval"]), default=str)[:2000])
                if wait_for:
                    page.wait_for_selector(wait_for, timeout=20_000)
                if screenshot:
                    path = resolve_path(screenshot, ctx.cwd)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(path), full_page=True)
                    ctx.changed.add(ctx.rel(path))
                    notes.append(f"screenshot saved to {ctx.rel(path)}")
                text = to_text(page.content())
                return "\n".join([f"URL: {page.url}", f"Title: {page.title()}", *notes, "", text])
            finally:
                b.close()

    return [browser]
