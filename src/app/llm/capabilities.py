"""What each provider type brings (shown on the dashboard, used for routing decisions)."""
CAPABILITIES = {
    "claude_code": {"agent_loop": "native", "browser": "playwright-mcp", "skills": "native",
                    "sessions": "resume", "billing": "subscription"},
    "codex": {"agent_loop": "native", "browser": "playwright-mcp", "skills": "files",
              "sessions": "resume", "billing": "subscription"},
    "openai": {"agent_loop": "langchain", "browser": "playwright-tool", "skills": "tool",
               "sessions": "checkpointer", "billing": "tokens/gateway"},
    "anthropic": {"agent_loop": "langchain", "browser": "playwright-tool", "skills": "tool",
                  "sessions": "checkpointer", "billing": "tokens"},
    "google": {"agent_loop": "langchain", "browser": "playwright-tool", "skills": "tool",
               "sessions": "checkpointer", "billing": "tokens"},
    "ollama": {"agent_loop": "langchain", "browser": "playwright-tool", "skills": "tool",
               "sessions": "checkpointer", "billing": "local"},
    "bedrock": {"agent_loop": "langchain", "browser": "playwright-tool", "skills": "tool",
                "sessions": "checkpointer", "billing": "tokens"},
    "mock": {"agent_loop": "fake", "browser": "-", "skills": "-", "sessions": "-", "billing": "free"},
}


def for_type(kind: str) -> dict:
    return CAPABILITIES.get(kind, {})
