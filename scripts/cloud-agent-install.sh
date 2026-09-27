#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the Grok Build workspace.
# Safe to run when this file is missing from the checked-out revision:
# the dashboard install command inlines the same steps.
set -eu

echo "[grok-build] bootstrap"

mkdir -p "${HOME}/.grok-build/work"

git --version
node --version
npm --version
python3 --version
pnpm --version
gh --version
command -v google-chrome

if [ -f grok-build.contract.json ]; then
  jq -e '.role == "builder"' grok-build.contract.json >/dev/null
  echo "[grok-build] contract ok"
fi

date -u +"%Y-%m-%dT%H:%M:%SZ" > "${HOME}/.grok-build/ready"
echo "[grok-build] ready"
