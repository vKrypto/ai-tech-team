#!/usr/bin/env bash
# Build and (re)deploy the ai_team swarm stack (stack.yml) to a Docker engine, e.g. the Proxmox docker-vm.
#   ./deploy.sh                    deploy with .env.prod
#   ./deploy.sh --env FILE         deploy with another env file (target, providers, channels…)
#   ./deploy.sh --relogin          log the CLI providers and GitHub in again
#   ./deploy.sh --codex-auth-file F  push a Codex login (auth.json from a separate `codex login`) to the target
#   ./deploy.sh --smoke            after deploying, run one small real task end to end
#
# Target (in the env file):
#   AI_TEAM_DEPLOY_CONTEXT   docker context of the swarm manager (default: current context).
#                            One-time: docker context create docker-vm --docker host=ssh://docker-vm
#   AI_TEAM_DEPLOY_HOST      host name/IP to verify the dashboard on (default: from the context)
#   AI_TEAM_DATA_ROOT        data dir ON THE TARGET (redis AOF, mongo, logins, skills)
#   AI_TEAM_WORKSPACE_ROOT   repos dir ON THE TARGET, mounted at /workspace for the agents
#   AI_TEAM_REGISTRY         optional registry (e.g. 192.168.100.10:10400): build here, push, target pulls.
#                            Empty: the image is built by the target engine itself (single-node swarm).
#
# Provider/GitHub credentials are checked with one tiny real call on the target before deploying. Every
# deploy is verified (rollout, health, components alive, durability, isolation); the script exits non-zero
# with diagnostics if a check fails. DEPLOY_TIMEOUT (default 300s) bounds the wait.
set -euo pipefail
cd "$(dirname "$0")"

STACK=ai_team
SECRET_PREFIX=ai_team_claude_token_
ENV_FILE=.env.prod
RELOGIN=false
SMOKE=false
CODEX_AUTH_FILE="${CODEX_AUTH_FILE:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --env) ENV_FILE="$2"; shift ;;
    --relogin) RELOGIN=true ;;
    --smoke) SMOKE=true ;;
    --codex-auth-file) CODEX_AUTH_FILE="$2"; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
[ -f "$ENV_FILE" ] || { echo "$ENV_FILE not found: copy .env.example to $ENV_FILE and fill in the Deploy section" >&2; exit 2; }
export AI_TEAM_ENV_FILE="$ENV_FILE"
env_get() { sed -n "s/^$1=//p" "$ENV_FILE" | tail -1; }

CTX="$(env_get AI_TEAM_DEPLOY_CONTEXT)"; CTX="${CTX:-$(docker context show)}"
dk() { docker --context "$CTX" "$@"; }
dk info >/dev/null 2>&1 || { echo "docker context '$CTX' is not reachable (docker context ls)" >&2; exit 1; }
endpoint="$(docker context inspect "$CTX" --format '{{.Endpoints.docker.Host}}')"
DEPLOY_HOST="$(env_get AI_TEAM_DEPLOY_HOST)"
if [ -z "$DEPLOY_HOST" ]; then
  case "$endpoint" in
    ssh://*) DEPLOY_HOST="${endpoint#ssh://}"; DEPLOY_HOST="${DEPLOY_HOST#*@}"; DEPLOY_HOST="${DEPLOY_HOST%%:*}" ;;
    tcp://*) DEPLOY_HOST="${endpoint#tcp://}"; DEPLOY_HOST="${DEPLOY_HOST%%:*}" ;;
    *) DEPLOY_HOST=localhost ;;
  esac
fi
LOCAL=false; [[ "$endpoint" == unix://* ]] && LOCAL=true

export DATA_HOST_DIR="$(env_get AI_TEAM_DATA_ROOT)"
export WORKSPACE_HOST_DIR="$(env_get AI_TEAM_WORKSPACE_ROOT)"
if $LOCAL; then   # deploying to this machine: relative paths are fine
  DATA_HOST_DIR="$(realpath -m "${DATA_HOST_DIR:-data}")"
  WORKSPACE_HOST_DIR="$(realpath -m "${WORKSPACE_HOST_DIR:-..}")"
fi
[[ "$DATA_HOST_DIR" == /* && "$WORKSPACE_HOST_DIR" == /* ]] \
  || { echo "set AI_TEAM_DATA_ROOT and AI_TEAM_WORKSPACE_ROOT to absolute paths on the target in $ENV_FILE" >&2; exit 2; }
export AI_TEAM_PORT="$(env_get AI_TEAM_PORT)"; AI_TEAM_PORT="${AI_TEAM_PORT:-8765}"
export AI_TEAM_AGENTS="$(env_get AI_TEAM_AGENTS)"; AI_TEAM_AGENTS="${AI_TEAM_AGENTS:-3}"
export AI_TEAM_ENGINES="$(env_get AI_TEAM_ENGINES)"; AI_TEAM_ENGINES="${AI_TEAM_ENGINES:-3}"
REGISTRY="$(env_get AI_TEAM_REGISTRY)"
PROVIDERS="$(env_get AI_TEAM_PROVIDERS | tr -d '[]" ' )"; PROVIDERS="${PROVIDERS:-mock}"
has_provider() { [[ ",$PROVIDERS," == *",$1,"* ]]; }
GITHUB="$(env_get AI_TEAM_GITHUB_ENABLED)"; [ "$GITHUB" = true ] || GITHUB=false
BASE_URL="http://$DEPLOY_HOST:$AI_TEAM_PORT"
UI_USER="$(env_get AI_TEAM_UI_USERNAME)"; UI_USER="${UI_USER:-admin}"
UI_PASS="$(env_get AI_TEAM_UI_PASSWORD)"; UI_PASS="${UI_PASS:-admin@123}"
acurl() { curl -u "$UI_USER:$UI_PASS" "$@"; }   # the API needs a login (Basic auth for scripts)
UIDGID="$(id -u):$(id -g)"
# Local, per-target state (never in git): the Claude token. Everything else lives on the target.
STATE_DIR="data/deploy/$CTX"
mkdir -p "$STATE_DIR/claude" && chmod 700 "$STATE_DIR" "$STATE_DIR/claude"
echo "target: context '$CTX' ($endpoint) · data $DATA_HOST_DIR · workspace $WORKSPACE_HOST_DIR · $BASE_URL"

if [ "$(dk info --format '{{.Swarm.LocalNodeState}}')" != "active" ]; then
  if $LOCAL; then
    echo "initialising single-node swarm"
    dk swarm init --advertise-addr 127.0.0.1 --listen-addr 127.0.0.1:2377 >/dev/null
  else
    echo "the target is not a swarm manager (run 'docker swarm init' there first)" >&2; exit 1
  fi
fi

# --- Image ---------------------------------------------------------------------------------------
echo "agent CLIs…"
scripts/fetch_clis.sh   # vendor/cli/: downloaded once, reused by every build
TS="$(date +%Y%m%d-%H%M%S)"   # unique tag so `stack deploy` actually rolls the services
BUILD_ARGS=(--build-arg UID="$(id -u)" --build-arg GID="$(id -g)")
if [ -n "$REGISTRY" ]; then
  TAG="$REGISTRY/ai-team:$TS"
  echo "building image locally, pushing to $REGISTRY…"
  docker build -q "${BUILD_ARGS[@]}" -t "$TAG" -t "$REGISTRY/ai-team:latest" . >/dev/null
  docker push -q "$TAG" >/dev/null && docker push -q "$REGISTRY/ai-team:latest" >/dev/null
  RESOLVE=always
else
  TAG="ai-team:$TS"
  echo "building image on the target engine…"
  dk build -q "${BUILD_ARGS[@]}" -t "$TAG" -t ai-team:latest . >/dev/null
  RESOLVE=never
fi
export AI_TEAM_IMAGE="$TAG"

# --- Target directories, skills -----------------------------------------------------------------
# Created through a throwaway container, so it works the same over an ssh context.
dk run --rm --user 0 -v "$DATA_HOST_DIR:/d" -v "$WORKSPACE_HOST_DIR:/w" "$TAG" sh -c "
  mkdir -p /d/redis /d/mongo /d/claude-home /d/codex /d/github /d/skills &&
  chown $UIDGID /d/claude-home /d/codex /d/github /d/skills /w && chmod 700 /d/codex /d/github &&
  ln -sfn ../skills /d/claude-home/skills && ln -sfn ../skills /d/codex/skills"

# Your Claude skills (synced + plugin skills) → <data>/skills: Claude Code loads them natively, Codex from
# CODEX_HOME/skills, chat-model providers via the list_skills/load_skill tools. Re-synced on every deploy.
skills_tmp="$(mktemp -d)"; trap 'rm -rf "$skills_tmp"' EXIT
nskills="$(scripts/sync_skills.sh "$skills_tmp")"
tar -C "$skills_tmp" -cf - . | dk run --rm -i -v "$DATA_HOST_DIR/skills:/s" "$TAG" \
  sh -c 'find /s -mindepth 1 -delete && tar -xf - -C /s'
echo "  ✓ synced $nskills skills to the target"

# --- Credentials: validate, re-login if invalid ----------------------------------------------------
# Never in env files, git or the image. Checked with one tiny real call from a throwaway container.
need_tty() { [ -t 0 ] || { echo "$1 needs an interactive terminal." >&2; exit 1; }; }
SMOKE_PROMPT="Reply with exactly: OK"

CLAUDE_TOKEN_FILE="${CLAUDE_TOKEN_FILE:-$STATE_DIR/claude/oauth_token}"
[ -s "$CLAUDE_TOKEN_FILE" ] || [ ! -s data/claude/oauth_token ] || cp -p data/claude/oauth_token "$CLAUDE_TOKEN_FILE"
find_claude() {
  command -v claude 2>/dev/null && return
  ls -1d "$HOME"/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude 2>/dev/null | sort -V | tail -1
}
claude_check() {
  [ -s "$CLAUDE_TOKEN_FILE" ] || { echo "no token stored"; return 1; }
  local out
  out="$(CLAUDE_CODE_OAUTH_TOKEN="$(cat "$CLAUDE_TOKEN_FILE")" dk run --rm -e CLAUDE_CODE_OAUTH_TOKEN "$TAG" \
        claude -p "$SMOKE_PROMPT" --model haiku --tools "" --no-session-persistence 2>&1 | tail -1)"
  echo "$out"; [[ "$out" == *OK* ]]
}
claude_login() {
  local token="${CLAUDE_CODE_OAUTH_TOKEN:-}" claude
  if [ -z "$token" ]; then
    need_tty "Claude login"
    claude="$(find_claude)"
    echo "== Claude login: approve in the browser, then copy the token it prints. =="
    if [ -n "$claude" ]; then "$claude" setup-token; else docker run --rm -it "$TAG" claude setup-token; fi
    read -rsp "Paste the token (input hidden): " token; echo
  fi
  token="$(printf '%s' "$token" | tr -d '[:space:]')"
  [[ "$token" == sk-ant-* ]] || { echo "that doesn't look like a Claude token (expected sk-ant-…)" >&2; exit 1; }
  ( umask 077; printf '%s' "$token" > "$CLAUDE_TOKEN_FILE" )
  echo "saved token to $CLAUDE_TOKEN_FILE"
}
# Codex: ChatGPT login = <data>/codex/auth.json on the target, mounted read-write into the agents and the
# orchestrator. Unlike Claude's fixed token it can't be a swarm secret: Codex rewrites auth.json whenever it
# refreshes the session, so the target's copy is the source of truth and deploys never overwrite it unless
# it's invalid, --relogin, or a new file is pushed.
codex_prepare() {   # file-based credential store, private dir
  dk run --rm --user 0 -v "$DATA_HOST_DIR/codex:/c" "$TAG" sh -c "
    touch /c/config.toml && grep -q '^cli_auth_credentials_store' /c/config.toml ||
      printf 'cli_auth_credentials_store = \"file\"\n' >> /c/config.toml
    chown -R $UIDGID /c && chmod 700 /c && chmod 600 /c/config.toml"
}
codex_check() {
  local out
  out="$(dk run --rm -v "$DATA_HOST_DIR/codex:/data/codex" -e CODEX_HOME=/data/codex -w /tmp "$TAG" sh -c \
        "test -s /data/codex/auth.json || { echo 'not logged in'; exit 1; }; codex exec --ephemeral --skip-git-repo-check -c 'model_reasoning_effort=\"low\"' '$SMOKE_PROMPT'" 2>&1 | tail -1)"
  echo "$out"; [[ "$out" == *OK* ]]
}
codex_login() {
  [ -n "$CODEX_AUTH_FILE" ] && { codex_push_file "$CODEX_AUTH_FILE"; return; }
  need_tty "Codex login (or pass --codex-auth-file / CODEX_AUTH_FILE)"
  echo "== Codex login for the server: open the URL shown, sign in with ChatGPT and enter the code. =="
  echo "   (If device login is disabled: ChatGPT → Settings → Security → enable device code auth for Codex.)"
  dk run --rm -it -v "$DATA_HOST_DIR/codex:/data/codex" -e CODEX_HOME=/data/codex "$TAG" \
    codex login --device-auth -c 'cli_auth_credentials_store="file"'
}
codex_push_file() {   # validate locally (never printing it), then copy to <data>/codex/auth.json with mode 600
  local f="$1"
  [ -s "$f" ] || { echo "  ✗ codex auth file '$f' not found or empty" >&2; exit 1; }
  if [ "$(realpath "$f")" = "$(realpath -m "$HOME/.codex/auth.json")" ] && [ "${CODEX_ALLOW_HOST_SESSION:-}" != 1 ]; then
    echo "  ✗ that is this machine's own Codex session: sharing it makes the server and this machine log each other out" >&2
    echo "    (refresh tokens rotate). Make a separate one:  CODEX_HOME=\$(mktemp -d) codex login  and pass that auth.json." >&2
    exit 1
  fi
  python3 - "$f" <<'PY' || { echo "  ✗ '$f' is not a Codex auth.json (expected tokens.refresh_token or OPENAI_API_KEY)" >&2; exit 1; }
import json, sys
d = json.load(open(sys.argv[1]))
assert (d.get("tokens") or {}).get("refresh_token") or d.get("OPENAI_API_KEY")
PY
  dk run --rm -i --user 0 -v "$DATA_HOST_DIR/codex:/c" "$TAG" sh -c \
    "cat > /c/auth.json.new && chmod 600 /c/auth.json.new && chown $UIDGID /c/auth.json.new && mv /c/auth.json.new /c/auth.json" < "$f"
  echo "  ✓ pushed codex login to $DATA_HOST_DIR/codex/auth.json (mode 600)"
}
# GitHub: gh login stored in <data>/github (GH_CONFIG_DIR), shared by agents and the PR watcher.
# Non-interactive: GH_TOKEN=... ./deploy.sh (use a bot account's fine-grained token).
github_check() {
  local out
  out="$(dk run --rm -v "$DATA_HOST_DIR/github:/data/github" -e GH_CONFIG_DIR=/data/github "$TAG" \
        gh api user --jq '"logged in as " + .login' 2>&1 | tail -1)"
  echo "$out"; [[ "$out" == "logged in as "* ]]
}
github_login() {
  if [ -n "${GH_TOKEN:-}" ]; then
    printf '%s' "$GH_TOKEN" | env -u GH_TOKEN docker --context "$CTX" run --rm -i \
      -v "$DATA_HOST_DIR/github:/data/github" -e GH_CONFIG_DIR=/data/github "$TAG" \
      gh auth login -h github.com -p https --with-token
    return
  fi
  need_tty "GitHub login"
  echo "== GitHub login: open https://github.com/login/device and enter the code shown. =="
  dk run --rm -it -v "$DATA_HOST_DIR/github:/data/github" -e GH_CONFIG_DIR=/data/github "$TAG" \
    gh auth login -h github.com -p https -w -s repo,read:org,project,workflow
}
omniroute_check() {
  local url; url="$(env_get AI_TEAM_OMNIROUTE_URL)"; url="${url:-http://192.168.100.10:10200/v1}"
  dk run --rm "$TAG" python -c "import urllib.request,sys; urllib.request.urlopen(sys.argv[1].rstrip('/') + '/models', timeout=10)" \
    "$url" >/dev/null 2>&1 || { echo "gateway $url not reachable from the target"; return 1; }
  echo "gateway $url reachable from the target"
}
ensure_login() {   # ensure_login <name> <check_fn> <login_fn>
  local name="$1" check="$2" login="$3" out
  if ! $RELOGIN; then
    if out="$($check)"; then echo "  ✓ $name: $out"; return; fi
    echo "  ! $name credentials invalid ($out); logging in again"
  fi
  $login
  out="$($check)" || { echo "  ✗ $name still rejected after login: $out" >&2; exit 1; }
  echo "  ✓ $name: $out"
}

echo "checking providers ($PROVIDERS)…"
SECRET=""
if has_provider claude; then
  if [ ! -s "$CLAUDE_TOKEN_FILE" ] && [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then claude_login; fi
  ensure_login Claude claude_check claude_login
  SECRET="$SECRET_PREFIX$(sha256sum "$CLAUDE_TOKEN_FILE" | cut -c1-12)"
  dk secret inspect "$SECRET" >/dev/null 2>&1 || { dk secret create "$SECRET" "$CLAUDE_TOKEN_FILE" >/dev/null; echo "  ✓ created swarm secret $SECRET"; }
fi
if has_provider codex; then
  codex_prepare
  if [ -n "$CODEX_AUTH_FILE" ]; then codex_push_file "$CODEX_AUTH_FILE"; fi   # explicit new login wins
  ensure_login Codex codex_check codex_login
elif [ -n "$CODEX_AUTH_FILE" ]; then
  echo "  ! --codex-auth-file given but codex isn't in AI_TEAM_PROVIDERS; add it to $ENV_FILE to use Codex" >&2
fi
if has_provider omniroute; then out="$(omniroute_check)" || { echo "  ✗ omniroute: $out" >&2; exit 1; }; echo "  ✓ omniroute: $out"; fi
if $GITHUB; then ensure_login GitHub github_check github_login; fi

# Generated each deploy: the Claude token as a swarm secret for the services that call LLMs.
{
  echo 'version: "3.8"'
  if [ -n "$SECRET" ]; then
    echo 'services:'
    for svc in agent orchestrator; do
      echo "  $svc:"
      echo '    secrets:'
      echo "      - {source: $SECRET, target: claude_oauth_token, uid: \"$(id -u)\", gid: \"$(id -g)\", mode: 0400}"
    done
    echo 'secrets:'
    echo "  $SECRET: {external: true}"
  fi
} > stack.generated.yml

echo "deploying stack $STACK ($TAG)…"
# --prune removes services that are no longer in the stack.
dk stack deploy --prune --resolve-image "$RESOLVE" -c stack.yml -c stack.generated.yml "$STACK" >/dev/null

# --- Verify -------------------------------------------------------------------------------------
TIMEOUT="${DEPLOY_TIMEOUT:-300}"
deadline=$((SECONDS + TIMEOUT))
APP_SERVICES="scheduler orchestrator engine agent notifier"
ok() { echo "  ✓ $*"; }
fail() {
  echo "  ✗ $*" >&2
  for s in redis mongo $APP_SERVICES; do
    echo "--- ${STACK}_$s ---" >&2
    dk service ps "${STACK}_$s" --no-trunc --format '{{.Name}} {{.CurrentState}} {{.Error}}' 2>&1 | head -3 >&2
    dk service logs --raw --tail 8 "${STACK}_$s" 2>&1 | tail -8 >&2
  done
  exit 1
}
want_replicas() { case "$1" in agent) echo "$AI_TEAM_AGENTS" ;; engine) echo "$AI_TEAM_ENGINES" ;; *) echo 1 ;; esac; }
running_new() {  # healthy containers of a service on the new image (single-node swarm: all on the manager)
  local svc="${STACK}_$1" n=0 c
  for c in $(dk ps -q --filter "label=com.docker.swarm.service.name=$svc"); do
    case "$1" in redis|mongo) ;; *) [[ "$(dk inspect -f '{{.Config.Image}}' "$c")" == "$TAG"* ]] || continue ;; esac
    [ "$(dk inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}running{{end}}' "$c")" = healthy ] && n=$((n + 1))
  done
  echo "$n"
}
ctr() { dk ps -q --filter "label=com.docker.swarm.service.name=${STACK}_$1" | head -1; }

echo "verifying (timeout ${TIMEOUT}s)…"
for s in redis mongo $APP_SERVICES; do
  want="$(want_replicas "$s")"
  while :; do
    state="$(dk service inspect "${STACK}_$s" --format '{{if .UpdateStatus}}{{.UpdateStatus.State}}{{end}}' 2>/dev/null || true)"
    case "$state" in rollback_*|paused) fail "$s: swarm update $state (new version failed, rolled back)" ;; esac
    [ "$(running_new "$s")" -ge "$want" ] && break
    [ "$SECONDS" -lt "$deadline" ] || fail "$s: $(running_new "$s")/$want healthy on $TAG after ${TIMEOUT}s"
    sleep 3
  done
  ok "$s: $want/$want healthy"
done

[ "$(dk exec "$(ctr redis)" redis-cli config get appendonly | tail -1)" = yes ] || fail "redis AOF is off"
ok "redis durability: AOF on ($DATA_HOST_DIR/redis)"
[ -n "$(dk exec "$(ctr mongo)" sh -c 'ls -A /data/db | head -1')" ] || fail "mongo wrote nothing to $DATA_HOST_DIR/mongo"
ok "mongo durability: files in $DATA_HOST_DIR/mongo"

META=""
while :; do
  META="$(acurl -sf -m 5 "$BASE_URL/api/meta" || true)"
  [ -n "$META" ] && err="$(printf '%s' "$META" | python3 -c '
import json, sys
m, agents, providers, engines = json.load(sys.stdin), int(sys.argv[1]), sys.argv[2].split(","), int(sys.argv[3])
kinds = [s["kind"] for s in m["services"]]
need = {"scheduler": 1, "orchestrator": 1, "engine": engines, "agent": agents, "notifier": 1}
missing = [f"{k} {kinds.count(k)}/{n}" for k, n in need.items() if kinds.count(k) < n]
assert not missing, "components not heartbeating: " + ", ".join(missing)
on = sorted(p["name"] for p in m["providers"] if p["enabled"])
assert on == sorted(providers), f"enabled providers {on}, expected {sorted(providers)}"
assert m["workspace_root"] == "/workspace", "workspace not mounted"
print(len(m["projects"]))' "$AI_TEAM_AGENTS" "$PROVIDERS" "$AI_TEAM_ENGINES" 2>&1)" && break
  [ "$SECONDS" -lt "$deadline" ] || fail "API check: $(printf '%s' "${err:-API not reachable at $BASE_URL}" | tail -1)"
  sleep 3
done
ok "api: all components heartbeating, providers [$PROVIDERS], $err project(s) in the workspace"
[ "$err" != 0 ] || echo "  ! the workspace is empty: clone repos into $WORKSPACE_HOST_DIR (or ask the team to, with gh)"
code="$(curl -s -o /dev/null -w '%{http_code}' -m 5 "$BASE_URL/")"
[ "$code" = 200 ] || fail "dashboard returned HTTP $code"
code="$(curl -s -o /dev/null -w '%{http_code}' -m 5 "$BASE_URL/api/meta")"
[ "$code" = 401 ] || fail "API answered $code without a login (expected 401)"
ok "dashboard: $BASE_URL/ (API requires login)"
PUBLIC_URL="$(env_get AI_TEAM_PUBLIC_URL)"
PUBLIC_HOST="$(printf '%s' "$PUBLIC_URL" | sed -E 's#^[a-z]+://##; s#[:/].*##')"
if [ -n "$PUBLIC_HOST" ] && [ "$PUBLIC_HOST" != "$DEPLOY_HOST" ] && [ "$PUBLIC_HOST" != localhost ]; then
  # through the reverse proxy on the target (port 80), independent of whether DNS is in place yet
  pcode="$(curl -s -o /dev/null -w '%{http_code}' -m 5 -H "Host: $PUBLIC_HOST" "http://$DEPLOY_HOST/api/health" || true)"
  if [ "$pcode" = 200 ]; then ok "reverse proxy: $PUBLIC_HOST → dashboard"
  else echo "  ! reverse proxy: http://$DEPLOY_HOST with Host $PUBLIC_HOST returned $pcode (add the proxy host in NPM)"; fi
  if getent hosts "$PUBLIC_HOST" >/dev/null; then ok "dns: $PUBLIC_HOST resolves"
  else echo "  ! dns: $PUBLIC_HOST does not resolve yet (add it to Pi-hole)"; fi
fi

agent_ctr="$(ctr agent)"
[ -z "$(dk exec "$agent_ctr" sh -c 'ls -A /workspace/ai-team 2>/dev/null')" ] || fail "/workspace/ai-team is visible to agents"
dk exec "$agent_ctr" sh -c 'git --version && gh --version && command -v playwright-mcp' >/dev/null \
  || fail "agent toolbox incomplete (git / gh / playwright-mcp)"
n="$(dk exec "$agent_ctr" sh -c 'ls /data/skills | wc -l')"
ok "agents: ai-team hidden, git + gh + playwright available, $n skills mounted"
if $GITHUB; then
  who="$(dk exec "$agent_ctr" gh api user --jq .login 2>&1)" || fail "gh not logged in inside agents: $who"
  ok "github: agents use gh as $who"
fi
if [ -n "$SECRET" ]; then
  dk exec "$agent_ctr" test -s /run/secrets/claude_oauth_token || fail "Claude token secret not mounted"
  ok "claude: token mounted in agents"
fi

if $SMOKE; then
  echo "smoke test: one small real task…"
  tid="$(acurl -sf -XPOST "$BASE_URL/api/tasks" -H 'content-type: application/json' \
         -d '{"text":"Smoke test: what is 2 + 2? Answer with just the number."}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')"
  sdeadline=$((SECONDS + 600))
  while :; do
    st="$(acurl -sf "$BASE_URL/api/tasks/$tid" | python3 -c 'import json,sys;print(json.load(sys.stdin)["status"])')"
    case "$st" in done) ok "smoke task #$tid done"; break ;; failed|cancelled|hold*) fail "smoke task #$tid ended $st" ;; esac
    [ "$SECONDS" -lt "$sdeadline" ] || fail "smoke task #$tid still $st after 10 min"
    sleep 3
  done
fi

# Only now drop superseded token secrets (ones still attached to a task are skipped by docker).
for old in $(dk secret ls --format '{{.Name}}' | grep "^$SECRET_PREFIX" | grep -vx "${SECRET:-none}" || true); do
  dk secret rm "$old" >/dev/null 2>&1 || true
done
echo "deployed and verified $TAG on '$CTX' (providers: $PROVIDERS) → $BASE_URL"
