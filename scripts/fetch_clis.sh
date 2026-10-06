#!/usr/bin/env bash
# Put the Claude Code and Codex CLI binaries in vendor/cli/ once, so image builds never download them.
#   scripts/fetch_clis.sh            ensure both are present at the versions in scripts/cli-versions.env
#   scripts/fetch_clis.sh --force    fetch again
# Per binary: keep it if it's already there at the right version; else copy it out of a local ai-team image
# (no download); else download it (with retries; Claude's is checked against its release manifest).
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/cli-versions.env
OUT=vendor/cli
FORCE=false; [ "${1:-}" = "--force" ] && FORCE=true
mkdir -p "$OUT"

have() { [ -s "$OUT/$1" ] && [ "$(cat "$OUT/$1.version" 2>/dev/null)" = "$2" ]; }
retry() { local n; for n in 1 2 3 4 5; do "$@" && return 0; echo "  … attempt $n failed, retrying in $((n * 3))s" >&2; sleep $((n * 3)); done; return 1; }
from_image() {   # from_image <name> <version> <path in image>
  local img cid
  for img in ai-team:latest ai-team:dev; do
    docker image inspect "$img" >/dev/null 2>&1 || continue
    cid="$(docker create --entrypoint true "$img")"
    if docker cp -L "$cid:$3" "$OUT/$1.tmp" 2>/dev/null; then
      docker rm "$cid" >/dev/null
      chmod +x "$OUT/$1.tmp"
      # the copy only counts if it reports the wanted version
      if docker run --rm -v "$PWD/$OUT/$1.tmp:/x:ro" --entrypoint /x "$img" --version 2>/dev/null | grep -q "$2"; then
        mv "$OUT/$1.tmp" "$OUT/$1"; return 0
      fi
      rm -f "$OUT/$1.tmp"
    else
      docker rm "$cid" >/dev/null
    fi
  done
  return 1
}

# --- Claude Code -------------------------------------------------------------------------------------
if $FORCE || ! have claude "$CLAUDE_VERSION"; then
  if ! $FORCE && from_image claude "$CLAUDE_VERSION" "/home/agent/.local/share/claude/versions/$CLAUDE_VERSION"; then
    echo "  ✓ claude $CLAUDE_VERSION copied from the local ai-team image"
  else
    base="https://downloads.claude.ai/claude-code-releases/$CLAUDE_VERSION"
    echo "  downloading claude $CLAUDE_VERSION…"
    retry curl -fsSL --max-time 600 "$base/linux-x64/claude" -o "$OUT/claude.tmp"
    want="$(retry curl -fsSL --max-time 60 "$base/manifest.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["platforms"]["linux-x64"]["checksum"])')"
    got="$(sha256sum "$OUT/claude.tmp" | cut -d' ' -f1)"
    [ "$want" = "$got" ] || { rm -f "$OUT/claude.tmp"; echo "  ✗ claude checksum mismatch" >&2; exit 1; }
    chmod +x "$OUT/claude.tmp" && mv "$OUT/claude.tmp" "$OUT/claude"
    echo "  ✓ claude $CLAUDE_VERSION downloaded (checksum ok)"
  fi
  echo "$CLAUDE_VERSION" > "$OUT/claude.version"
fi

# --- Codex -------------------------------------------------------------------------------------------
if $FORCE || ! have codex "$CODEX_VERSION"; then
  if ! $FORCE && from_image codex "$CODEX_VERSION" /home/agent/.local/bin/codex; then
    echo "  ✓ codex $CODEX_VERSION copied from the local ai-team image"
  else
    echo "  downloading codex $CODEX_VERSION…"
    tmp="$(mktemp -d)"
    retry curl -fsSL --max-time 600 \
      "https://github.com/openai/codex/releases/download/rust-v${CODEX_VERSION}/codex-x86_64-unknown-linux-musl.tar.gz" -o "$tmp/codex.tgz"
    tar xzf "$tmp/codex.tgz" -C "$tmp" && mv "$tmp/codex-x86_64-unknown-linux-musl" "$OUT/codex" && chmod +x "$OUT/codex"
    rm -rf "$tmp"
    echo "  ✓ codex $CODEX_VERSION downloaded"
  fi
  echo "$CODEX_VERSION" > "$OUT/codex.version"
fi
echo "  ✓ CLIs ready in $OUT: claude $(cat "$OUT/claude.version"), codex $(cat "$OUT/codex.version")"
