#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Pipestream AI - Prerequisite Check${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

check_tool() {
    local tool_name=$1
    local command_check=$2
    local version_command=$3
    
    echo -n "Checking for $tool_name... "
    
    if command -v "$command_check" &> /dev/null; then
        echo -e "${GREEN}INSTALLED${NC}"
        echo -e "  $($version_command 2>&1 | head -n 1)"
    else
        echo -e "${RED}MISSING${NC}"
        echo -e "  ${YELLOW}Please install $tool_name to proceed with development.${NC}"
    fi
    echo ""
}

# 1. Docker
check_tool "Docker" "docker" "docker --version"

echo -n "Checking Docker daemon connectivity... "
if docker ps > /dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
    echo -e "  ${YELLOW}Cannot connect to Docker daemon.${NC}"
    echo -e "  ${YELLOW}Fix: Run the following command:${NC}"
    echo -e "       ${GREEN}sudo usermod -aG docker \$USER && newgrp docker${NC}"
fi
echo ""

# 2. Java
check_tool "Java" "java" "java --version"

# 3. Groovy
check_tool "Groovy" "groovy" "groovy --version"

# 4. Gradle
check_tool "Gradle" "gradle" "gradle --version"

# 5. Quarkus CLI
check_tool "Quarkus CLI" "quarkus" "quarkus --version"

# 6. Node.js
check_tool "Node.js" "node" "node --version"

# 7. NPM (usually comes with Node, but good to check)
check_tool "NPM" "npm" "npm --version"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Check Complete${NC}"
echo -e "${BLUE}========================================${NC}"
