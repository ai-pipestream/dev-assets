#!/usr/bin/env bash
set -uo pipefail

# Verify that a developer machine has every tool and credential needed
# to build and run the ai-pipestream platform. Exit code is non-zero if
# anything mandatory is missing.
#
# Run this before bootstrap.sh.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/shared-utils.sh"

MISSING_REQUIRED=()
MISSING_OPTIONAL=()

check_required() {
  local name="$1" cmd="$2" version_cmd="$3"
  echo -n "Checking for ${name}... "
  if command -v "${cmd}" >/dev/null 2>&1; then
    echo -e "${GREEN}INSTALLED${NC}"
    local ver
    ver=$(eval "${version_cmd}" 2>&1 | head -n 1 || true)
    [[ -n "${ver}" ]] && echo "  ${ver}"
  else
    echo -e "${RED}MISSING${NC}"
    MISSING_REQUIRED+=("${name}")
  fi
}

check_optional() {
  local name="$1" cmd="$2" version_cmd="$3" note="$4"
  echo -n "Checking for ${name}... "
  if command -v "${cmd}" >/dev/null 2>&1; then
    echo -e "${GREEN}INSTALLED${NC}"
    local ver
    ver=$(eval "${version_cmd}" 2>&1 | head -n 1 || true)
    [[ -n "${ver}" ]] && echo "  ${ver}"
  else
    echo -e "${YELLOW}MISSING (optional)${NC}"
    echo "  ${note}"
    MISSING_OPTIONAL+=("${name}")
  fi
}

check_env_var() {
  local var="$1" note="$2"
  echo -n "Checking \$${var}... "
  if [[ -n "${!var:-}" ]]; then
    echo -e "${GREEN}SET${NC}"
  else
    echo -e "${RED}UNSET${NC}"
    echo "  ${note}"
    MISSING_REQUIRED+=("\$${var}")
  fi
}

print_status "header" "ai-pipestream — Prerequisite Check"

# --- Mandatory ------------------------------------------------------------

# Docker + daemon
check_required "Docker"       "docker"       "docker --version"
echo -n "Checking Docker daemon connectivity... "
if docker ps >/dev/null 2>&1; then
  echo -e "${GREEN}OK${NC}"
else
  echo -e "${RED}FAILED${NC}"
  echo "  Start Docker Desktop, or on Linux add your user to the 'docker' group:"
  echo "  sudo usermod -aG docker \$USER && newgrp docker"
  MISSING_REQUIRED+=("docker daemon")
fi

# Docker Compose v2 (plugin, not standalone docker-compose)
echo -n "Checking for Docker Compose v2... "
if docker compose version >/dev/null 2>&1; then
  echo -e "${GREEN}INSTALLED${NC}"
  echo "  $(docker compose version 2>&1 | head -n 1)"
else
  echo -e "${RED}MISSING${NC}"
  echo "  Install Docker Desktop (ships with compose v2) or the docker-compose-plugin package."
  MISSING_REQUIRED+=("docker compose v2")
fi

# Java 21 — platform standard per 07-build-versions.md
check_required "Java (21+)"   "java"  "java --version"
if command -v java >/dev/null 2>&1; then
  JAVA_MAJOR=$(java -version 2>&1 | head -n 1 | sed -E 's/.*"([0-9]+).*/\1/')
  if [[ -n "${JAVA_MAJOR}" && "${JAVA_MAJOR}" -lt 21 ]]; then
    echo -e "  ${RED}Java ${JAVA_MAJOR} detected — platform requires 21 (Temurin recommended).${NC}"
    MISSING_REQUIRED+=("Java 21")
  fi
fi

# Node + pnpm — required for pipestream-frontend
check_required "Node.js (LTS)" "node"  "node --version"
check_required "pnpm"          "pnpm"  "pnpm --version"

# Git + GitHub auth
check_required "git"           "git"   "git --version"
check_env_var  "GITHUB_ACTOR"   "Required by Gradle to pull pipestream libraries from GitHub Packages. Set in ~/.gradle/gradle.properties or shell env."
check_env_var  "GITHUB_TOKEN"   "Personal access token with read:packages. Required to resolve ai.pipestream:* dependencies."

# --- Optional but recommended --------------------------------------------

check_optional "gh (GitHub CLI)" "gh"    "gh --version" \
  "Preferred way to clone via setup-workspace.sh; falls back to plain git."
check_optional "buf"            "buf"   "buf --version" \
  "The proto toolchain plugin downloads its own buf; a system buf is only needed for manual 'buf lint' / 'buf breaking' runs against pipestream-protos."
check_optional "Quarkus CLI"    "quarkus" "quarkus --version" \
  "Convenience only; ./gradlew quarkusDev works without it."
check_optional "Gradle"         "gradle" "gradle --version" \
  "Every project ships a Gradle wrapper; a system Gradle is never required."

# --- Summary --------------------------------------------------------------

echo
print_status "header" "Prerequisite Check Summary"
if (( ${#MISSING_REQUIRED[@]} == 0 )); then
  print_status "success" "All required tools and credentials are present."
else
  print_status "error" "Missing required: ${MISSING_REQUIRED[*]}"
fi

if (( ${#MISSING_OPTIONAL[@]} > 0 )); then
  print_status "info" "Missing optional: ${MISSING_OPTIONAL[*]}"
fi

(( ${#MISSING_REQUIRED[@]} == 0 ))
