"""Claude Code CLI in headless mode (`claude -p`), on a Claude subscription.

Full-access mode: every built-in tool, permissions bypassed (the container is the sandbox), plus the
Playwright MCP browser. Reading the mounted token is denied. Sessions live in a CLAUDE_CONFIG_DIR shared by
all agent replicas, so `--resume` works whichever replica picks up the next job. The skills library is
installed in that config dir by deploy.sh, so Claude loads skills natively.
"""
import json
import os
import subprocess
import uuid
from pathlib import Path

from pydantic import BaseModel

from ...settings import settings
from .base import AgentRequest, AgentResponse, Cancelled, Provider, ProviderError

DENY = ["Read(//run/secrets/**)", "Bash(cat /run/secrets/*)"]
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def _token() -> str:
    tok = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    if not tok and settings.claude_token_file.is_file():
        tok = settings.claude_token_file.read_text().strip()
    if not tok:
        raise ProviderError(f"no Claude token: run ./deploy.sh (expected {settings.claude_token_file})")
    return tok


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("AI_TEAM_")}
    env.update(CLAUDE_CODE_OAUTH_TOKEN=_token(), DISABLE_AUTOUPDATER="1",
               CLAUDE_CONFIG_DIR=str(settings.claude_config_dir))
    return env


def _mcp_config() -> list[str]:
    if not (settings.browser_enabled and settings.playwright_mcp):
        return ["--strict-mcp-config"]
    cfg = {"mcpServers": {"playwright": {"command": settings.playwright_mcp,
                                         "args": ["--headless", "--isolated", "--no-sandbox", "--browser", "chromium"]}}}
    return ["--mcp-config", json.dumps(cfg), "--strict-mcp-config"]


def _summarize(name: str, inp: dict) -> str:
    key = inp.get("file_path") or inp.get("pattern") or inp.get("command") or inp.get("url") or inp.get("path") or ""
    return f"{name}({str(key)[:160]!r})"


def _rel(path: str) -> str | None:
    try:
        return str(Path(path).resolve().relative_to(settings.workspace_root))
    except ValueError:
        return None


class ClaudeCodeProvider(Provider):
    type = "claude_code"

    def _base(self, model: str) -> list[str]:
        return [settings.claude_bin, "-p", "--model", model]

    def run_agent(self, req: AgentRequest) -> AgentResponse:
        model = self.model_for(req.tier)
        session_args = ["--resume", req.session] if req.session else ["--session-id", str(uuid.uuid4())]
        if req.session:
            req.log("status", f"resuming claude session {req.session[:8]}")
        cmd = self._base(model) + session_args + [
            "--output-format", "stream-json", "--verbose",
            "--permission-mode", "bypassPermissions",
            "--disallowedTools", *DENY,
            "--append-system-prompt", req.system_prompt,
            "--add-dir", str(settings.workspace_root), "--add-dir", str(settings.skills_dir),
            *_mcp_config(),
        ]
        proc = subprocess.Popen(cmd, cwd=req.cwd, env=_env(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        proc.stdin.write(req.brief)   # via stdin: no argv length limit
        proc.stdin.close()
        final, result = "", None
        try:
            for line in proc.stdout:
                if req.cancelled():
                    proc.kill()
                    raise Cancelled()
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") == "assistant":
                    for block in ev.get("message", {}).get("content", []):
                        if block.get("type") == "text" and block.get("text", "").strip():
                            final = block["text"]
                            req.log("message", final)
                        elif block.get("type") == "tool_use":
                            inp = block.get("input") or {}
                            req.log("tool", _summarize(block.get("name", "?"), inp))
                            if block.get("name") in EDIT_TOOLS and inp.get("file_path"):
                                if (r := _rel(inp["file_path"])) is not None:
                                    req.changed.add(r)
                elif ev.get("type") == "user":   # tool results come back as user turns
                    for block in (ev.get("message") or {}).get("content", []) or []:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            c = block.get("content")
                            text = c if isinstance(c, str) else " ".join(
                                x.get("text", "") for x in c or [] if isinstance(x, dict))
                            first = (text or "").strip().splitlines()[0][:160] if (text or "").strip() else "(empty)"
                            req.log("tool_result", ("error: " if block.get("is_error") else "") +
                                    f"{len(text or '')} chars: {first}")
                elif ev.get("type") == "result":
                    result = ev
            proc.wait(timeout=60)
        finally:
            if proc.poll() is None:
                proc.kill()
        if result is None:
            raise ProviderError(f"claude exited {proc.returncode} without a result: {proc.stderr.read()[-2000:]}")
        if result.get("is_error"):
            raise ProviderError(f"claude {result.get('subtype', 'error')}: {str(result.get('result', ''))[:1000]}")
        cost = result.get("total_cost_usd")
        req.log("status", f"claude/{model}: {result.get('num_turns', '?')} turns"
                          + (f", ~${cost:.3f} API-equivalent (subscription)" if cost is not None else ""))
        return AgentResponse(result.get("result") or final, result.get("session_id") or session_args[1], model, None)

    def structured(self, prompt: str, schema: type[BaseModel], tier: str = "fast") -> dict:
        cmd = self._base(self.model_for(tier)) + [
            "--no-session-persistence", "--output-format", "json", "--tools", "", "--strict-mcp-config",
            "--json-schema", json.dumps(schema.model_json_schema())]
        r = subprocess.run(cmd, input=prompt, cwd=settings.workspace_root, env=_env(), capture_output=True,
                           text=True, timeout=300)
        try:
            out = json.loads(r.stdout)
        except json.JSONDecodeError:
            raise ProviderError(f"claude exited {r.returncode}: {(r.stderr or r.stdout)[-2000:]}")
        if out.get("is_error"):
            raise ProviderError(f"claude {out.get('subtype', 'error')}: {str(out.get('result', ''))[:1000]}")
        data = out.get("structured_output")
        if data is None:
            text = out.get("result", "")
            data = json.loads(text[text.find("{"):text.rfind("}") + 1])
        return data
