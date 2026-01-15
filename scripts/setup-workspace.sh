#!/bin/bash
set -e

# Configuration
ORG="ai-pipestream"
BASE_DIR=$(pwd)
GITHUB_BASE_URL="https://github.com/$ORG"

# Repository Mappings
# Format: "category/repo_name"
REPOS=(
    # Core Services
    "core-services/account-service"
    "core-services/mapping-service"
    "core-services/connector-admin"
    "core-services/opensearch-manager"
    "core-services/connector-intake-service"
    "core-services/repository-service"
    "core-services/platform-registration-service"
    "core-services/pipestream-engine"
    "core-services/pipestream-engine-kafka-sidecar"
    "core-services/pipestream-platform"
    "core-services/pipestream-protos"

    # Modules
    "modules/module-embedder"
    "modules/module-echo"
    "modules/module-parser"
    "modules/module-opensearch-sink"
    "modules/module-chunker"
    "modules/module-proxy"
    "modules/module-pipeline-probe"

    # Frontend
    "frontend/pipestream-frontend"

    # Dev Tools (dev-assets is already cloned, but listed for completeness)
    "dev-tools/quarkus-buf-grpc-generator"
    "dev-tools/pipestream-wiremock-server"
    "dev-tools/docker-integration-tests"
    "dev-tools/tika4-shaded"

    # Sample Documents
    "sample-documents/sample-documents"
)

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}Starting Pipestream AI Environment Setup...${NC}"

for entry in "${REPOS[@]}"; do
    CATEGORY=$(dirname "$entry")
    REPO_NAME=$(basename "$entry")
    TARGET_DIR="$BASE_DIR/$CATEGORY/$REPO_NAME"

    echo -e "Processing ${YELLOW}$REPO_NAME${NC} in ${BLUE}$CATEGORY${NC}..."

    # Ensure category directory exists
    mkdir -p "$BASE_DIR/$CATEGORY"

    if [ -d "$TARGET_DIR/.git" ]; then
        echo -e "  ${GREEN}✓${NC} Already exists. Updating..."
        cd "$TARGET_DIR"
        # Try to pull, but don't fail the script if it fails (e.g. detached head, local changes)
        git pull --rebase || echo -e "  ${RED}⚠ Pull failed. Please check manually.${NC}"
        cd "$BASE_DIR"
    else
        echo -e "  Cloning..."
        # Try gh CLI first, fall back to HTTPS
        if command -v gh &> /dev/null; then
            gh repo clone "$ORG/$REPO_NAME" "$TARGET_DIR" || git clone "$GITHUB_BASE_URL/$REPO_NAME.git" "$TARGET_DIR"
        else
            git clone "$GITHUB_BASE_URL/$REPO_NAME.git" "$TARGET_DIR"
        fi
    fi
done

echo -e "${GREEN}Setup Complete!${NC}"
