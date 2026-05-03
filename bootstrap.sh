#!/usr/bin/env bash
# ai-pipestream developer machine bootstrap.
#
# Entry point. Verifies python3 (>= 3.11) is available, then hands off to
# scripts/bootstrap.py for everything else (prereq install, repo clone,
# build, process-compose, reference-code sync).
#
# Usage:
#   ./bootstrap.sh check            # detect prereqs and offer to install
#   ./bootstrap.sh check --yes      # auto-confirm install prompt
#   ./bootstrap.sh check --skip-install
#   ./bootstrap.sh --help           # see all subcommands

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
    cat >&2 <<EOF
ERROR: python3 not found.

Install python3 (>= 3.11) for your platform first:
  Ubuntu/Debian:  sudo apt install python3
  Fedora/RHEL:    sudo dnf install python3
  macOS:          brew install python3   (or use the python.org installer)

Then re-run ./bootstrap.sh
EOF
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 11 ]]; then
    echo "ERROR: python3 >= 3.11 required (found ${PY_VERSION})." >&2
    echo "  We rely on the stdlib tomllib module (added in 3.11)." >&2
    exit 1
fi

exec python3 "${SCRIPT_DIR}/scripts/bootstrap.py" "$@"
