#!/usr/bin/env bash
# Save a restore copy of the current repo before Grok Build changes existing work.
# Usage: scripts/save-copy.sh [label]
set -eu

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[grok-build] save-copy: not a git repository" >&2
  exit 1
fi

label="${1:-pre-change}"
safe_label="$(printf '%s' "$label" | tr -c 'a-zA-Z0-9._-' '-')"
stamp="$(date -u +"%Y%m%dT%H%M%SZ")"
branch="backup/${stamp}-${safe_label}"

git branch "$branch"
echo "[grok-build] saved committed copy as branch ${branch} ($(git rev-parse --short HEAD))"

if [ -n "$(git status --porcelain)" ]; then
  stash_sha="$(git stash create "grok-build-save-copy ${branch}")"
  if [ -n "${stash_sha}" ]; then
    git stash store -m "grok-build-save-copy ${branch}" "$stash_sha"
    echo "[grok-build] saved uncommitted copy as stash ${stash_sha}"
  fi
fi

echo "$branch"
