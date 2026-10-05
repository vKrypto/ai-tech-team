import pytest

from app.guardrails.output import redact
from app.guardrails.tool_permissions import PermissionDenied, check_command, resolve_path
from app.settings import settings


def test_paths_stay_in_workspace():
    with pytest.raises(PermissionDenied):
        resolve_path("../../etc/passwd")
    with pytest.raises(PermissionDenied):
        resolve_path(str(settings.hidden_dirs[0] / "x"))
    assert resolve_path(".") == settings.workspace_root


def test_destructive_commands_refused_normal_allowed():
    for bad in ("rm -rf /", "sudo ls", "cat /run/secrets/claude_oauth_token", "mkfs.ext4 /dev/sda"):
        with pytest.raises(PermissionDenied):
            check_command(bad)
    check_command("git status && pytest -q && curl -s https://example.com")


def test_redact():
    s = redact("token sk-ant-oat01-abcdefghijklmnopqrstuvwxyz and Bearer abcdefghijklmnopqrstuvwxyz123")
    assert "sk-ant" not in s and "abcdefghijklmnopqrstuvwxyz123" not in s and "Bearer [REDACTED]" in s
