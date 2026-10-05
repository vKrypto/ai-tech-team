"""OpenAI Codex CLI headless (`codex exec --json`), on a ChatGPT plan.

Codex's own sandbox needs bubblewrap, which Docker's AppArmor blocks, so it runs with its sandbox bypassed
(full access) and the container is the sandbox. Login state lives in /data/codex (deploy.sh does the device
login); it is shared by agent replicas, so `codex exec resume` works on any of them.
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel

from ...settings import settings
from .base import AgentRequest, AgentResponse, Cancelled, Provider, ProviderError

EFFORT = {"fast": "low", "balanced": "medium", "deep": "high"}


def _strict(schema: dict) -> dict:
    """OpenAI structured output wants every object closed and every property required."""
    if schema.get("type") == "object":
        schema["additionalProperties"] = False
        schema["required"] = list(schema.get("properties", {}))
    for v in list(schema.get("properties", {}).values()) + list(schema.get("$defs", {}).values()):
        _strict(v)
    if isinstance(schema.get("items"), dict):
        _strict(schema["items"])
    return schema


class CodexProvider(Provider):
    type = "codex"

    def _env(self) -> dict:
        if not (settings.codex_home / "auth.json").is_file():
            raise ProviderError("Codex is not logged in: run ./deploy.sh (it runs `codex login --device-auth`)")
        env = {k: v for k, v in os.environ.items() if not k.startswith("AI_TEAM_")}
        env["CODEX_HOME"] = str(settings.codex_home)
        return env

    def _cmd(self, tier: str, cwd: Path, session: str | None = None, ephemeral: bool = False) -> list[str]:
        cmd = [settings.codex_bin, "exec"] + (["resume", session] if session else ["-C", str(cwd)])
        cmd += ["--json", "--skip-git-repo-check", "--dangerously-bypass-approvals-and-sandbox",
                "-c", f'model_reasoning_effort="{EFFORT.get(tier, "medium")}"']
        if settings.browser_enabled and settings.playwright_mcp and not ephemeral:
            cmd += ["-c", f'mcp_servers.playwright.command="{settings.playwright_mcp}"',
                    "-c", 'mcp_servers.playwright.args=["--headless","--isolated","--no-sandbox","--browser","chromium"]']
        if ephemeral:
            cmd.append("--ephemeral")
        if model := self.model_for(tier):
            cmd += ["-m", model]
        return cmd

    def _stream(self, cmd, prompt, cwd, log, cancelled, changed: set | None = None):
        with tempfile.NamedTemporaryFile("r", suffix=".txt") as last:
            proc = subprocess.Popen(cmd + ["-o", last.name, "-"], cwd=cwd, env=self._env(), stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            proc.stdin.write(prompt)
            proc.stdin.close()
            error, usage, thread = None, None, None
            try:
                for line in proc.stdout:
                    if cancelled():
                        proc.kill()
                        raise Cancelled()
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    kind = ev.get("type", "")
                    if kind == "thread.started":
                        thread = ev.get("thread_id")
                    elif kind == "item.completed":
                        item = ev.get("item") or {}
                        t = item.get("type")
                        if t == "agent_message" and item.get("text"):
                            log("message", item["text"])
                        elif t == "command_execution":
                            log("tool", f"shell({item.get('command', '')[:160]!r}) -> exit {item.get('exit_code')}")
                        elif t == "file_change":
                            for c in item.get("changes", []):
                                log("tool", f"edit({c.get('kind')} {c.get('path')})")
                                if changed is not None:
                                    try:
                                        changed.add(str((cwd / c.get("path", "")).resolve()
                                                        .relative_to(settings.workspace_root)))
                                    except ValueError:
                                        pass
                        elif t in ("mcp_tool_call", "web_search"):
                            log("tool", f"{t}({str(item)[:160]})")
                    elif kind == "turn.completed":
                        usage = ev.get("usage")
                    elif kind in ("turn.failed", "error"):
                        error = (ev.get("error") or {}).get("message") or ev.get("message") or str(ev)
                proc.wait(timeout=60)
            finally:
                if proc.poll() is None:
                    proc.kill()
            final = Path(last.name).read_text().strip()
        if error or (proc.returncode and not final):
            raise ProviderError(f"codex failed (exit {proc.returncode}): {error or proc.stderr.read()[-2000:]}")
        if usage:
            log("status", f"codex: tokens in {usage.get('input_tokens', '?')}, out {usage.get('output_tokens', '?')}")
        return final, thread

    def run_agent(self, req: AgentRequest) -> AgentResponse:
        prompt = req.brief if req.session else f"{req.system_prompt}\n\n---\n\n{req.brief}"
        if req.session:
            req.log("status", f"resuming codex session {req.session[:8]}")
        out, thread = self._stream(self._cmd(req.tier, req.cwd, req.session), prompt, req.cwd, req.log,
                                   req.cancelled, req.changed)
        return AgentResponse(out, thread or req.session, self.model_for(req.tier) or "codex-default")

    def structured(self, prompt: str, schema: type[BaseModel], tier: str = "fast") -> dict:
        with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
            json.dump(_strict(schema.model_json_schema()), f)
            f.flush()
            cmd = self._cmd(tier, settings.workspace_root, ephemeral=True) + ["--output-schema", f.name]
            text, _ = self._stream(cmd, "Answer with JSON only. Do not run any commands.\n\n" + prompt,
                                   settings.workspace_root, lambda *_: None, lambda: False)
        return json.loads(text[text.find("{"):text.rfind("}") + 1])
