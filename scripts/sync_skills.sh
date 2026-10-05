#!/usr/bin/env bash
# Collect the host's Claude skills (~/.claude/skills incl. synced ones, and every plugin's skills) into DEST.
#   scripts/sync_skills.sh data/skills
set -euo pipefail
dest="${1:?usage: sync_skills.sh DEST}"
mkdir -p "$dest"
find "$dest" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
n=0
while IFS= read -r skill_md; do
  dir="$(dirname "$skill_md")"; name="$(basename "$dir")"
  case "$skill_md" in */plugins/*) [ -e "$dest/$name" ] && name="$(basename "$(dirname "$(dirname "$dir")")")-$name" ;; esac
  [ -e "$dest/$name" ] && continue
  cp -rL "$dir" "$dest/$name" 2>/dev/null && n=$((n + 1))
done < <(find "$HOME/.claude/skills" "$HOME/.claude/plugins" -name SKILL.md -not -path '*/.trash/*' \
           -not -path '*/node_modules/*' 2>/dev/null | sort)
echo "$n"
