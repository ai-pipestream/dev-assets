# CI/CD Workflows Guide

**Date**: 2025-10-23
**Purpose**: GitHub Actions workflows for independent builds and publishing

---

## Table of Contents

1. [Overview](#overview)
2. [Publishing Strategy](#publishing-strategy)
3. [Build Phases](#build-phases)
4. [Workflow Templates](#workflow-templates)
5. [Docker Registry Configuration](#docker-registry-configuration)
6. [Rollout Plan](#rollout-plan)

---

## Overview

### Goals

1. **Independent Builds**: Each component builds independently
2. **Artifact Publishing**: Maven artifacts to GitHub Packages, Docker images to configurable registry
3. **Path-Based Triggers**: Only build what changed
4. **No Forced Cascades**: Changing gRPC doesn't auto-trigger all downstream (optional later)
5. **Local-First Development**: Maven Local → GitHub Packages fallback

### Build Order

**Phase 1: Foundation** (must complete first)
1. gRPC stubs → Publish to GitHub Packages
2. Libraries → Publish to GitHub Packages

**Phase 2: Core Service** (foundational for all others)
3. platform-registration-service → Publish Docker image

**Phase 3: Applications & Modules** (can build in parallel)
4. All other applications
5. All modules

**Phase 4: Frontend**
6. Node shared libraries → Publish to GitHub Packages
7. web-proxy → Publish Docker image
8. platform-shell → Publish Docker image

---

## Publishing Strategy

### Maven Artifacts (GitHub Packages)

**What gets published**:
- `io.pipeline:grpc-stubs`
- `io.pipeline:grpc-wiremock`
- `io.pipeline:bom`
- All libraries in `libraries/`

**Repository Configuration**:
```gradle
// Maven Local FIRST, then GitHub Packages
repositories {
    mavenLocal()  // Check local first (fast dev)

    maven {
        name = "GitHubPackages"
        url = uri("https://maven.pkg.github.com/YOUR_ORG/pipeline-engine-refactor")
        credentials {
            username = System.getenv("GITHUB_ACTOR") ?: project.findProperty("gpr.user")
            password = System.getenv("GITHUB_TOKEN") ?: project.findProperty("gpr.token")
        }
    }

    mavenCentral()
}
```

**Publishing**:
```gradle
publishing {
    publications {
        maven(MavenPublication) {
            from components.java
        }
    }
    repositories {
        maven {
            name = "GitHubPackages"
            url = uri("https://maven.pkg.github.com/YOUR_ORG/pipeline-engine-refactor")
            credentials {
                username = System.getenv("GITHUB_ACTOR")
                password = System.getenv("GITHUB_TOKEN")
            }
        }
    }
}
```

### Docker Images

**Registry Options**:

1. **GitHub Container Registry (GHCR)** - Default for CI/CD
   - URL: `ghcr.io`
   - Authentication: GitHub token
   - Unlimited public images
   - Free for public repos

2. **Docker Hub** - Optional
   - URL: `docker.io`
   - Authentication: Docker Hub credentials
   - Rate limits: 200 pulls/6hrs (free tier)
   - Consideration: May hit limits with many services

3. **Local Registry** - For development only
   - Not pushed from CI/CD
   - Used for local testing

**Decision**: Start with GHCR, add Docker Hub as optional later

**Image Naming Convention**:
```
ghcr.io/YOUR_ORG/platform-registration-service:latest
ghcr.io/YOUR_ORG/platform-registration-service:1.0.0-SNAPSHOT
ghcr.io/YOUR_ORG/platform-registration-service:sha-abc123
```

---

## Build Phases

### Phase 1: gRPC Stubs

**Trigger**: Changes to `grpc/**`

**Workflow**: `.github/workflows/grpc-stubs.yml`

**Actions**:
1. Build gRPC stubs
2. Run tests
3. Publish to GitHub Packages (on main)

**Does NOT trigger**: Downstream services (they pull on-demand)

### Phase 2: Libraries

**Trigger**: Changes to `libraries/**` or `grpc/**`

**Workflow**: `.github/workflows/libraries.yml`

**Actions**:
1. Pull gRPC stubs from GitHub Packages
2. Build all libraries
3. Run tests
4. Publish to GitHub Packages (on main)

**Does NOT trigger**: Applications (they pull on-demand)

### Phase 3: platform-registration-service

**Trigger**: Changes to `applications/platform-registration-service/**`

**Workflow**: `.github/workflows/app-platform-registration-service.yml`

**Actions**:
1. Pull dependencies from GitHub Packages
2. Run unit tests
3. Run integration tests (Testcontainers)
4. Build Docker image
5. Push to GHCR (on main)

**Special**: This is the foundational service - all others depend on it at runtime

### Phase 4+: Other Services

Each service (applications + modules) gets its own workflow.

**All Applications**:
- account-manager
- connector-service
- repo-service
- opensearch-manager
- mapping-service
- linear-engine
- (future) connector-intake-service

**All Modules** (each is a container):
- parser
- chunker
- embedder
- echo

**Each follows same pattern**: Test → Build → Publish Docker image

### Phase 5: Node/Frontend

**After platform-registration-service is complete**

1. **Node Shared Libraries**: Publish to GitHub Packages
2. **web-proxy**: Build & publish Docker image
3. **platform-shell**: Build & publish Docker image

---

## Workflow Templates

### Template 1: gRPC Stubs

**File**: `.github/workflows/grpc-stubs.yml`

```yaml
name: gRPC Stubs

on:
  push:
    branches: [main, develop]
    paths:
      - 'grpc/**'
      - '.github/workflows/grpc-stubs.yml'
  pull_request:
    paths:
      - 'grpc/**'

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Java
        uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'
          cache: 'gradle'

      - name: Build and Test
        run: |
          cd grpc
          ./gradlew build test

      - name: Upload Test Results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: grpc-test-results
          path: grpc/*/build/test-results/**/*.xml

  publish:
    needs: build-and-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - name: Setup Java
        uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'

      - name: Publish to GitHub Packages
        run: |
          cd grpc
          ./gradlew publish
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Summary
        run: |
          echo "### gRPC Stubs Published ✅" >> $GITHUB_STEP_SUMMARY
          echo "Published artifacts:" >> $GITHUB_STEP_SUMMARY
          echo "- io.pipeline:grpc-stubs:1.0.0-SNAPSHOT" >> $GITHUB_STEP_SUMMARY
          echo "- io.pipeline:grpc-wiremock:1.0.0-SNAPSHOT" >> $GITHUB_STEP_SUMMARY
```

### Template 2: Libraries

**File**: `.github/workflows/libraries.yml`

```yaml
name: Libraries

on:
  push:
    branches: [main, develop]
    paths:
      - 'libraries/**'
      - 'grpc/**'
      - 'gradle/libs.versions.toml'
      - '.github/workflows/libraries.yml'
  pull_request:
    paths:
      - 'libraries/**'
      - 'grpc/**'
      - 'gradle/libs.versions.toml'

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Java
        uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'
          cache: 'gradle'

      - name: Configure GitHub Packages Access
        run: |
          mkdir -p ~/.gradle
          echo "gpr.user=${{ github.actor }}" >> ~/.gradle/gradle.properties
          echo "gpr.token=${{ secrets.GITHUB_TOKEN }}" >> ~/.gradle/gradle.properties

      # Build gRPC locally for dependency (faster than pulling from Packages)
      - name: Build gRPC Stubs (local dependency)
        run: |
          cd grpc
          ./gradlew publishToMavenLocal

      - name: Build Libraries
        run: |
          cd libraries
          ./gradlew build test
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Upload Test Results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: libraries-test-results
          path: libraries/*/build/test-results/**/*.xml

  publish:
    needs: build-and-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - name: Setup Java
        uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'

      - name: Configure GitHub Packages Access
        run: |
          mkdir -p ~/.gradle
          echo "gpr.user=${{ github.actor }}" >> ~/.gradle/gradle.properties
          echo "gpr.token=${{ secrets.GITHUB_TOKEN }}" >> ~/.gradle/gradle.properties

      - name: Build gRPC Stubs
        run: |
          cd grpc
          ./gradlew publishToMavenLocal

      - name: Publish Libraries to GitHub Packages
        run: |
          cd libraries
          ./gradlew publish
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Summary
        run: |
          echo "### Libraries Published ✅" >> $GITHUB_STEP_SUMMARY
          echo "Published artifacts:" >> $GITHUB_STEP_SUMMARY
          echo "- io.pipeline:bom:1.0.0-SNAPSHOT" >> $GITHUB_STEP_SUMMARY
          echo "- io.pipeline:pipeline-api:1.0.0-SNAPSHOT" >> $GITHUB_STEP_SUMMARY
          echo "- io.pipeline:pipeline-commons:1.0.0-SNAPSHOT" >> $GITHUB_STEP_SUMMARY
          echo "- io.pipeline:data-util:1.0.0-SNAPSHOT" >> $GITHUB_STEP_SUMMARY
          echo "- io.pipeline:dynamic-grpc:1.0.0-SNAPSHOT" >> $GITHUB_STEP_SUMMARY
          echo "- io.pipeline:dynamic-grpc-registration-clients:1.0.0-SNAPSHOT" >> $GITHUB_STEP_SUMMARY
          echo "- io.pipeline:testing-utils:1.0.0-SNAPSHOT" >> $GITHUB_STEP_SUMMARY
```

### Template 3: platform-registration-service (Docker)

**File**: `.github/workflows/app-platform-registration-service.yml`

```yaml
name: Platform Registration Service

on:
  push:
    branches: [main, develop]
    paths:
      - 'applications/platform-registration-service/**'
      - 'grpc/**'
      - 'libraries/**'
      - '.github/workflows/app-platform-registration-service.yml'
  pull_request:
    paths:
      - 'applications/platform-registration-service/**'
      - 'grpc/**'
      - 'libraries/**'

env:
  SERVICE_NAME: platform-registration-service
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository_owner }}/platform-registration-service

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Java
        uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'
          cache: 'gradle'

      - name: Configure GitHub Packages Access
        run: |
          mkdir -p ~/.gradle
          echo "gpr.user=${{ github.actor }}" >> ~/.gradle/gradle.properties
          echo "gpr.token=${{ secrets.GITHUB_TOKEN }}" >> ~/.gradle/gradle.properties

      - name: Run Unit Tests
        run: |
          cd applications/platform-registration-service
          ./gradlew test
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Run Integration Tests
        run: |
          cd applications/platform-registration-service
          ./gradlew integrationTest
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Upload Test Results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: applications/platform-registration-service/build/test-results/**/*.xml

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Java
        uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'

      - name: Configure GitHub Packages Access
        run: |
          mkdir -p ~/.gradle
          echo "gpr.user=${{ github.actor }}" >> ~/.gradle/gradle.properties
          echo "gpr.token=${{ secrets.GITHUB_TOKEN }}" >> ~/.gradle/gradle.properties

      - name: Build Application
        run: |
          cd applications/platform-registration-service
          ./gradlew build -x test
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Build Docker Image (Local)
        run: |
          cd applications/platform-registration-service
          ./gradlew build \
            -Dquarkus.container-image.build=true \
            -Dquarkus.container-image.registry=${{ env.REGISTRY }} \
            -Dquarkus.container-image.group=${{ github.repository_owner }} \
            -Dquarkus.container-image.name=${{ env.SERVICE_NAME }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  publish-image:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - name: Setup Java
        uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'

      - name: Configure GitHub Packages Access
        run: |
          mkdir -p ~/.gradle
          echo "gpr.user=${{ github.actor }}" >> ~/.gradle/gradle.properties
          echo "gpr.token=${{ secrets.GITHUB_TOKEN }}" >> ~/.gradle/gradle.properties

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and Push Docker Image
        run: |
          cd applications/platform-registration-service
          ./gradlew build \
            -Dquarkus.container-image.push=true \
            -Dquarkus.container-image.registry=${{ env.REGISTRY }} \
            -Dquarkus.container-image.group=${{ github.repository_owner }} \
            -Dquarkus.container-image.name=${{ env.SERVICE_NAME }} \
            -Dquarkus.container-image.tag=latest \
            -Dquarkus.container-image.additional-tags=${{ github.sha }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Summary
        run: |
          echo "### Docker Image Published ✅" >> $GITHUB_STEP_SUMMARY
          echo "Image: \`${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest\`" >> $GITHUB_STEP_SUMMARY
          echo "Tags:" >> $GITHUB_STEP_SUMMARY
          echo "- \`latest\`" >> $GITHUB_STEP_SUMMARY
          echo "- \`${{ github.sha }}\`" >> $GITHUB_STEP_SUMMARY
```

### Template 4: Generic Application/Module

**File**: `.github/workflows/app-account-manager.yml` (example)

```yaml
name: Account Manager

on:
  push:
    branches: [main, develop]
    paths:
      - 'applications/account-manager/**'
      - '.github/workflows/app-account-manager.yml'
  pull_request:
    paths:
      - 'applications/account-manager/**'

env:
  SERVICE_NAME: account-manager
  REGISTRY: ghcr.io

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'
          cache: 'gradle'

      - name: Configure GitHub Packages
        run: |
          mkdir -p ~/.gradle
          echo "gpr.user=${{ github.actor }}" >> ~/.gradle/gradle.properties
          echo "gpr.token=${{ secrets.GITHUB_TOKEN }}" >> ~/.gradle/gradle.properties

      - name: Run Tests
        run: |
          cd applications/account-manager
          ./gradlew test integrationTest
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  build-image:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and Push
        run: |
          cd applications/account-manager
          ./gradlew build \
            -Dquarkus.container-image.push=true \
            -Dquarkus.container-image.registry=${{ env.REGISTRY }} \
            -Dquarkus.container-image.group=${{ github.repository_owner }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## Docker Registry Configuration

### GitHub Container Registry (GHCR)

**Advantages**:
- Free for public images
- Tight GitHub integration
- No rate limits
- Easy authentication with GitHub token

**Setup**:

1. **Enable GHCR** (automatic for public repos)

2. **Quarkus Configuration**:
```properties
# src/main/resources/application.properties
quarkus.container-image.builder=docker
quarkus.container-image.registry=ghcr.io
quarkus.container-image.group=${CONTAINER_GROUP:YOUR_ORG}
quarkus.container-image.name=platform-registration-service
quarkus.container-image.tag=${quarkus.application.version}
```

3. **Build and Push**:
```bash
# Local (for testing)
./gradlew build \
  -Dquarkus.container-image.build=true

# CI/CD (push to registry)
./gradlew build \
  -Dquarkus.container-image.push=true \
  -Dquarkus.container-image.username=$GITHUB_ACTOR \
  -Dquarkus.container-image.password=$GITHUB_TOKEN
```

### Docker Hub (Optional Future)

**For when you want public discoverability**:

```yaml
# Add to workflow
- name: Login to Docker Hub
  uses: docker/login-action@v3
  with:
    username: ${{ secrets.DOCKERHUB_USERNAME }}
    password: ${{ secrets.DOCKERHUB_TOKEN }}

- name: Push to Docker Hub
  run: |
    docker tag ghcr.io/${{ github.repository_owner }}/platform-registration-service:latest \
      ${{ secrets.DOCKERHUB_USERNAME }}/platform-registration-service:latest
    docker push ${{ secrets.DOCKERHUB_USERNAME }}/platform-registration-service:latest
```

### Local Registry (Development Only)

**Not pushed from CI/CD, only for local testing**:

```bash
# Build locally without pushing
cd applications/platform-registration-service
./gradlew build -Dquarkus.container-image.build=true

# Tag for local registry (optional)
docker tag platform-registration-service:1.0.0-SNAPSHOT localhost:5000/platform-registration-service:latest
docker push localhost:5000/platform-registration-service:latest
```

---

## Rollout Plan

### Phase 1: Foundation (Week 1)

**Goal**: Get gRPC and libraries publishing to GitHub Packages

1. **Day 1-2: gRPC Stubs**
   - Create workflow: `grpc-stubs.yml`
   - Test PR trigger
   - Test publish to GitHub Packages
   - Verify artifacts are downloadable

2. **Day 3-4: Libraries**
   - Restructure libraries build (separate from root)
   - Create workflow: `libraries.yml`
   - Test dependency resolution (Maven Local → GitHub Packages)
   - Verify all libraries publish

3. **Day 5: Validation**
   - Test clean build from scratch (no Maven Local)
   - Ensure artifacts pull from GitHub Packages
   - Document any issues

### Phase 2: Core Service (Week 2)

**Goal**: Get platform-registration-service building and publishing Docker image

1. **Day 1-2: Independent Build Setup**
   - Create `applications/platform-registration-service/settings.gradle`
   - Update `build.gradle` to use GitHub Packages
   - Add Gradle wrapper
   - Test local build

2. **Day 3: Testcontainers**
   - Set up Consul Testcontainer for integration tests
   - Write integration tests
   - Verify tests pass in CI

3. **Day 4: Docker Build**
   - Configure Quarkus container image
   - Test Docker build locally
   - Test push to GHCR locally

4. **Day 5: CI/CD Workflow**
   - Create workflow: `app-platform-registration-service.yml`
   - Test PR trigger
   - Test Docker push to GHCR on main
   - Verify image is pullable

### Phase 3: Remaining Services (Weeks 3-4)

**Goal**: Migrate all other applications and modules

**Applications** (1-2 per day):
- account-manager
- connector-service
- repo-service
- opensearch-manager
- mapping-service
- linear-engine

**Modules** (1-2 per day):
- parser
- chunker
- embedder
- echo

**For each**:
1. Create independent build
2. Set up Testcontainers
3. Create CI/CD workflow
4. Test and validate

### Phase 4: Frontend (Week 5)

**Goal**: Node shared libraries + web-proxy + platform-shell

1. **Node Shared Libraries**
   - Publish to GitHub Packages (npm)
   - Update dependents to pull from Packages

2. **web-proxy**
   - Create Dockerfile
   - Create CI/CD workflow
   - Publish to GHCR

3. **platform-shell**
   - Create Dockerfile
   - Create CI/CD workflow
   - Publish to GHCR

---

## Success Criteria

- [ ] All gRPC artifacts publish to GitHub Packages automatically
- [ ] All libraries publish to GitHub Packages automatically
- [ ] platform-registration-service Docker image builds and publishes
- [ ] All other services have independent CI/CD workflows
- [ ] PRs trigger tests for affected components only
- [ ] Main branch merges trigger publishing
- [ ] Docker images are tagged with both `latest` and commit SHA
- [ ] Artifacts are consumable by downstream projects

---

**Document Version**: 1.0
**Last Updated**: 2025-10-23
