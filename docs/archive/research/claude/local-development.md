# Local Development Guide

**Date**: 2025-10-23
**Purpose**: Complete guide for setting up and working with the Pipeline Engine locally

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [First-Time Setup](#first-time-setup)
3. [Daily Development Workflows](#daily-development-workflows)
4. [Working with Different Components](#working-with-different-components)
5. [Common Development Tasks](#common-development-tasks)
6. [Troubleshooting](#troubleshooting)
7. [IDE Configuration](#ide-configuration)
8. [Tips and Tricks](#tips-and-tricks)

---

## Prerequisites

### Required Software

| Tool | Version | Purpose | Installation |
|------|---------|---------|--------------|
| **Java** | 21+ | Backend services | https://adoptium.net/ |
| **Node.js** | 22+ | Frontend & web-proxy | https://nodejs.org/ |
| **pnpm** | 10+ | Node package manager | `npm install -g pnpm` |
| **Docker** | Latest | Infrastructure services | https://www.docker.com/ |
| **Docker Compose** | Latest | Multi-container orchestration | Included with Docker Desktop |
| **Gradle** | 8.11+ | Java build tool | Included via wrapper |
| **Git** | Latest | Version control | https://git-scm.com/ |

### Optional Software

| Tool | Purpose | Installation |
|------|---------|--------------|
| **IntelliJ IDEA** | Recommended Java IDE | https://www.jetbrains.com/idea/ |
| **VS Code** | Recommended for Node.js | https://code.visualstudio.com/ |
| **Postman** | API testing | https://www.postman.com/ |
| **Buf CLI** | Proto management | https://buf.build/docs/installation |

### Hardware Requirements

- **Minimum**: 16 GB RAM, 4 cores
- **Recommended**: 32 GB RAM, 8 cores
- **Disk Space**: 20 GB free (for Docker images, builds, etc.)

---

## First-Time Setup

### Step 1: Clone Repository

```bash
# Clone the repository
git clone https://github.com/YOUR_ORG/pipeline-engine-refactor.git
cd pipeline-engine-refactor

# Verify you're on the right branch
git branch
```

### Step 2: Configure GitHub Packages (if using published artifacts)

For pulling published artifacts from GitHub Packages:

```bash
# Create Gradle properties file
mkdir -p ~/.gradle
cat >> ~/.gradle/gradle.properties << EOF
gpr.user=YOUR_GITHUB_USERNAME
gpr.token=YOUR_GITHUB_PERSONAL_ACCESS_TOKEN
EOF
```

**Generate GitHub Personal Access Token**:
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `read:packages`, `write:packages`
4. Copy token and use in gradle.properties above

### Step 3: Run Setup Script

```bash
# Make script executable
chmod +x dev-infrastructure/scripts/setup-local-dev.sh

# Run setup
./dev-infrastructure/scripts/setup-local-dev.sh
```

**What this does**:
1. Builds gRPC stubs → publishes to Maven Local
2. Builds libraries → publishes to Maven Local
3. Installs Node dependencies via pnpm

**Expected output**:
```
==========================================
Pipeline Engine - Local Development Setup
==========================================

✓ Prerequisites check passed

Building gRPC stubs...
✓ gRPC stubs published to Maven Local

Building libraries...
✓ Libraries published to Maven Local

Installing Node dependencies...
✓ Node dependencies installed

==========================================
✓ Local development environment ready!
==========================================
```

### Step 4: Start Infrastructure Services

```bash
# Start Docker Compose services
cd dev-infrastructure
docker compose -f compose-devservices.yml up -d

# Verify services are running
docker compose -f compose-devservices.yml ps
```

**Services started**:
- MySQL (port 3306)
- Kafka + Zookeeper (ports 9092, 2181)
- Apicurio Registry (port 8081)
- Consul (port 8500)
- MinIO (ports 9000, 9001)
- OpenSearch (port 9200)
- Traefik (ports 80, 8080)

### Step 5: Verify Setup

```bash
# Test building an application
cd applications/account-manager
./gradlew build

# Expected: BUILD SUCCESSFUL

# Test starting Quarkus dev mode
./gradlew quarkusDev
# Press 'w' to open browser, 'q' to quit
```

---

## Daily Development Workflows

### Scenario 1: Working on Application Code (Most Common)

You're working on `account-manager` service.

```bash
# Terminal 1: Ensure infrastructure is running
cd dev-infrastructure
docker compose -f compose-devservices.yml ps  # Check status
# If stopped: docker compose -f compose-devservices.yml up -d

# Terminal 2: Start application in dev mode
cd applications/account-manager
./gradlew quarkusDev
```

**What you get**:
- **Hot Reload**: Java code changes auto-reload (no restart needed)
- **Dev UI**: http://localhost:8080/q/dev
- **Swagger UI**: http://localhost:8080/q/swagger-ui
- **Logs**: Real-time in terminal

**Development loop**:
1. Edit Java code in your IDE
2. Save file
3. Quarkus automatically reloads
4. Test via Swagger UI or curl
5. Repeat

### Scenario 2: Working on Frontend

You're working on Vue.js frontend embedded in an application.

```bash
# Terminal 1: Start infrastructure
cd dev-infrastructure
docker compose -f compose-devservices.yml up -d

# Terminal 2: Start backend service
cd applications/mapping-service
./gradlew quarkusDev

# Terminal 3 (optional): Watch frontend build
cd applications/mapping-service/src/main/ui-vue
pnpm run dev
```

**Access**:
- Frontend: http://localhost:8080 (proxied through Quarkus)
- Quarkus hot reload works for backend
- Vite hot reload works for frontend

### Scenario 3: Working on Multiple Services

Testing interaction between `connector-service` and `account-manager`.

```bash
# Terminal 1: Infrastructure
cd dev-infrastructure
docker compose -f compose-devservices.yml up -d

# Terminal 2: account-manager
cd applications/account-manager
./gradlew quarkusDev

# Terminal 3: connector-service
cd applications/connector-service
./gradlew quarkusDev
```

**Services auto-discover each other via Consul**.

### Scenario 4: Full-Stack Development

Working on backend + web-proxy + platform-shell.

```bash
# Terminal 1: Infrastructure
cd dev-infrastructure
docker compose -f compose-devservices.yml up -d

# Terminal 2: Backend (example: account-manager)
cd applications/account-manager
./gradlew quarkusDev

# Terminal 3: Web Proxy
cd node/web-proxy
pnpm run dev

# Terminal 4: Platform Shell
cd node/platform-shell
pnpm run dev
```

**Access**:
- Platform Shell (main UI): http://localhost:37200
- Web Proxy API: http://localhost:37201
- Backend API: http://localhost:8080

**Traffic flow**:
```
Browser → Platform Shell (37200)
    ↓
Web Proxy (37201) ← gRPC-Web translation
    ↓
Account Manager (8080) ← gRPC
```

---

## Working with Different Components

### gRPC Stubs (Proto Changes)

When you modify `.proto` files:

```bash
# 1. Edit proto file
vim grpc/grpc-stubs/src/main/proto/account/account_service.proto

# 2. Rebuild gRPC stubs
cd grpc
./gradlew clean build publishToMavenLocal

# 3. Rebuild libraries (depend on stubs)
cd ../libraries
./gradlew clean build publishToMavenLocal

# 4. Restart application to pick up changes
cd ../applications/account-manager
./gradlew quarkusDev
```

**For Node.js**:
```bash
# Sync proto files to Node
cd node/libraries/proto-files
pnpm run sync

# Regenerate TypeScript stubs
cd ../proto-stubs
pnpm run generate

# Restart web-proxy
cd ../../web-proxy
pnpm run dev
```

### Libraries (Shared Code)

When you modify a library:

```bash
# 1. Make changes to library
vim libraries/pipeline-commons/src/main/java/io/pipeline/commons/SomeClass.java

# 2. Rebuild and publish library
cd libraries
./gradlew :pipeline-commons:build :pipeline-commons:publishToMavenLocal

# 3. Restart dependent application
cd ../applications/account-manager
./gradlew quarkusDev  # Picks up new library from Maven Local
```

**Hot reload won't work for library changes** - you must restart the application.

### Applications

Standard development workflow:

```bash
cd applications/account-manager

# Run tests
./gradlew test

# Run integration tests
./gradlew integrationTest

# Build
./gradlew build

# Start dev mode
./gradlew quarkusDev

# Build Docker image
./gradlew build -Dquarkus.container-image.build=true
```

### Modules (Processing Services)

Same as applications:

```bash
cd modules/parser

./gradlew test
./gradlew build
./gradlew quarkusDev
```

### Node Applications

```bash
cd node/web-proxy

# Install dependencies
pnpm install

# Run in dev mode (hot reload)
pnpm run dev

# Build
pnpm run build

# Run production build
pnpm start

# Run tests
pnpm test
```

---

## Common Development Tasks

### Task: Add a New gRPC Service Method

**Example**: Add `GetAccountById` to account service.

```bash
# 1. Update proto
vim grpc/grpc-stubs/src/main/proto/account/account_service.proto
```

```protobuf
service AccountService {
  rpc CreateAccount(CreateAccountRequest) returns (CreateAccountResponse);
  rpc GetAccountById(GetAccountByIdRequest) returns (GetAccountByIdResponse);  // NEW
}

message GetAccountByIdRequest {
  string account_id = 1;
}

message GetAccountByIdResponse {
  Account account = 1;
}
```

```bash
# 2. Rebuild gRPC
cd grpc
./gradlew build publishToMavenLocal

# 3. Implement in application
vim applications/account-manager/src/main/java/io/pipeline/app/account/AccountGrpcService.java
```

```java
@Override
public Uni<GetAccountByIdResponse> getAccountById(GetAccountByIdRequest request) {
    return Uni.createFrom().item(() -> {
        Account account = accountService.getById(request.getAccountId());
        return GetAccountByIdResponse.newBuilder()
            .setAccount(toProto(account))
            .build();
    });
}
```

```bash
# 4. Test in dev mode
cd applications/account-manager
./gradlew quarkusDev

# 5. Test via grpcurl
grpcurl -plaintext -d '{"account_id":"123"}' \
  localhost:9000 \
  account.AccountService/GetAccountById
```

### Task: Add New REST Endpoint

```bash
cd applications/account-manager

# 1. Create/update resource class
vim src/main/java/io/pipeline/app/account/AccountResource.java
```

```java
@Path("/api/accounts")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class AccountResource {

    @Inject
    AccountService accountService;

    @GET
    @Path("/{id}")
    public Account getById(@PathParam("id") String id) {
        return accountService.getById(id);
    }
}
```

```bash
# 2. Start dev mode
./gradlew quarkusDev

# 3. Test via curl
curl http://localhost:8080/api/accounts/123

# Or use Swagger UI: http://localhost:8080/q/swagger-ui
```

### Task: Add Database Migration

```bash
cd applications/account-manager

# 1. Create migration file
mkdir -p src/main/resources/db/migration
vim src/main/resources/db/migration/V2__add_account_status.sql
```

```sql
ALTER TABLE accounts ADD COLUMN status VARCHAR(50) DEFAULT 'ACTIVE';
CREATE INDEX idx_account_status ON accounts(status);
```

```bash
# 2. Restart application (Flyway runs migration on startup)
./gradlew quarkusDev

# Check logs for:
# Flyway: Successfully applied 1 migration to schema `accountdb`
```

### Task: Update Frontend Component

```bash
cd applications/mapping-service/src/main/ui-vue

# 1. Edit component
vim src/components/MappingForm.vue

# 2. Vite auto-reloads in browser (if pnpm run dev is running)

# 3. Build for production
pnpm run build

# 4. Test in Quarkus
cd ../../..
./gradlew quarkusDev
# Access: http://localhost:8080
```

### Task: Debug with Breakpoints

**IntelliJ IDEA**:

1. Set breakpoint in code
2. Run configuration → Edit Configurations
3. Add new "Remote JVM Debug"
4. Port: 5005 (Quarkus default debug port)
5. Start app: `./gradlew quarkusDev`
6. Click Debug button in IntelliJ

**VS Code** (for Node.js):

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "node",
      "request": "launch",
      "name": "Debug web-proxy",
      "runtimeExecutable": "pnpm",
      "runtimeArgs": ["run", "dev"],
      "cwd": "${workspaceFolder}/node/web-proxy",
      "console": "integratedTerminal"
    }
  ]
}
```

---

## Troubleshooting

### Problem: "Could not find io.pipeline:grpc-stubs"

**Cause**: gRPC stubs not published to Maven Local.

**Solution**:
```bash
cd grpc
./gradlew clean publishToMavenLocal
```

### Problem: "Port already in use: 8080"

**Cause**: Another service is using port 8080.

**Solution 1** - Find and kill process:
```bash
lsof -i :8080
kill -9 <PID>
```

**Solution 2** - Change port:
```bash
# Edit src/main/resources/application.properties
quarkus.http.port=8081

# Or run with override
./gradlew quarkusDev -Dquarkus.http.port=8081
```

### Problem: "Cannot connect to database"

**Cause**: MySQL container not running.

**Solution**:
```bash
cd dev-infrastructure
docker compose -f compose-devservices.yml ps  # Check status
docker compose -f compose-devservices.yml up -d  # Start if stopped

# Check MySQL logs
docker compose -f compose-devservices.yml logs mysql
```

### Problem: Quarkus Dev Mode Stuck

**Solution**:
```bash
# Kill Quarkus process
# Press 'q' in terminal (graceful quit)
# Or Ctrl+C (force quit)

# If still stuck, find and kill Java process
ps aux | grep quarkus
kill -9 <PID>

# Clean build directory
./gradlew clean

# Restart
./gradlew quarkusDev
```

### Problem: Frontend Not Loading

**Cause**: Vite dev server not running or port conflict.

**Solution**:
```bash
cd node/web-proxy

# Check if running
lsof -i :37201

# Restart
pnpm run dev

# Check for errors in terminal
```

### Problem: Proto Files Out of Sync

**Cause**: Node proto files not synchronized with Java protos.

**Solution**:
```bash
cd node/libraries/proto-files
pnpm run sync

cd ../proto-stubs
pnpm run generate

# Restart web-proxy
cd ../../web-proxy
pnpm run dev
```

### Problem: Docker Out of Disk Space

**Solution**:
```bash
# Check Docker disk usage
docker system df

# Clean up
docker system prune -a --volumes

# Remove unused images
docker image prune -a

# Remove stopped containers
docker container prune
```

### Problem: Tests Failing with "Testcontainers timeout"

**Cause**: Docker not running or resource limits.

**Solution**:
```bash
# Verify Docker is running
docker ps

# Increase Docker resources (Docker Desktop → Settings → Resources)
# Memory: 8 GB minimum
# CPUs: 4 minimum

# Clean Docker
docker system prune -a
```

---

## IDE Configuration

### IntelliJ IDEA

**Recommended Plugins**:
- Quarkus Tools
- Protocol Buffers
- Lombok
- SonarLint
- GitToolBox

**Project Setup**:

1. **Import Project**:
   - File → Open → Select `pipeline-engine-refactor`
   - Import as Gradle project
   - Use Gradle wrapper
   - JDK: 21

2. **Configure Gradle**:
   - Settings → Build, Execution, Deployment → Build Tools → Gradle
   - Build and run using: IntelliJ IDEA (for better debugging)
   - Run tests using: Gradle (for Testcontainers support)

3. **Code Style**:
   - Settings → Editor → Code Style → Java
   - Import scheme from `config/intellij-code-style.xml` (if exists)

4. **Run Configurations**:
   - Quarkus Dev: `./gradlew quarkusDev`
   - Tests: Use Gradle task

### VS Code

**Recommended Extensions**:
- Volar (Vue.js)
- ESLint
- Prettier
- Proto3
- Docker
- GitLens

**Settings** (`.vscode/settings.json`):
```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "eslint.validate": ["javascript", "typescript", "vue"],
  "volar.takeOverMode.enabled": true
}
```

---

## Tips and Tricks

### Quick Commands

```bash
# Alias for common commands (add to ~/.bashrc or ~/.zshrc)
alias dev-start="cd dev-infrastructure && docker compose -f compose-devservices.yml up -d"
alias dev-stop="cd dev-infrastructure && docker compose -f compose-devservices.yml down"
alias dev-status="cd dev-infrastructure && docker compose -f compose-devservices.yml ps"

alias acc-dev="cd applications/account-manager && ./gradlew quarkusDev"
alias conn-dev="cd applications/connector-service && ./gradlew quarkusDev"
alias repo-dev="cd applications/repo-service && ./gradlew quarkusDev"
```

### Fast Iteration

**Skip tests during development build**:
```bash
./gradlew build -x test
```

**Continuous test execution** (auto-run on file change):
```bash
./gradlew test --continuous
```

**Quarkus continuous testing** (in dev mode):
```bash
./gradlew quarkusDev
# Then press 'r' to enable continuous testing
```

### Gradle Optimization

```bash
# Parallel builds
./gradlew build --parallel

# Offline mode (faster, uses cached deps)
./gradlew build --offline

# Build cache
./gradlew build --build-cache

# Daemon (faster builds, enabled by default)
./gradlew --status  # Check daemon status
```

### Docker Compose Shortcuts

```bash
# View logs for specific service
docker compose -f compose-devservices.yml logs -f mysql

# Restart specific service
docker compose -f compose-devservices.yml restart kafka

# Execute command in container
docker compose -f compose-devservices.yml exec mysql mysql -u root -p

# Check resource usage
docker stats
```

### Proto Development

**Watch proto changes and auto-rebuild**:
```bash
# Terminal 1: Watch proto files
cd node/libraries/proto-files
pnpm run watch  # Auto-syncs on changes

# Terminal 2: Watch for proto changes in Java
cd grpc
./gradlew build --continuous
```

### Database Tools

**Connect to MySQL in container**:
```bash
docker compose -f dev-infrastructure/compose-devservices.yml exec mysql \
  mysql -u root -proot

# Or use your favorite DB client:
# Host: localhost
# Port: 3306
# User: root
# Password: root
```

**View MinIO files**:
```bash
# MinIO Console: http://localhost:9001
# User: minioadmin
# Password: minioadmin
```

### Performance Profiling

**Quarkus startup time**:
```bash
./gradlew quarkusDev -Dquarkus.log.category."io.quarkus".level=DEBUG
# Check logs for startup timing
```

**JVM heap dump** (if memory issues):
```bash
jps  # Find Quarkus PID
jmap -dump:format=b,file=heap.bin <PID>
# Analyze with VisualVM or Eclipse MAT
```

---

## Environment Variables

### Common Configuration

```bash
# Set in your shell profile (~/.bashrc, ~/.zshrc)

# GitHub Packages (if not using gradle.properties)
export GITHUB_ACTOR=your-username
export GITHUB_TOKEN=your-token

# Docker
export DOCKER_HOST=unix:///var/run/docker.sock

# Java (if multiple versions)
export JAVA_HOME=/path/to/java21
export PATH=$JAVA_HOME/bin:$PATH

# Node (if using nvm)
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm use 22
```

### Application-Specific

```bash
# Override Quarkus config
export QUARKUS_DATASOURCE_JDBC_URL=jdbc:mysql://localhost:3306/custom_db
export QUARKUS_HTTP_PORT=8081

# Override gRPC port
export QUARKUS_GRPC_SERVER_PORT=9001
```

---

## Next Steps

After completing setup:

1. **Read Architecture Docs**: `docs/research/claude/build-restructuring-plan.md`
2. **Review Testing Strategy**: `docs/research/claude/testing-strategy.md`
3. **Explore a Service**: Start with `account-manager`
4. **Run Tests**: `./gradlew test`
5. **Make Your First Change**: Fix a bug or add a feature

---

## Getting Help

- **Documentation**: `docs/` directory
- **Code Examples**: Look at existing services as templates
- **Team**: Ask in Slack/Teams
- **Issues**: Check GitHub Issues for known problems

---

**Document Version**: 1.0
**Last Updated**: 2025-10-23
