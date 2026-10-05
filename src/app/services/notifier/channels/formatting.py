"""Plain-text and HTML renderings shared by channels."""
import html

ICON = {"action": "🙋", "error": "❌", "info": "✅"}


def options_text(n: dict) -> str:
    return "\n".join(f"  [{o.get('id')}] {o.get('label')}" + (f" — {o['details']}" if o.get("details") else "")
                     for o in n.get("options") or [])


def text(n: dict, with_title: bool = True) -> str:
    parts = [f"{ICON.get(n.get('level'), '')} {n['title']}".strip()] if with_title else []
    parts.append(n.get("message") or "")
    if n.get("options"):
        parts.append("Options:\n" + options_text(n))
    if n.get("link"):
        parts.append(n["link"])
    return "\n\n".join(p for p in parts if p)


def html_text(n: dict) -> str:
    e = html.escape
    out = f"<b>{e(ICON.get(n.get('level'), ''))} {e(n['title'])}</b>\n\n{e(n.get('message') or '')}"
    if n.get("options"):
        out += "\n\n<b>Options</b>\n" + e(options_text(n))
    if n.get("link"):
        out += f"\n\n<a href=\"{e(n['link'])}\">Open in dashboard</a>"
    return out
