# One image for every component (scheduler, orchestrator, engine, agent, notifier); the stack picks the
# command. Agents work in full-access mode, so the image carries their toolbox: git, gh, curl, node, a headless
# Chromium (Playwright, for the Python tool and the Playwright MCP server), Claude Code and Codex CLIs.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates git jq ripgrep procps nodejs npm sqlite3 build-essential \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
         -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
         > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*'
WORKDIR /app

# Python deps first (cached unless pyproject changes)
COPY pyproject.toml .
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" \
      > /tmp/requirements.txt && pip install -r /tmp/requirements.txt \
    && pip install pytest uv   # for the agents: run Python test suites, set up per-project environments

# Browsers: Python Playwright's Chromium (+ system deps), and the Playwright MCP server with its own
# Playwright's Chromium (versions can differ), both under /ms-playwright.
ARG PLAYWRIGHT_MCP_VERSION=latest
RUN playwright install --with-deps chromium \
    && npm install -g "@playwright/mcp@${PLAYWRIGHT_MCP_VERSION}" \
    && cd "$(npm root -g)/@playwright/mcp" && npx --no-install playwright install chromium \
    && chmod -R a+rX /ms-playwright && npm cache clean --force

# Same UID/GID as the workstation user, so files agents write in /workspace stay yours.
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} agent && useradd -u ${UID} -g ${GID} -m agent && mkdir -p /data && chown agent:agent /data
USER agent

# Claude Code CLI (provider type claude_code) and Codex CLI (provider type codex): copied from vendor/cli/,
# which scripts/fetch_clis.sh fills once (deploy.sh runs it), so builds never download them.
RUN mkdir -p /home/agent/.local/bin
COPY --chown=agent:agent vendor/cli/claude vendor/cli/codex /home/agent/.local/bin/
ENV PATH=/home/agent/.local/bin:$PATH DISABLE_AUTOUPDATER=1

COPY --chown=agent:agent configs configs
COPY --chown=agent:agent src src
ENV PYTHONPATH=/app/src AI_TEAM_DATA_DIR=/data AI_TEAM_WORKSPACE_ROOT=/workspace \
    AI_TEAM_HIDDEN_DIRS='["/workspace/ai-team"]'
EXPOSE 8765
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --start-interval=2s CMD python -m app health
CMD ["python", "-m", "app", "agent"]
