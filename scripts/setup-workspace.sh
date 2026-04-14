#!/usr/bin/env bash
set -euo pipefail

# Clone (or update) every ai-pipestream platform repo listed in
# config/platform-repos.tsv into the workspace root.
#
# Layout created:
#   $WORKSPACE/core-projects/<repo>
#   $WORKSPACE/modules/<repo>
#   $WORKSPACE/dev-tools/<repo>
#   $WORKSPACE/connectors/<repo>
#
# The manifest is the source of truth. To add a new repo, edit
# config/platform-repos.tsv and re-run this script.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# dev-assets lives at $WORKSPACE/dev-tools/dev-assets, so the workspace root
# is three levels up from this script (scripts -> dev-assets -> dev-tools -> WORKSPACE).
WORKSPACE_DEFAULT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
MANIFEST_DEFAULT="${SCRIPT_DIR}/config/platform-repos.tsv"

source "${SCRIPT_DIR}/shared-utils.sh"

DO_UPDATE=false
DO_LIST=false
USE_SSH=false
WORKSPACE="${WORKSPACE_DEFAULT}"
MANIFEST_PATH="${MANIFEST_DEFAULT}"

usage() {
  cat <<EOF
Usage: $0 [--update] [--list] [--ssh|--https] [--workspace PATH] [--manifest PATH]

Clones every ai-pipestream platform repo from the manifest into the workspace.

Options:
  --update         Fetch + fast-forward existing clones (default: skip existing)
  --list           Dry run: print what would happen, change nothing
  --ssh            Use SSH URLs (default: HTTPS)
  --https          Use HTTPS URLs (default)
  --workspace PATH Override workspace root (default: ${WORKSPACE_DEFAULT})
  --manifest PATH  Override manifest path (default: ${MANIFEST_DEFAULT})

Manifest format (one repo per line, '|'-delimited, '#' comments allowed):
  category|repo_name|branch
  Use '-' for branch to use the remote default.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --update) DO_UPDATE=true; shift ;;
    --list) DO_LIST=true; shift ;;
    --ssh) USE_SSH=true; shift ;;
    --https) USE_SSH=false; shift ;;
    --workspace) WORKSPACE="$2"; shift 2 ;;
    --manifest) MANIFEST_PATH="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

if [[ ! -f "${MANIFEST_PATH}" ]]; then
  print_status "error" "Manifest not found: ${MANIFEST_PATH}"
  exit 1
fi

print_status "header" "Platform Workspace Sync"
print_status "info" "Workspace: ${WORKSPACE}"
print_status "info" "Manifest:  ${MANIFEST_PATH}"
print_status "info" "URLs:      $(if $USE_SSH; then echo SSH; else echo HTTPS; fi)"
print_status "info" "Mode:      $(if $DO_UPDATE; then echo 'clone + update existing'; else echo 'clone missing only'; fi)"
echo

mkdir -p "${WORKSPACE}"

TOTAL=0; CLONED=0; UPDATED=0; SKIPPED=0; ERR=0
set +e

while IFS= read -r raw; do
  line="${raw%$'\r'}"
  [[ -z "${line}" ]] && continue
  [[ "${line}" =~ ^[[:space:]]*# ]] && continue

  IFS='|' read -r CATEGORY REPO BRANCH <<< "${line}"
  CATEGORY="${CATEGORY//[[:space:]]/}"
  REPO="${REPO//[[:space:]]/}"
  BRANCH="${BRANCH//[[:space:]]/}"

  if [[ -z "${CATEGORY}" || -z "${REPO}" ]]; then
    print_status "warning" "Skipping invalid line: ${line}"
    continue
  fi

  ((TOTAL++))

  DEST="${WORKSPACE}/${CATEGORY}/${REPO}"

  if $USE_SSH; then
    URL="git@github.com:ai-pipestream/${REPO}.git"
  else
    URL="https://github.com/ai-pipestream/${REPO}.git"
  fi

  if [[ -d "${DEST}/.git" ]]; then
    if $DO_UPDATE; then
      if $DO_LIST; then
        print_status "info" "[${CATEGORY}/${REPO}] would fetch + fast-forward"
        ((UPDATED++)); continue
      fi
      (
        cd "${DEST}"
        git fetch --all --prune >/dev/null 2>&1 || true
        if [[ -n "${BRANCH}" && "${BRANCH}" != "-" ]]; then
          git checkout "${BRANCH}" >/dev/null 2>&1 || true
        fi
        git pull --ff-only >/dev/null 2>&1 || true
      ) && { print_status "success" "[${CATEGORY}/${REPO}] updated"; ((UPDATED++)); } \
        || { print_status "error"   "[${CATEGORY}/${REPO}] update failed"; ((ERR++)); }
    else
      print_status "info" "[${CATEGORY}/${REPO}] exists (skipping; use --update to pull)"
      ((SKIPPED++))
    fi
    continue
  fi

  if $DO_LIST; then
    print_status "info" "[${CATEGORY}/${REPO}] would clone from ${URL}"
    ((CLONED++)); continue
  fi

  mkdir -p "${WORKSPACE}/${CATEGORY}"
  print_status "info" "[${CATEGORY}/${REPO}] cloning from ${URL}"

  CLONE_ARGS=(git clone)
  if [[ -n "${BRANCH}" && "${BRANCH}" != "-" ]]; then
    CLONE_ARGS+=("--branch" "${BRANCH}")
  fi
  CLONE_ARGS+=("${URL}" "${DEST}")

  if "${CLONE_ARGS[@]}" >/dev/null 2>&1; then
    print_status "success" "[${CATEGORY}/${REPO}] cloned"
    ((CLONED++))
  else
    # Retry without --branch in case the branch doesn't exist yet
    if [[ -n "${BRANCH}" && "${BRANCH}" != "-" ]]; then
      print_status "warning" "[${CATEGORY}/${REPO}] branch '${BRANCH}' not found; retrying with remote default"
      if git clone "${URL}" "${DEST}" >/dev/null 2>&1; then
        print_status "success" "[${CATEGORY}/${REPO}] cloned (remote default branch)"
        ((CLONED++))
      else
        print_status "error" "[${CATEGORY}/${REPO}] clone failed — check access to ${URL}"
        ((ERR++))
      fi
    else
      print_status "error" "[${CATEGORY}/${REPO}] clone failed — check access to ${URL}"
      ((ERR++))
    fi
  fi
done < "${MANIFEST_PATH}"

set -e

echo
print_status "header" "Platform Workspace Sync Complete"
echo "Total: ${TOTAL}  Cloned: ${CLONED}  Updated: ${UPDATED}  Skipped: ${SKIPPED}  Errors: ${ERR}"
if (( ERR > 0 )); then
  print_status "warning" "Some repos failed. Check auth (GITHUB_TOKEN / SSH keys) and network."
  exit 1
fi
