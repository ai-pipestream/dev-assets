# Pipeline Engine Build Restructuring Plan

**Date**: 2025-10-23
**Goal**: Transform the current monolithic Gradle build into independent, CI/CD-ready builds while maintaining mono-repo benefits

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Problems with Current Build](#problems-with-current-build)
3. [Proposed Architecture](#proposed-architecture)
4. [Step-by-Step Migration Plan](#step-by-step-migration-plan)
5. [GitHub Packages Setup](#github-packages-setup)
6. [CI/CD Pipeline Configuration](#cicd-pipeline-configuration)
7. [Local Development Workflow](#local-development-workflow)
8. [Testing Strategy](#testing-strategy)
9. [Node/Frontend Strategy](#nodefrontend-strategy)
10. [Rollout Schedule](#rollout-schedule)

---

## Current State Analysis

### Build Components

The current build consists of several interconnected parts:

```
pipeline-engine-refactor/
├── grpc/                    # Separate Gradle build
│   ├── grpc-stubs/         # Proto definitions + generated Java/gRPC code
│   └── grpc-wiremock/      # WireMock utilities for testing
├── bom/                     # Bill of Materials (dependency versions)
├── libraries/               # Shared Java libraries
│   ├── pipeline-api/
│   ├── pipeline-commons/
│   ├── data-util/
│   ├── dynamic-grpc/
│   ├── dynamic-grpc-registration-clients/
│   └── testing-utils/
├── applications/            # Quarkus microservices
│   ├── account-manager/
│   ├── connector-service/
│   ├── repo-service/
│   ├── mapping-service/
│   ├── opensearch-manager/
│   ├── linear-engine/
│   ├── platform-registration-service/
│   └── node/               # Node.js applications
│       ├── web-proxy/
│       ├── platform-shell/
│       └── libraries/
├── modules/                 # Processing microservices
│   ├── parser/
│   ├── chunker/
│   ├── embedder/
│   └── echo/
└── src/test/resources/     # Shared dev infrastructure
    └── compose-devservices.yml
```

### Current Build Order

From `BUILD_ORDER.md`:

1. **Proto files** (already exist in `grpc/grpc-stubs/src/main/proto/`)
2. **Node proto stubs** (`pnpm install` triggers proto sync)
3. **gRPC stubs** (Java) → `publishToMavenLocal`
4. **BOM** → `publishToMavenLocal`
5. **Java libraries** → `publishToMavenLocal` (each one)
6. **Main Java build** (`./gradlew build`)
7. **Infrastructure** (`docker compose up`)

### Dependency Graph

```
grpc-stubs
    ├─→ grpc-wiremock
    ├─→ bom
    ├─→ pipeline-commons
    └─→ pipeline-api
        └─→ pipeline-commons

libraries (all depend on grpc-stubs + bom)
    ├─→ pipeline-api
    ├─→ pipeline-commons
    ├─→ data-util
    ├─→ dynamic-grpc
    └─→ dynamic-grpc-registration-clients

applications (depend on libraries + grpc-stubs)
    ├─→ account-manager (MySQL, registration-service)
    ├─→ connector-service (account-manager, kafka)
    ├─→ repo-service (MinIO, many services)
    ├─→ mapping-service (embedded Vue)
    ├─→ opensearch-manager (Kafka, Apicurio, OpenSearch)
    ├─→ linear-engine
    └─→ platform-registration-service (Consul)

modules (depend on libraries + grpc-stubs)
    ├─→ parser
    ├─→ chunker
    ├─→ embedder
    └─→ echo

node
    ├─→ web-proxy (syncs protos from grpc/grpc-stubs)
    ├─→ platform-shell (uses Traefik for routing)
    └─→ libraries (proto-stubs, shared-components, etc.)
```

---

## Problems with Current Build

### 1. **Heavy Interdependency**
- All projects must be built together
- Changing one library triggers rebuilds of everything
- Full build is slow and heavyweight

### 2. **Complex Setup for New Developers**
- Multi-step build process (7+ steps)
- Easy to get out of sync with Maven Local
- Chicken-and-egg problems (which came first?)

### 3. **No CI/CD**
- No automated testing on pull requests
- No artifact publishing
- Manual deployment process

### 4. **Testing Issues**
- Shared `compose-devservices.yml` causes test drift
- Integration tests are brittle (interdependent services)
- Difficult to test services in isolation
- Hard for LLMs to maintain tests

### 5. **Versioning Chaos**
- Everything is `1.0.0-SNAPSHOT`
- No way to track which version of library works with which app
- Breaking changes in libraries affect everything

### 6. **Proto Sync Complexity**
- Node projects manually sync proto files
- Easy to get out of sync
- No automated validation

---

## Proposed Architecture

### Design Principle: "Independently Buildable, Collectively Coherent"

**Keep mono-repo** to maintain proto/API contract coherence, but **make each component independently buildable and testable**.

### New Directory Structure

```
pipeline-engine-refactor/  (single repo)
│
├── .github/
│   └── workflows/
│       ├── grpc-stubs.yml              # CI for gRPC layer
│       ├── libraries.yml               # CI for shared libraries
│       ├── app-account-manager.yml     # Independent app CI
│       ├── app-connector.yml
│       ├── app-repo-service.yml
│       ├── module-parser.yml           # Independent module CI
│       ├── module-chunker.yml
│       ├── web-proxy.yml               # Node.js CI
│       └── e2e-integration.yml         # Optional full integration
│
├── grpc/                               # Separate Gradle build (unchanged)
│   ├── build.gradle
│   ├── settings.gradle
│   ├── grpc-stubs/
│   └── grpc-wiremock/
│
├── libraries/                          # NEW: Separate Gradle build
│   ├── build.gradle                    # Root build for libraries
│   ├── settings.gradle                 # Multi-project settings
│   ├── bom/                            # Moved from root
│   ├── pipeline-api/
│   ├── pipeline-commons/
│   ├── data-util/
│   ├── dynamic-grpc/
│   ├── dynamic-grpc-registration-clients/
│   └── testing-utils/
│
├── applications/
│   ├── account-manager/                # Independent Gradle build
│   │   ├── build.gradle
│   │   ├── settings.gradle             # Single-project settings
│   │   ├── src/
│   │   ├── .github/                    # Optional: app-specific workflows
│   │   └── README.md
│   ├── connector-service/              # Independent Gradle build
│   │   ├── build.gradle
│   │   ├── settings.gradle
│   │   └── src/
│   ├── repo-service/
│   ├── mapping-service/
│   ├── opensearch-manager/
│   ├── linear-engine/
│   └── platform-registration-service/
│
├── modules/
│   ├── parser/                         # Independent Gradle build
│   │   ├── build.gradle
│   │   ├── settings.gradle
│   │   └── src/
│   ├── chunker/
│   ├── embedder/
│   └── echo/
│
├── node/                               # Moved from applications/node
│   ├── pnpm-workspace.yaml
│   ├── web-proxy/
│   ├── platform-shell/
│   ├── dev-tools/
│   └── libraries/
│       ├── proto-files/                # Syncs from grpc/grpc-stubs
│       ├── proto-stubs/
│       ├── protobuf-forms/
│       ├── shared-components/
│       └── shared-nav/
│
├── dev-infrastructure/                 # NEW: Shared dev environment
│   ├── compose-devservices.yml         # Moved from src/test/resources
│   ├── scripts/
│   │   ├── setup-local-dev.sh
│   │   ├── start-dev-services.sh
│   │   └── stop-dev-services.sh
│   └── README.md
│
├── docs/
│   └── research/claude/
│       └── build-restructuring-plan.md (this file)
│
├── scripts/                            # Root-level utility scripts
│   ├── publish-all-local.sh
│   └── validate-proto-sync.sh
│
└── README.md                           # Updated root README
```

### Key Architectural Changes

#### 1. **Independent Gradle Builds**

Each application/module becomes a **standalone Gradle project**:

```gradle
// applications/account-manager/settings.gradle
rootProject.name = 'account-manager'

dependencyResolutionManagement {
    repositories {
        // GitHub Packages for published artifacts
        maven {
            name = "GitHubPackages"
            url = uri("https://maven.pkg.github.com/YOUR_ORG/pipeline-engine-refactor")
            credentials {
                username = System.getenv("GITHUB_ACTOR") ?: project.findProperty("gpr.user")
                password = System.getenv("GITHUB_TOKEN") ?: project.findProperty("gpr.token")
            }
        }
        // Maven Local for local development
        mavenLocal()
        mavenCentral()
    }
}
```

```gradle
// applications/account-manager/build.gradle
plugins {
    id 'java'
    id 'io.quarkus' version '3.28.4'
}

group = 'io.pipeline.app'
version = '1.0.0-SNAPSHOT'

dependencies {
    // Published dependencies from GitHub Packages (or Maven Local)
    implementation platform('io.pipeline:bom:1.0.0-SNAPSHOT')
    implementation 'io.pipeline:grpc-stubs:1.0.0-SNAPSHOT'
    implementation 'io.pipeline:pipeline-commons:1.0.0-SNAPSHOT'
    implementation 'io.pipeline:dynamic-grpc:1.0.0-SNAPSHOT'
    implementation 'io.pipeline:dynamic-grpc-registration-clients:1.0.0-SNAPSHOT'

    // Quarkus dependencies (versions from BOM)
    implementation 'io.quarkus:quarkus-grpc'
    implementation 'io.quarkus:quarkus-hibernate-orm-panache'
    implementation 'io.quarkus:quarkus-rest'
    implementation 'io.quarkus:quarkus-jdbc-mysql'
    // ... etc

    // Testing
    testImplementation 'io.quarkus:quarkus-junit5'
    testImplementation 'org.testcontainers:mysql:1.21.3'
    testImplementation 'io.pipeline:grpc-wiremock:1.0.0-SNAPSHOT'
}

java {
    sourceCompatibility = JavaVersion.VERSION_21
    targetCompatibility = JavaVersion.VERSION_21
}

test {
    systemProperty "java.util.logging.manager", "org.jboss.logmanager.LogManager"
    useJUnitPlatform()
}
```

#### 2. **Libraries as Separate Build**

```gradle
// libraries/settings.gradle
rootProject.name = 'pipeline-libraries'

// Include BOM first
include 'bom'

// Include all library projects
include 'pipeline-api'
include 'pipeline-commons'
include 'data-util'
include 'dynamic-grpc'
include 'dynamic-grpc-registration-clients'
include 'testing-utils'
```

```gradle
// libraries/build.gradle
plugins {
    id 'base'
}

allprojects {
    group = 'io.pipeline'
    version = '1.0.0-SNAPSHOT'

    repositories {
        maven {
            name = "GitHubPackages"
            url = uri("https://maven.pkg.github.com/YOUR_ORG/pipeline-engine-refactor")
            credentials {
                username = System.getenv("GITHUB_ACTOR") ?: project.findProperty("gpr.user")
                password = System.getenv("GITHUB_TOKEN") ?: project.findProperty("gpr.token")
            }
        }
        mavenLocal()
        mavenCentral()
    }
}

subprojects {
    apply plugin: 'java-library'
    apply plugin: 'maven-publish'

    java {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
    }

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
}
```

#### 3. **Path-Based CI/CD Triggers**

Each component has its own GitHub Actions workflow that triggers only when relevant files change:

```yaml
# .github/workflows/app-account-manager.yml
name: Account Manager

on:
  push:
    branches: [main, develop]
    paths:
      - 'applications/account-manager/**'
      - 'grpc/**'                    # Rebuild if protos change
      - 'libraries/**'               # Rebuild if libraries change
      - '.github/workflows/app-account-manager.yml'
  pull_request:
    paths:
      - 'applications/account-manager/**'
      - 'grpc/**'
      - 'libraries/**'

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
          ./gradlew test
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Build Docker Image
        run: |
          cd applications/account-manager
          ./gradlew build -Dquarkus.container-image.build=true

  publish:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'

      - name: Build and Push Docker Image
        run: |
          cd applications/account-manager
          ./gradlew build \
            -Dquarkus.container-image.push=true \
            -Dquarkus.container-image.registry=ghcr.io \
            -Dquarkus.container-image.group=${{ github.repository_owner }} \
            -Dquarkus.container-image.username=${{ github.actor }} \
            -Dquarkus.container-image.password=${{ secrets.GITHUB_TOKEN }}
```

---

## Step-by-Step Migration Plan

### Phase 0: Preparation (1-2 hours)

**Goal**: Set up GitHub Packages and validate current build

#### Tasks:

1. **Enable GitHub Packages**
   - Go to repository Settings → Actions → General
   - Under "Workflow permissions", select "Read and write permissions"
   - Enable "Allow GitHub Actions to create and approve pull requests"

2. **Create GitHub Personal Access Token (for local dev)**
   - Go to Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Generate new token with scopes: `read:packages`, `write:packages`
   - Save token securely (add to password manager)

3. **Configure local Gradle properties**
   ```bash
   # Create or edit ~/.gradle/gradle.properties
   echo "gpr.user=YOUR_GITHUB_USERNAME" >> ~/.gradle/gradle.properties
   echo "gpr.token=YOUR_GITHUB_TOKEN" >> ~/.gradle/gradle.properties
   ```

4. **Baseline test - verify current build works**
   ```bash
   # Full clean build from scratch
   ./gradlew clean
   cd grpc && ./gradlew clean build publishToMavenLocal && cd ..
   ./gradlew :bom:publishToMavenLocal
   ./gradlew build
   ```

5. **Create feature branch**
   ```bash
   git checkout -b feature/build-restructure
   ```

---

### Phase 1: Restructure Libraries (2-3 hours)

**Goal**: Move BOM and libraries into a separate Gradle build

#### Step 1.1: Create libraries build structure

```bash
cd /home/krickert/IdeaProjects/pipeline-engine-refactor

# Create new libraries build root
mkdir -p libraries-new
```

#### Step 1.2: Create libraries/settings.gradle

```bash
cat > libraries-new/settings.gradle << 'EOF'
rootProject.name = 'pipeline-libraries'

// Import version catalog from parent repo
dependencyResolutionManagement {
    versionCatalogs {
        libs {
            from(files("../gradle/libs.versions.toml"))
        }
    }
}

include 'bom'
include 'pipeline-api'
include 'pipeline-commons'
include 'data-util'
include 'dynamic-grpc'
include 'dynamic-grpc-registration-clients'
include 'testing-utils'
EOF
```

#### Step 1.3: Create libraries/build.gradle

```bash
cat > libraries-new/build.gradle << 'EOF'
plugins {
    id 'base'
}

allprojects {
    group = 'io.pipeline'
    version = '1.0.0-SNAPSHOT'

    repositories {
        // GitHub Packages for dependencies
        maven {
            name = "GitHubPackages"
            url = uri("https://maven.pkg.github.com/YOUR_ORG/pipeline-engine-refactor")
            credentials {
                username = System.getenv("GITHUB_ACTOR") ?: project.findProperty("gpr.user")
                password = System.getenv("GITHUB_TOKEN") ?: project.findProperty("gpr.token")
            }
        }
        // Maven Local for grpc-stubs during local dev
        mavenLocal()

        // Sonatype for Quarkus early releases
        maven {
            url uri('https://s01.oss.sonatype.org/content/groups/public/')
            content {
                includeGroupByRegex 'io\\.quarkus(\\..*)?'
                includeGroup 'io.quarkus.platform'
            }
        }
        mavenCentral()

        // Apache snapshots for Tika
        maven {
            url "https://repository.apache.org/content/repositories/snapshots/"
            content {
                includeGroup "org.apache.tika"
            }
            mavenContent {
                snapshotsOnly()
            }
        }
    }
}

subprojects {
    pluginManager.withPlugin('java') {
        java {
            sourceCompatibility = JavaVersion.VERSION_21
            targetCompatibility = JavaVersion.VERSION_21
        }

        tasks.withType(JavaCompile) {
            options.encoding = 'UTF-8'
            options.compilerArgs << '-parameters'
        }

        test {
            systemProperty "java.util.logging.manager", "org.jboss.logmanager.LogManager"
            useJUnitPlatform()
        }
    }

    pluginManager.withPlugin('maven-publish') {
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
                        username = System.getenv("GITHUB_ACTOR") ?: project.findProperty("gpr.user")
                        password = System.getenv("GITHUB_TOKEN") ?: project.findProperty("gpr.token")
                    }
                }
            }
        }

        tasks.withType(GenerateModuleMetadata) {
            suppressedValidationErrors.add('enforced-platform')
        }
    }
}
EOF
```

#### Step 1.4: Move library projects

```bash
# Move BOM
mv bom libraries-new/

# Move libraries
mv libraries/pipeline-api libraries-new/
mv libraries/pipeline-commons libraries-new/
mv libraries/data-util libraries-new/
mv libraries/dynamic-grpc libraries-new/
mv libraries/dynamic-grpc-registration-clients libraries-new/
mv libraries/testing-utils libraries-new/

# Remove old libraries directory
rmdir libraries

# Rename libraries-new to libraries
mv libraries-new libraries
```

#### Step 1.5: Update library build.gradle files

Each library needs to be updated to remove root project dependencies:

```bash
# Example: Update pipeline-commons/build.gradle
cat > libraries/pipeline-commons/build.gradle << 'EOF'
plugins {
    id 'java-library'
    alias(libs.plugins.quarkus)
    alias(libs.plugins.jandex)
    id 'maven-publish'
}

dependencies {
    // Get grpc-stubs from Maven Local or GitHub Packages
    implementation 'io.pipeline:grpc-stubs:1.0.0-SNAPSHOT'
    implementation 'io.pipeline:grpc-wiremock:1.0.0-SNAPSHOT'

    // Use BOM from this multi-project build
    implementation platform(project(':bom'))

    // Quarkus dependencies
    implementation libs.bundles.quarkus.common
    implementation libs.quarkus.jackson
    implementation 'io.quarkus:quarkus-smallrye-openapi'

    // Protobuf
    api libs.protobuf.java

    // Depend on pipeline-api from this build
    implementation project(':pipeline-api')

    // Testing
    testImplementation libs.quarkus.junit5
    testImplementation libs.jimfs
    implementation libs.memoryfilesystem
}

publishing {
    publications {
        maven(MavenPublication) {
            pom {
                name = 'Pipeline Commons'
                description = 'Shared utilities and gRPC client interfaces used across services and tests'
            }
        }
    }
}
EOF
```

Repeat similar updates for other libraries (adjust dependencies as needed).

#### Step 1.6: Test libraries build

```bash
cd libraries
./gradlew clean build
./gradlew publishToMavenLocal
cd ..
```

#### Step 1.7: Create libraries CI workflow

```bash
mkdir -p .github/workflows
cat > .github/workflows/libraries.yml << 'EOF'
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

      # Build gRPC stubs first (needed by libraries)
      - name: Build gRPC Stubs
        run: |
          cd grpc
          ./gradlew build publishToMavenLocal
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Build Libraries
        run: |
          cd libraries
          ./gradlew build
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Run Tests
        run: |
          cd libraries
          ./gradlew test

  publish:
    needs: build-and-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'

      - name: Configure GitHub Packages
        run: |
          mkdir -p ~/.gradle
          echo "gpr.user=${{ github.actor }}" >> ~/.gradle/gradle.properties
          echo "gpr.token=${{ secrets.GITHUB_TOKEN }}" >> ~/.gradle/gradle.properties

      - name: Build gRPC Stubs
        run: |
          cd grpc
          ./gradlew build publishToMavenLocal
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Publish Libraries to GitHub Packages
        run: |
          cd libraries
          ./gradlew publish
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
EOF
```

---

### Phase 2: Create Independent Application Build (Proof of Concept) (2-3 hours)

**Goal**: Convert `account-manager` to independent build as proof of concept

#### Step 2.1: Create account-manager/settings.gradle

```bash
cat > applications/account-manager/settings.gradle << 'EOF'
rootProject.name = 'account-manager'

dependencyResolutionManagement {
    repositories {
        // GitHub Packages for published artifacts
        maven {
            name = "GitHubPackages"
            url = uri("https://maven.pkg.github.com/YOUR_ORG/pipeline-engine-refactor")
            credentials {
                username = System.getenv("GITHUB_ACTOR") ?: project.findProperty("gpr.user")
                password = System.getenv("GITHUB_TOKEN") ?: project.findProperty("gpr.token")
            }
        }

        // Maven Local for local development
        mavenLocal()

        // Sonatype for Quarkus
        maven {
            url uri('https://s01.oss.sonatype.org/content/groups/public/')
            content {
                includeGroupByRegex 'io\\.quarkus(\\..*)?'
                includeGroup 'io.quarkus.platform'
            }
        }

        mavenCentral()
    }

    versionCatalogs {
        libs {
            from(files("../../gradle/libs.versions.toml"))
        }
    }
}
EOF
```

#### Step 2.2: Update account-manager/build.gradle

```bash
cat > applications/account-manager/build.gradle << 'EOF'
plugins {
    id 'java'
    alias(libs.plugins.quarkus)
}

group = 'io.pipeline.app'
version = '1.0.0-SNAPSHOT'

dependencies {
    // Use published BOM and libraries
    implementation platform('io.pipeline:bom:1.0.0-SNAPSHOT')
    implementation enforcedPlatform(libs.quarkus.amazon.services.bom)

    // Core Quarkus dependencies
    implementation 'io.quarkus:quarkus-hibernate-orm-panache'
    implementation 'io.quarkus:quarkus-rest'
    implementation 'io.quarkus:quarkus-smallrye-health'
    implementation 'io.quarkus:quarkus-jdbc-mysql'
    implementation 'io.quarkus:quarkus-arc'
    implementation 'io.quarkus:quarkus-flyway'
    implementation 'org.flywaydb:flyway-mysql'
    implementation 'io.quarkus:quarkus-smallrye-openapi'
    implementation 'io.quarkus:quarkus-grpc'
    implementation 'io.quarkus:quarkus-smallrye-stork'

    // S3 Client
    implementation 'io.quarkiverse.amazonservices:quarkus-amazon-s3'
    implementation libs.aws.sdk.url.connection
    implementation libs.aws.sdk.netty.nio

    // Quinoa for Vue.js frontend
    implementation libs.quarkus.quinoa

    // Service Discovery
    implementation 'io.smallrye.stork:stork-service-discovery-consul'
    implementation 'io.smallrye.reactive:smallrye-mutiny-vertx-consul-client'
    implementation 'io.smallrye.stork:stork-service-registration-consul'

    // Published pipeline dependencies
    implementation 'io.pipeline:grpc-stubs:1.0.0-SNAPSHOT'
    implementation 'io.pipeline:dynamic-grpc-registration-clients:1.0.0-SNAPSHOT'
    implementation 'io.pipeline:dynamic-grpc:1.0.0-SNAPSHOT'

    // Test dependencies
    testImplementation 'io.quarkus:quarkus-junit5'
    testImplementation 'org.testcontainers:mysql:1.21.3'
    testImplementation 'io.pipeline:grpc-wiremock:1.0.0-SNAPSHOT'
}

java {
    sourceCompatibility = JavaVersion.VERSION_21
    targetCompatibility = JavaVersion.VERSION_21
}

tasks.withType(JavaCompile) {
    options.encoding = 'UTF-8'
    options.compilerArgs << '-parameters'
}

test {
    systemProperty "java.util.logging.manager", "org.jboss.logmanager.LogManager"
    useJUnitPlatform()
}

// Quarkus container image configuration
quarkus {
    containerImage {
        registry = System.getenv("CONTAINER_REGISTRY") ?: "ghcr.io"
        group = System.getenv("CONTAINER_GROUP") ?: "YOUR_ORG"
        name = "account-manager"
        tag = version
    }
}
EOF
```

#### Step 2.3: Add Gradle wrapper to account-manager

```bash
cd applications/account-manager
gradle wrapper --gradle-version 8.11
cd ../..
```

#### Step 2.4: Test independent build

```bash
cd applications/account-manager

# Test build (will pull from Maven Local)
./gradlew build

# Test running in dev mode
./gradlew quarkusDev
# Press 'q' to quit

cd ../..
```

#### Step 2.5: Create account-manager CI workflow

```bash
cat > .github/workflows/app-account-manager.yml << 'EOF'
name: Account Manager

on:
  push:
    branches: [main, develop]
    paths:
      - 'applications/account-manager/**'
      - 'grpc/**'
      - 'libraries/**'
      - '.github/workflows/app-account-manager.yml'
  pull_request:
    paths:
      - 'applications/account-manager/**'
      - 'grpc/**'
      - 'libraries/**'

jobs:
  build-and-test:
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
          ./gradlew test
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Build Application
        run: |
          cd applications/account-manager
          ./gradlew build
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Build Docker Image
        if: github.ref == 'refs/heads/main'
        run: |
          cd applications/account-manager
          ./gradlew build -Dquarkus.container-image.build=true

  publish-image:
    needs: build-and-test
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

      - name: Configure GitHub Packages
        run: |
          mkdir -p ~/.gradle
          echo "gpr.user=${{ github.actor }}" >> ~/.gradle/gradle.properties
          echo "gpr.token=${{ secrets.GITHUB_TOKEN }}" >> ~/.gradle/gradle.properties

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and Push Docker Image
        run: |
          cd applications/account-manager
          ./gradlew build \
            -Dquarkus.container-image.push=true \
            -Dquarkus.container-image.registry=ghcr.io \
            -Dquarkus.container-image.group=${{ github.repository_owner }} \
            -Dquarkus.container-image.username=${{ github.actor }} \
            -Dquarkus.container-image.password=${{ secrets.GITHUB_TOKEN }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
EOF
```

---

### Phase 3: Update Root Build (1 hour)

**Goal**: Update root build to exclude migrated projects

#### Step 3.1: Update root settings.gradle

```bash
# Edit settings.gradle to remove account-manager and libraries
cat > settings.gradle << 'EOF'
pluginManagement {
    repositories {
        mavenLocal() {
            content {
                includeGroupByRegex "io\\.pipeline(\\..*)?"
            }
        }
        maven { url = uri('https://s01.oss.sonatype.org/content/groups/public/') }
        gradlePluginPortal()
        mavenCentral()
    }
}

rootProject.name = 'pipeline'

// gRPC is built separately
include ':grpc:grpc-wiremock'

// Libraries are now built separately (see libraries/ directory)
// include ':bom'
// include ':libraries:...'

// Applications (except account-manager which is now independent)
include ':applications:platform-registration-service'
include ':applications:repo-service'
// include ':applications:account-manager'  // Now independent
include ':applications:mapping-service'
include ':applications:opensearch-manager'
include ':applications:connector-service'
include ':applications:linear-engine'

// Modules
include ':modules:echo'
include ':modules:chunker'
include ':modules:embedder'
include ':modules:parser'

buildCache {
    local {
        enabled = true
    }
}
EOF
```

#### Step 3.2: Update root build.gradle

Remove the dependency substitution for libraries that are now external:

```bash
# Keep most of build.gradle but update the substitution section
# You'll need to manually edit this file, but here's the key change:
```

Edit `/home/krickert/IdeaProjects/pipeline-engine-refactor/build.gradle` and modify the `allprojects` configuration block to only substitute remaining projects:

```gradle
allprojects {
    configurations.configureEach { cfg ->
        resolutionStrategy.dependencySubstitution { subs ->
            // Only substitute projects still in this build
            // Libraries are now external dependencies from GitHub Packages/Maven Local
            // subs.substitute module('io.pipeline:pipeline-commons') using project(':libraries:pipeline-commons')
            // ... (remove all library substitutions)

            // Keep grpc-wiremock substitution if it's still included
            subs.substitute module('io.pipeline:grpc-wiremock') using project(':grpc:grpc-wiremock')
        }
    }
}
```

---

### Phase 4: Migrate Remaining Applications (4-6 hours)

**Goal**: Convert all other applications to independent builds

For each application, repeat the process from Phase 2:

1. Create `settings.gradle`
2. Update `build.gradle`
3. Add Gradle wrapper
4. Test build
5. Create CI workflow

**Applications to migrate:**
- connector-service
- repo-service
- mapping-service
- opensearch-manager
- linear-engine
- platform-registration-service

**Template for each app:**

```bash
# Example: connector-service
cd applications/connector-service

# Create settings.gradle (same as account-manager)
cat > settings.gradle << 'EOF'
rootProject.name = 'connector-service'
# ... (same repository configuration as account-manager)
EOF

# Update build.gradle (adjust dependencies)
# Add Gradle wrapper
gradle wrapper --gradle-version 8.11

# Test
./gradlew build

# Create CI workflow
cat > ../../.github/workflows/app-connector-service.yml << 'EOF'
name: Connector Service
# ... (similar to account-manager workflow)
EOF

cd ../..
```

---

### Phase 5: Migrate Modules (3-4 hours)

**Goal**: Convert processing modules to independent builds

Same process as applications. For each module:

1. Create `settings.gradle`
2. Update `build.gradle`
3. Add Gradle wrapper
4. Test build
5. Create CI workflow

**Modules to migrate:**
- parser
- chunker
- embedder
- echo

---

### Phase 6: Restructure Node/Frontend (2-3 hours)

**Goal**: Move Node apps to root level and improve proto sync

#### Step 6.1: Move Node applications

```bash
# Move applications/node to root level
mv applications/node ./node-temp
mv node-temp node
```

#### Step 6.2: Update pnpm workspace

```bash
cat > node/pnpm-workspace.yaml << 'EOF'
packages:
  - 'web-proxy'
  - 'platform-shell'
  - 'dev-tools/frontend'
  - 'dev-tools/backend'
  - 'dev-tools/shared-ui'
  - 'drive-uploader'
  - 'libraries/*'

onlyBuiltDependencies:
  - '@parcel/watcher'
EOF
```

#### Step 6.3: Update proto sync scripts

Update proto sync paths in `node/libraries/proto-files/package.json`:

```json
{
  "scripts": {
    "sync": "rm -rf ./proto && mkdir -p ./proto && rsync -av --delete ../../grpc/grpc-stubs/src/main/proto/ ./proto/"
  }
}
```

#### Step 6.4: Update web-proxy proto sync

Update `node/web-proxy/package.json`:

```json
{
  "scripts": {
    "proto:sync": "rm -rf ./proto && mkdir -p ./proto && rsync -av --delete ../../grpc/grpc-stubs/src/main/proto/ ./proto/ && mkdir -p ./proto/engine && cp -f ./proto-local/shell_service.proto ./proto/engine/shell_service.proto"
  }
}
```

#### Step 6.5: Create Node CI workflow

```bash
cat > .github/workflows/web-proxy.yml << 'EOF'
name: Web Proxy

on:
  push:
    branches: [main, develop]
    paths:
      - 'node/web-proxy/**'
      - 'grpc/**'
      - '.github/workflows/web-proxy.yml'
  pull_request:
    paths:
      - 'node/web-proxy/**'
      - 'grpc/**'

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: 10

      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'pnpm'
          cache-dependency-path: 'node/pnpm-lock.yaml'

      - name: Install dependencies
        run: |
          cd node
          pnpm install

      - name: Build
        run: |
          cd node/web-proxy
          pnpm run build

      - name: Build Docker Image
        if: github.ref == 'refs/heads/main'
        run: |
          cd node/web-proxy
          docker build -t ghcr.io/${{ github.repository_owner }}/web-proxy:${{ github.sha }} .

  publish-image:
    needs: build-and-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and Push
        run: |
          cd node/web-proxy
          docker build -t ghcr.io/${{ github.repository_owner }}/web-proxy:latest .
          docker push ghcr.io/${{ github.repository_owner }}/web-proxy:latest
EOF
```

---

### Phase 7: Update gRPC Build for GitHub Packages (1 hour)

**Goal**: Configure gRPC stubs to publish to GitHub Packages

#### Step 7.1: Update grpc/build.gradle

Add publishing configuration:

```gradle
// Add to grpc/build.gradle
subprojects {
    apply plugin: 'maven-publish'

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
                    username = System.getenv("GITHUB_ACTOR") ?: project.findProperty("gpr.user")
                    password = System.getenv("GITHUB_TOKEN") ?: project.findProperty("gpr.token")
                }
            }
        }
    }
}
```

#### Step 7.2: Create gRPC CI workflow

```bash
cat > .github/workflows/grpc-stubs.yml << 'EOF'
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

      - uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'
          cache: 'gradle'

      - name: Build and Test
        run: |
          cd grpc
          ./gradlew build

  publish:
    needs: build-and-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'

      - name: Configure GitHub Packages
        run: |
          mkdir -p ~/.gradle
          echo "gpr.user=${{ github.actor }}" >> ~/.gradle/gradle.properties
          echo "gpr.token=${{ secrets.GITHUB_TOKEN }}" >> ~/.gradle/gradle.properties

      - name: Publish to GitHub Packages
        run: |
          cd grpc
          ./gradlew publish
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
EOF
```

---

### Phase 8: Create Development Infrastructure (1 hour)

**Goal**: Organize shared development resources

#### Step 8.1: Create dev-infrastructure directory

```bash
mkdir -p dev-infrastructure/scripts
```

#### Step 8.2: Move compose files

```bash
mv src/test/resources/compose-devservices.yml dev-infrastructure/
mv src/test/resources/compose-test-services.yml dev-infrastructure/
```

#### Step 8.3: Create setup script

```bash
cat > dev-infrastructure/scripts/setup-local-dev.sh << 'EOF'
#!/bin/bash
set -e

echo "=========================================="
echo "Pipeline Engine - Local Development Setup"
echo "=========================================="
echo ""

# Check prerequisites
command -v java >/dev/null 2>&1 || { echo "Error: Java 21 required but not found"; exit 1; }
command -v pnpm >/dev/null 2>&1 || { echo "Error: pnpm required but not found"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "Error: Docker required but not found"; exit 1; }

echo "✓ Prerequisites check passed"
echo ""

# Get repository root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

echo "Building gRPC stubs..."
cd grpc
./gradlew clean build publishToMavenLocal
cd ..
echo "✓ gRPC stubs published to Maven Local"
echo ""

echo "Building libraries..."
cd libraries
./gradlew clean build publishToMavenLocal
cd ..
echo "✓ Libraries published to Maven Local"
echo ""

echo "Installing Node dependencies..."
cd node
pnpm install
cd ..
echo "✓ Node dependencies installed"
echo ""

echo "=========================================="
echo "✓ Local development environment ready!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Start dev services:"
echo "     cd dev-infrastructure"
echo "     docker compose -f compose-devservices.yml up -d"
echo ""
echo "  2. Run any application:"
echo "     cd applications/account-manager"
echo "     ./gradlew quarkusDev"
echo ""
echo "  3. Run web-proxy:"
echo "     cd node/web-proxy"
echo "     pnpm run dev"
echo ""
EOF

chmod +x dev-infrastructure/scripts/setup-local-dev.sh
```

#### Step 8.4: Create start/stop scripts

```bash
cat > dev-infrastructure/scripts/start-dev-services.sh << 'EOF'
#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")/.."
docker compose -f compose-devservices.yml up -d
echo "✓ Dev services started"
docker compose -f compose-devservices.yml ps
EOF

chmod +x dev-infrastructure/scripts/start-dev-services.sh

cat > dev-infrastructure/scripts/stop-dev-services.sh << 'EOF'
#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")/.."
docker compose -f compose-devservices.yml down
echo "✓ Dev services stopped"
EOF

chmod +x dev-infrastructure/scripts/stop-dev-services.sh
```

#### Step 8.5: Update pnpm workspace at root

Update root `pnpm-workspace.yaml`:

```yaml
packages:
  - 'node/**'
  - 'applications/*/src/main/ui-vue'
  - 'modules/*/src/main/ui-vue'

onlyBuiltDependencies:
  - '@parcel/watcher'
```

---

### Phase 9: Update Documentation (1 hour)

#### Step 9.1: Update root README.md

Create comprehensive README:

```bash
cat > README.md << 'EOF'
# Pipeline Engine

Microservices-based document processing and search platform.

## Architecture

This mono-repository contains independent builds for:

- **gRPC Layer** (`grpc/`): Protocol definitions and testing utilities
- **Libraries** (`libraries/`): Shared Java libraries
- **Applications** (`applications/`): Microservices (Quarkus + gRPC)
- **Modules** (`modules/`): Processing modules (parser, chunker, etc.)
- **Node** (`node/`): Frontend applications and web proxy

## Quick Start

### Prerequisites

- Java 21+
- Node.js 22+
- pnpm 10+
- Docker + Docker Compose
- Gradle 8.11+

### Local Development Setup

```bash
# 1. Clone repository
git clone <repo-url>
cd pipeline-engine-refactor

# 2. Run setup script
./dev-infrastructure/scripts/setup-local-dev.sh

# 3. Start infrastructure services
cd dev-infrastructure
docker compose -f compose-devservices.yml up -d

# 4. Run an application (example: account-manager)
cd ../applications/account-manager
./gradlew quarkusDev
```

### Project Structure

```
pipeline-engine-refactor/
├── grpc/                           # gRPC stubs & wiremock (independent build)
├── libraries/                      # Shared libraries (independent build)
├── applications/                   # Microservices (each is independent build)
│   ├── account-manager/
│   ├── connector-service/
│   ├── repo-service/
│   └── ...
├── modules/                        # Processing modules (each is independent build)
│   ├── parser/
│   ├── chunker/
│   └── ...
├── node/                          # Node.js applications
│   ├── web-proxy/
│   ├── platform-shell/
│   └── libraries/
├── dev-infrastructure/            # Shared dev environment
│   ├── compose-devservices.yml
│   └── scripts/
└── .github/workflows/             # CI/CD pipelines (per-component)
```

## Building

Each component can be built independently:

```bash
# Build gRPC stubs
cd grpc && ./gradlew build

# Build libraries
cd libraries && ./gradlew build

# Build specific application
cd applications/account-manager && ./gradlew build

# Build specific module
cd modules/parser && ./gradlew build

# Build Node apps
cd node && pnpm install && pnpm run build
```

## Testing

### Unit Tests (Fast)

```bash
# Test specific application
cd applications/account-manager
./gradlew test
```

### Integration Tests (with Testcontainers)

```bash
# Run integration tests for specific service
cd applications/account-manager
./gradlew integrationTest
```

### Dev Mode (Live Testing)

```bash
# Start Quarkus dev mode (with live reload)
cd applications/account-manager
./gradlew quarkusDev

# Start Node dev mode
cd node/web-proxy
pnpm run dev
```

## CI/CD

Each component has its own GitHub Actions workflow that:
- Triggers only on relevant file changes
- Runs tests
- Publishes artifacts to GitHub Packages (on main branch)
- Builds Docker images

See `.github/workflows/` for details.

## Published Artifacts

Artifacts are published to GitHub Packages:
- **Maven**: `io.pipeline:*` packages
- **Docker**: `ghcr.io/YOUR_ORG/*` images
- **npm**: `@pipeline/*` packages (future)

## Contributing

1. Create feature branch
2. Make changes in specific component(s)
3. CI will test only affected components
4. Create PR
5. Merge to main triggers publishing

## Documentation

- [Build Restructuring Plan](docs/research/claude/build-restructuring-plan.md)
- [Testing Strategy](docs/research/claude/testing-strategy.md)
- [Local Development](docs/research/claude/local-development.md)

## License

[Your License]
EOF
```

#### Step 9.2: Create BUILD_ORDER_NEW.md

Document the new simplified build order:

```bash
cat > BUILD_ORDER_NEW.md << 'EOF'
# Build Order - New Structure

## For CI/CD (GitHub Actions)

Each component builds independently and pulls published dependencies from GitHub Packages.

**Build order is automatic** - GitHub Actions handles dependencies:

1. `grpc/**` changes → Trigger gRPC workflow → Publish to GitHub Packages
2. `libraries/**` changes → Trigger Libraries workflow → Pulls gRPC from Packages → Publish
3. `applications/account-manager/**` → Trigger App workflow → Pulls deps from Packages

## For Local Development

### First-Time Setup

```bash
# One-time setup
./dev-infrastructure/scripts/setup-local-dev.sh
```

This script:
1. Builds gRPC stubs → Maven Local
2. Builds libraries → Maven Local
3. Installs Node dependencies

### Daily Development

**Working on a single application:**
```bash
# Just run the app - uses Maven Local for dependencies
cd applications/account-manager
./gradlew quarkusDev
```

**Working on a library:**
```bash
# Rebuild library
cd libraries
./gradlew :pipeline-commons:publishToMavenLocal

# Dependent apps will pick up changes
cd ../applications/account-manager
./gradlew quarkusDev  # Uses updated library from Maven Local
```

**Working on gRPC protos:**
```bash
# Rebuild gRPC
cd grpc
./gradlew publishToMavenLocal

# Rebuild libraries (depend on gRPC)
cd ../libraries
./gradlew publishToMavenLocal

# Dependent apps pick up changes
cd ../applications/account-manager
./gradlew quarkusDev
```

**Working on Node/frontend:**
```bash
# Start web-proxy
cd node/web-proxy
pnpm run dev

# In another terminal, start backend service
cd applications/account-manager
./gradlew quarkusDev
```

## No More

- ✗ Building everything from root
- ✗ Complex multi-step build process
- ✗ Chicken-and-egg dependency issues
- ✗ Waiting for unrelated projects to build

## Now

- ✓ Build only what you're working on
- ✓ Fast incremental builds
- ✓ Independent CI/CD
- ✓ Clear dependency chain
EOF
```

---

### Phase 10: Testing and Validation (2-3 hours)

#### Step 10.1: Full clean build test

```bash
# Clean everything
rm -rf ~/.m2/repository/io/pipeline
find . -name "build" -type d -exec rm -rf {} + 2>/dev/null || true

# Build in order
cd grpc
./gradlew clean build publishToMavenLocal

cd ../libraries
./gradlew clean build publishToMavenLocal

cd ../applications/account-manager
./gradlew clean build

cd ../../modules/parser
./gradlew clean build

cd ../../node
pnpm install
pnpm run build
```

#### Step 10.2: Test Quarkus dev mode

```bash
# Start dev services
cd dev-infrastructure
docker compose -f compose-devservices.yml up -d

# Test account-manager
cd ../applications/account-manager
./gradlew quarkusDev
# Verify it starts, then press 'q' to quit

# Test another app
cd ../connector-service
./gradlew quarkusDev
# Verify it starts, then press 'q' to quit
```

#### Step 10.3: Test CI workflows (if possible)

```bash
# Commit and push to trigger workflows
git add .
git commit -m "Restructure build for independent CI/CD"
git push origin feature/build-restructure

# Create PR and watch GitHub Actions
```

---

## GitHub Packages Setup

### Repository Settings

1. **Enable GitHub Packages**
   - Settings → Actions → General
   - Workflow permissions: "Read and write permissions"
   - Check "Allow GitHub Actions to create and approve pull requests"

2. **Package Visibility**
   - Packages are private by default
   - Can make public: Package settings → Change visibility

### Publishing Configuration

#### For Maven (Java)

Each build.gradle needs publishing configuration:

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
                username = System.getenv("GITHUB_ACTOR") ?: project.findProperty("gpr.user")
                password = System.getenv("GITHUB_TOKEN") ?: project.findProperty("gpr.token")
            }
        }
    }
}
```

#### For Docker Images

Quarkus configuration:

```properties
# src/main/resources/application.properties
quarkus.container-image.registry=ghcr.io
quarkus.container-image.group=YOUR_ORG
quarkus.container-image.name=account-manager
quarkus.container-image.tag=${quarkus.application.version}
```

Build and push:

```bash
./gradlew build \
  -Dquarkus.container-image.push=true \
  -Dquarkus.container-image.username=$GITHUB_ACTOR \
  -Dquarkus.container-image.password=$GITHUB_TOKEN
```

### Consuming Packages

#### Local Development

Configure `~/.gradle/gradle.properties`:

```properties
gpr.user=YOUR_GITHUB_USERNAME
gpr.token=YOUR_PERSONAL_ACCESS_TOKEN
```

Generate token: Settings → Developer settings → Personal access tokens → Generate new token
- Scopes: `read:packages`, `write:packages`

#### CI/CD

GitHub Actions automatically provides `GITHUB_TOKEN`:

```yaml
- name: Build
  run: ./gradlew build
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

#### Other Consumers (External Teams)

Share your packages:

```gradle
// Their build.gradle
repositories {
    maven {
        url = uri("https://maven.pkg.github.com/YOUR_ORG/pipeline-engine-refactor")
        credentials {
            username = "their-github-username"
            password = "their-personal-access-token"
        }
    }
}

dependencies {
    implementation 'io.pipeline:grpc-stubs:1.0.0-SNAPSHOT'
}
```

---

## CI/CD Pipeline Configuration

### Workflow Patterns

#### 1. Library Workflow (with Publishing)

```yaml
name: Libraries

on:
  push:
    branches: [main, develop]
    paths:
      - 'libraries/**'
      - 'grpc/**'
  pull_request:
    paths:
      - 'libraries/**'

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: '21'
          cache: 'gradle'

      - name: Build gRPC (dependency)
        run: cd grpc && ./gradlew publishToMavenLocal

      - name: Build and Test Libraries
        run: cd libraries && ./gradlew build test

  publish:
    needs: build-and-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4

      - name: Publish to GitHub Packages
        run: cd libraries && ./gradlew publish
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

#### 2. Application Workflow (with Docker)

```yaml
name: Account Manager

on:
  push:
    branches: [main]
    paths:
      - 'applications/account-manager/**'
  pull_request:
    paths:
      - 'applications/account-manager/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4

      - name: Run Tests (with Testcontainers)
        run: cd applications/account-manager && ./gradlew test

  build-image:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and Push
        run: |
          cd applications/account-manager
          ./gradlew build -Dquarkus.container-image.push=true
```

#### 3. Node/Frontend Workflow

```yaml
name: Web Proxy

on:
  push:
    branches: [main]
    paths:
      - 'node/web-proxy/**'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'pnpm'

      - run: cd node && pnpm install
      - run: cd node/web-proxy && pnpm run build
```

### Optimization Strategies

#### 1. Path-Based Triggers

Only run workflows when relevant files change:

```yaml
on:
  push:
    paths:
      - 'applications/account-manager/**'
      - 'grpc/**'           # Rebuild if proto changes
      - 'libraries/**'      # Rebuild if deps change
```

#### 2. Caching

```yaml
- uses: actions/setup-java@v4
  with:
    cache: 'gradle'  # Cache Gradle dependencies

- uses: actions/setup-node@v4
  with:
    cache: 'pnpm'    # Cache Node modules
```

#### 3. Parallel Jobs

```yaml
jobs:
  test:
    strategy:
      matrix:
        java: [21]
        os: [ubuntu-latest, macos-latest]
    runs-on: ${{ matrix.os }}
```

#### 4. Reusable Workflows

Create `.github/workflows/reusable-java-build.yml`:

```yaml
name: Reusable Java Build

on:
  workflow_call:
    inputs:
      project-path:
        required: true
        type: string

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
      - run: cd ${{ inputs.project-path }} && ./gradlew build
```

Use in app workflows:

```yaml
jobs:
  build:
    uses: ./.github/workflows/reusable-java-build.yml
    with:
      project-path: applications/account-manager
```

---

## Local Development Workflow

### First Day Setup

```bash
# 1. Clone repo
git clone <repo-url>
cd pipeline-engine-refactor

# 2. Configure Gradle for GitHub Packages (if needed)
echo "gpr.user=YOUR_GITHUB_USERNAME" >> ~/.gradle/gradle.properties
echo "gpr.token=YOUR_GITHUB_PAT" >> ~/.gradle/gradle.properties

# 3. Run setup script
./dev-infrastructure/scripts/setup-local-dev.sh

# 4. Start infrastructure
cd dev-infrastructure
docker compose -f compose-devservices.yml up -d
```

### Daily Workflows

#### Working on Application Code

```bash
# Start dev mode (hot reload)
cd applications/account-manager
./gradlew quarkusDev

# Make changes to Java code
# Quarkus automatically reloads

# Run tests
./gradlew test

# Build Docker image
./gradlew build -Dquarkus.container-image.build=true
```

#### Working on Libraries

```bash
# Make changes to library
cd libraries
./gradlew :pipeline-commons:build :pipeline-commons:publishToMavenLocal

# Restart dependent app to use updated library
cd ../applications/account-manager
./gradlew quarkusDev
```

#### Working on Protos

```bash
# Modify proto files
vim grpc/grpc-stubs/src/main/proto/your_service.proto

# Rebuild gRPC
cd grpc
./gradlew build publishToMavenLocal

# Rebuild libraries (depend on protos)
cd ../libraries
./gradlew build publishToMavenLocal

# Restart app
cd ../applications/account-manager
./gradlew quarkusDev

# Sync Node protos
cd ../../node/libraries/proto-files
pnpm run sync

# Regenerate Node stubs
cd ../proto-stubs
pnpm run generate
```

#### Working on Frontend

```bash
# Terminal 1: Start backend
cd applications/account-manager
./gradlew quarkusDev

# Terminal 2: Start web-proxy
cd node/web-proxy
pnpm run dev

# Terminal 3: Start platform-shell
cd node/platform-shell
pnpm run dev
```

### Troubleshooting

#### "Could not find io.pipeline:grpc-stubs"

```bash
# Rebuild and publish gRPC to Maven Local
cd grpc
./gradlew publishToMavenLocal
```

#### "Proto files out of sync"

```bash
# Sync Node proto files
cd node/libraries/proto-files
pnpm run sync

# Rebuild proto stubs
cd ../proto-stubs
pnpm run generate
```

#### "Testcontainers not starting"

```bash
# Verify Docker is running
docker ps

# Check Docker Compose services
cd dev-infrastructure
docker compose -f compose-devservices.yml ps
```

---

## Testing Strategy

### Test Pyramid

```
        /\
       /  \     E2E Tests (Playwright) - Slow, comprehensive
      /____\
     /      \   Integration Tests (Testcontainers) - Medium
    /________\
   /          \  Unit Tests (JUnit + WireMock) - Fast
  /__________  \
```

### Unit Tests

**Goal**: Fast, isolated, no external dependencies

**Approach**: WireMock for gRPC calls

```java
// account-manager/src/test/java/.../AccountServiceTest.java
@QuarkusTest
class AccountServiceTest {

    @ConfigProperty(name = "quarkus.grpc.clients.registration.host")
    String grpcHost;

    @BeforeEach
    void setupWireMock() {
        // Use grpc-wiremock to stub registration service
        WireMock.stubFor(
            WireMock.post("/registration.RegistrationService/RegisterAccount")
                .willReturn(WireMock.ok()
                    .withHeader("content-type", "application/grpc")
                    .withBody(/* protobuf response */))
        );
    }

    @Test
    void testAccountCreation() {
        // Test logic without real external service
        Account account = accountService.createAccount("test@example.com");
        assertThat(account).isNotNull();
    }
}
```

**Run**: `./gradlew test` (fast, < 30 seconds)

### Integration Tests

**Goal**: Test with real infrastructure (DB, Kafka, etc.)

**Approach**: Testcontainers

```java
// account-manager/src/test/java/.../AccountRepositoryIT.java
@QuarkusTest
@TestProfile(IntegrationTestProfile.class)
class AccountRepositoryIntegrationTest {

    @Container
    static MySQLContainer<?> mysql = new MySQLContainer<>("mysql:8.0")
        .withDatabaseName("accountdb")
        .withUsername("test")
        .withPassword("test");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("quarkus.datasource.jdbc.url", mysql::getJdbcUrl);
        registry.add("quarkus.datasource.username", mysql::getUsername);
        registry.add("quarkus.datasource.password", mysql::getPassword);
    }

    @Inject
    AccountRepository repository;

    @Test
    void testDatabaseOperations() {
        Account account = new Account();
        account.setEmail("test@example.com");

        repository.persist(account);

        Account found = repository.findByEmail("test@example.com");
        assertThat(found).isNotNull();
    }
}
```

**Run**: `./gradlew integrationTest` (medium speed, ~2 minutes)

### Dev Mode Testing

**Goal**: Visual testing with real services

**Approach**: Quarkus Dev Mode + Docker Compose

```bash
# Start all infrastructure
cd dev-infrastructure
docker compose -f compose-devservices.yml up -d

# Start app in dev mode
cd ../applications/account-manager
./gradlew quarkusDev

# Manually test via UI or API calls
curl http://localhost:8080/api/accounts
```

**Frontend testing**: Start web-proxy + platform-shell, test visually

### End-to-End Tests (Future)

**Goal**: Full system testing

**Approach**: Playwright

```typescript
// e2e-tests/account-creation.spec.ts
import { test, expect } from '@playwright/test';

test('create account flow', async ({ page }) => {
  await page.goto('http://localhost:37200');
  await page.click('text=Create Account');
  await page.fill('input[name="email"]', 'test@example.com');
  await page.click('button[type="submit"]');

  await expect(page.locator('.success-message')).toBeVisible();
});
```

**Run**: Nightly or on-demand (slow, ~10 minutes)

### Testing per Component

| Component | Unit Tests | Integration Tests | Dev Mode | E2E |
|-----------|------------|-------------------|----------|-----|
| account-manager | JUnit + WireMock | Testcontainers (MySQL) | ✓ | ✓ |
| connector-service | JUnit + WireMock | Testcontainers (Kafka) | ✓ | ✓ |
| repo-service | JUnit + WireMock | Testcontainers (MinIO) | ✓ | ✓ |
| opensearch-manager | JUnit + WireMock | Testcontainers (OpenSearch) | ✓ | ✓ |
| parser | JUnit | Testcontainers (optional) | ✓ | - |
| web-proxy | Jest | - | ✓ | ✓ |

---

## Node/Frontend Strategy

### Directory Structure

```
node/
├── pnpm-workspace.yaml
├── web-proxy/              # gRPC-Web proxy (Node.js server)
├── platform-shell/         # Main frontend app
├── dev-tools/
│   ├── frontend/
│   ├── backend/
│   └── shared-ui/
├── drive-uploader/
└── libraries/
    ├── proto-files/        # Synced from grpc/grpc-stubs
    ├── proto-stubs/        # Generated TypeScript stubs
    ├── protobuf-forms/     # Form generation from protos
    ├── shared-components/  # Reusable Vue components
    └── shared-nav/         # Navigation components
```

### Proto Synchronization

**Automated sync** in proto-files:

```json
// node/libraries/proto-files/package.json
{
  "name": "@pipeline/proto-files",
  "scripts": {
    "sync": "rsync -av --delete ../../grpc/grpc-stubs/src/main/proto/ ./proto/",
    "watch": "nodemon --watch ../../grpc/grpc-stubs/src/main/proto/ --exec 'pnpm run sync'"
  }
}
```

**Usage**:

```bash
# One-time sync
cd node/libraries/proto-files
pnpm run sync

# Watch mode (auto-sync on proto changes)
pnpm run watch
```

### Proto Stub Generation

```json
// node/libraries/proto-stubs/package.json
{
  "name": "@pipeline/proto-stubs",
  "scripts": {
    "prepare": "pnpm --filter @pipeline/proto-files sync",
    "generate": "buf generate"
  },
  "dependencies": {
    "@pipeline/proto-files": "workspace:*"
  }
}
```

### Frontend Development Workflow

```bash
# Terminal 1: Start dev services
cd dev-infrastructure
docker compose -f compose-devservices.yml up -d

# Terminal 2: Start backend (e.g., account-manager)
cd applications/account-manager
./gradlew quarkusDev

# Terminal 3: Start web-proxy
cd node/web-proxy
pnpm run dev

# Terminal 4: Start platform-shell
cd node/platform-shell
pnpm run dev
```

**Access**:
- Platform Shell: http://localhost:37200
- Web Proxy: http://localhost:37201
- Traefik (routing): http://localhost:8080

### Testing Strategy

**Unit tests** (Jest):
```bash
cd node/web-proxy
pnpm run test
```

**Visual testing**: Dev mode + manual testing

**E2E tests** (future Playwright):
```bash
pnpm run test:e2e
```

---

## Rollout Schedule

### Week 1: Foundation
- [ ] Phase 0: Preparation (Day 1)
- [ ] Phase 1: Restructure Libraries (Day 2-3)
- [ ] Phase 2: Proof of Concept (account-manager) (Day 4-5)

### Week 2: Migration
- [ ] Phase 3: Update Root Build (Day 1)
- [ ] Phase 4: Migrate Applications (Day 2-4)
- [ ] Phase 5: Migrate Modules (Day 5)

### Week 3: Frontend & Infrastructure
- [ ] Phase 6: Restructure Node/Frontend (Day 1-2)
- [ ] Phase 7: Update gRPC for GitHub Packages (Day 3)
- [ ] Phase 8: Create Dev Infrastructure (Day 4)
- [ ] Phase 9: Update Documentation (Day 5)

### Week 4: Validation & Rollout
- [ ] Phase 10: Testing and Validation (Day 1-2)
- [ ] Fix any issues found in testing (Day 3)
- [ ] Merge to main (Day 4)
- [ ] Monitor CI/CD pipelines (Day 5)
- [ ] Team training and documentation review (ongoing)

---

## Success Criteria

### Build Independence
- [ ] Each application builds without requiring root build
- [ ] Each module builds without requiring root build
- [ ] Libraries build independently
- [ ] gRPC builds independently

### CI/CD
- [ ] All components have GitHub Actions workflows
- [ ] Workflows trigger only on relevant changes
- [ ] Artifacts publish to GitHub Packages on main branch
- [ ] Docker images publish to GHCR

### Local Development
- [ ] Setup script works from clean checkout
- [ ] Quarkus dev mode works for all applications
- [ ] Node dev mode works for web-proxy and platform-shell
- [ ] Proto sync is automated

### Testing
- [ ] Unit tests run in < 1 minute per component
- [ ] Integration tests use Testcontainers
- [ ] No shared test infrastructure (except dev-infrastructure for dev mode)

### Documentation
- [ ] README updated
- [ ] Build order documented
- [ ] Testing strategy documented
- [ ] Local development workflow documented

---

## Risks and Mitigations

### Risk: Breaking Changes During Migration

**Mitigation**:
- Use feature branch
- Migrate one component at a time
- Test each phase before moving to next
- Keep root build working until migration complete

### Risk: GitHub Packages Authentication Issues

**Mitigation**:
- Document token setup clearly
- Provide fallback to Maven Local for local dev
- Test with different developer accounts

### Risk: CI/CD Costs

**Mitigation**:
- Start with path-based triggers (only build what changed)
- Use caching aggressively
- Monitor GitHub Actions usage
- Optimize workflows over time

### Risk: Team Resistance to Change

**Mitigation**:
- Demonstrate benefits with proof of concept
- Provide clear documentation
- Offer training sessions
- Keep setup script simple

---

## Future Enhancements

### Short-term (1-3 months)
- [ ] Add Playwright E2E tests
- [ ] Publish reusable Node libraries to GitHub Packages
- [ ] Implement semantic versioning for libraries
- [ ] Add build performance monitoring

### Medium-term (3-6 months)
- [ ] Implement automatic dependency updates (Dependabot)
- [ ] Add code coverage reporting
- [ ] Implement integration test parallelization
- [ ] Consider monorepo tools (Nx, Turborepo) for Node

### Long-term (6-12 months)
- [ ] Evaluate separate repositories for stable libraries
- [ ] Implement release automation
- [ ] Add performance regression testing
- [ ] Consider polyrepo for maximum independence

---

## Appendix: Command Reference

### Build Commands

```bash
# gRPC
cd grpc && ./gradlew build publishToMavenLocal

# Libraries
cd libraries && ./gradlew build publishToMavenLocal

# Application
cd applications/account-manager && ./gradlew build

# Module
cd modules/parser && ./gradlew build

# Node
cd node && pnpm install && pnpm run build
```

### Dev Mode Commands

```bash
# Quarkus app
cd applications/account-manager && ./gradlew quarkusDev

# Node app
cd node/web-proxy && pnpm run dev
```

### Testing Commands

```bash
# Unit tests
./gradlew test

# Integration tests
./gradlew integrationTest

# All tests
./gradlew check
```

### Infrastructure Commands

```bash
# Start dev services
cd dev-infrastructure && docker compose -f compose-devservices.yml up -d

# Stop dev services
docker compose -f compose-devservices.yml down

# View logs
docker compose -f compose-devservices.yml logs -f

# Check status
docker compose -f compose-devservices.yml ps
```

### Publishing Commands

```bash
# Publish to Maven Local
./gradlew publishToMavenLocal

# Publish to GitHub Packages
./gradlew publish

# Build Docker image
./gradlew build -Dquarkus.container-image.build=true

# Build and push Docker image
./gradlew build -Dquarkus.container-image.push=true
```

---

**Document Version**: 1.0
**Last Updated**: 2025-10-23
**Maintained By**: Development Team
