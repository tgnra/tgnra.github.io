#!/usr/bin/env bash
# Build the site and serve it at http://localhost:5000 with live reload.
# Usage: ./dev.sh [--drafts] [other `python -m ssg serve` flags]
set -euo pipefail
cd "$(dirname "$0")"

if command -v nix-shell >/dev/null 2>&1; then
  # NixOS: pip wheels can't find system libraries, so use shell.nix.
  exec nix-shell shell.nix --run 'python -m ssg serve --port 5000 "$@"' -- "$@"
fi

[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
exec .venv/bin/python -m ssg serve --port 5000 "$@"
