#!/usr/bin/env bash
set -euo pipefail

# One-shot bootstrap for a fresh ai-pipestream developer machine.
#
#   1. Verify prerequisites (tools + credentials)
#   2. Clone every platform repo listed in config/platform-repos.tsv
#   3. Clone every OSS reference repo listed in config/reference-repos.tsv
#   4. Print next steps
#
# Idempotent: re-running clones anything missing and (with --update)
# fast-forwards anything already present.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/shared-utils.sh"

DO_UPDATE=false
USE_SSH=false
SKIP_REFERENCE=false
SKIP_PREREQS=false

usage() {
  cat <<EOF
Usage: $0 [--update] [--ssh|--https] [--skip-reference] [--skip-prereqs]

Options:
  --update          Also fast-forward existing clones (default: skip existing)
  --ssh             Use SSH URLs for platform repos (default: HTTPS)
  --https           Use HTTPS URLs for platform repos (default)
  --skip-reference  Skip the reference-code sync (useful on CI)
  --skip-prereqs    Skip the prerequisite check (not recommended)
  -h, --help        Show this help

After this script succeeds, you should be able to:
  cd \$WORKSPACE/core-projects/pipestream-platform && ./gradlew build
  cd \$WORKSPACE/core-projects/pipestream-frontend && pnpm install
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --update)         DO_UPDATE=true; shift ;;
    --ssh)            USE_SSH=true; shift ;;
    --https)          USE_SSH=false; shift ;;
    --skip-reference) SKIP_REFERENCE=true; shift ;;
    --skip-prereqs)   SKIP_PREREQS=true; shift ;;
    -h|--help)        usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

print_status "header" "ai-pipestream Workspace Bootstrap"

# 1. Prerequisites ----------------------------------------------------------
if ! $SKIP_PREREQS; then
  print_status "info" "Step 1/3: checking prerequisites"
  if ! "${SCRIPT_DIR}/check-prerequisites.sh"; then
    print_status "error" "Prerequisite check failed. Fix the missing items above and re-run."
    exit 1
  fi
else
  print_status "warning" "Skipping prerequisite check (--skip-prereqs)"
fi

# 2. Platform repos ---------------------------------------------------------
print_status "info" "Step 2/3: cloning platform repos"
WORKSPACE_ARGS=()
$DO_UPDATE && WORKSPACE_ARGS+=(--update)
$USE_SSH   && WORKSPACE_ARGS+=(--ssh)
"${SCRIPT_DIR}/setup-workspace.sh" "${WORKSPACE_ARGS[@]}"

# 3. Reference-code sync ----------------------------------------------------
if ! $SKIP_REFERENCE; then
  print_status "info" "Step 3/3: cloning reference-code (OSS dependencies)"
  REFERENCE_ARGS=()
  $DO_UPDATE && REFERENCE_ARGS+=(--update)
  "${SCRIPT_DIR}/reference-code-sync.sh" "${REFERENCE_ARGS[@]}"
else
  print_status "warning" "Skipping reference-code sync (--skip-reference)"
fi

# Done ---------------------------------------------------------------------
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

echo
print_status "header" "Bootstrap Complete"
cat <<EOF

Workspace root: ${WORKSPACE_ROOT}

Next steps:

  1. Build the BOM + platform extensions:
     cd ${WORKSPACE_ROOT}/core-projects/pipestream-platform
     ./gradlew build publishToMavenLocal

  2. Build the protos:
     cd ${WORKSPACE_ROOT}/core-projects/pipestream-protos
     ./gradlew build

  3. Install frontend deps:
     cd ${WORKSPACE_ROOT}/core-projects/pipestream-frontend
     pnpm install

  4. Read the standards before making changes:
     ${WORKSPACE_ROOT}/dev-tools/dev-assets/docs/standards/README.md

EOF
