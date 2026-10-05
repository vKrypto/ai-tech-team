"""The skills library (synced from the host's Claude skills by deploy.sh) as tools for chat-model providers."""
import re
import time

from langchain_core.tools import tool

from ..settings import settings
from .base import ToolContext, guarded


_cache: tuple[float, list] = (0.0, [])


def index() -> list[tuple[str, str]]:
    """(name, description) of every skill; re-read at most every 5 minutes so newly synced skills appear."""
    global _cache
    if time.time() - _cache[0] < 300:
        return _cache[1]
    out = []
    root = settings.skills_dir
    if root.is_dir():
        for f in sorted(root.glob("*/SKILL.md")):
            head = f.read_text(errors="ignore")[:3000]
            m = re.search(r"^description:\s*(.+)$", head, re.M)
            out.append((f.parent.name, (m.group(1).strip().strip('"') if m else "")[:300]))
    _cache = (time.time(), out)
    return out


def make(ctx: ToolContext):
    g = guarded(ctx)

    @tool
    @g
    def list_skills() -> str:
        """List available skills (packaged know-how for pdf, docx, xlsx, pptx, mcp servers, ...)."""
        return "\n".join(f"- {n}: {d}" for n, d in index()) or "(no skills installed)"

    @tool
    @g
    def load_skill(name: str, file: str = "SKILL.md") -> str:
        """Read a skill's instructions (or another file inside the skill folder)."""
        base = (settings.skills_dir / name).resolve()
        p = (base / file).resolve()
        if settings.skills_dir.resolve() not in p.parents:
            return "ERROR: not inside the skills library"
        return p.read_text(errors="replace")

    return [list_skills, load_skill]
