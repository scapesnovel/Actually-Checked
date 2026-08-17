#!/usr/bin/env bash
# Safe push: pushes the local main TREE onto remote main as a new commit,
# but preserves whatever .github/workflows/ exists on the REMOTE
# (the GitHub App token isn't allowed to touch workflow files).
set -e
cd "$(dirname "$0")/.."
MSG="${1:-sync from sandbox}"
git fetch origin main
git checkout -B publish origin/main
git checkout main -- .
git add -A
# CRITICAL: unstage local workflows AFTER add -A, restore remote's copy
git rm -rq --cached .github/workflows 2>/dev/null || true
git checkout origin/main -- .github/workflows 2>/dev/null || true
git diff --cached --quiet || git commit -m "$MSG"
git push origin publish:main
git checkout -f main
git branch -D publish
echo "PUSHED: $MSG (remote workflows preserved)"
