# 07 — Build and versions

The platform stays on the latest Quarkus, uses Java 21, and centralizes every version through the `pipestream-platform` BOM and Gradle version catalog. Downstream projects never pin Quarkus or pipestream library versions directly.

## Pinned versions (as of April 2026)

- **Quarkus:** 3.34.3 (`pipestream-platform/gradle.properties`)
- **Java:** 21 (Temurin)
- **Gradle:** 9.4.x (wrapper)
- **Apicurio Registry:** v3, explicitly overridden in the BOM to a newer version than the Quarkus platform default
- **Protobuf + gRPC + Testcontainers:** managed via the Gradle version catalog (`libs.versions.toml` in `pipestream-platform`)

We always try to be on the latest Quarkus. When a new version lands:

1. Upgrade `pipestream-platform/gradle.properties`
2. Run `./gradlew build` in `pipestream-platform` — fix any API drift in the extensions
3. Cut a new BOM release
4. Downstream projects bump `pipestreamBomVersion` in their own `gradle.properties` and pick up the whole upgrade transitively

Never do a Quarkus upgrade by bumping one service directly — it will drift.

## BOM usage — mandatory

Every project imports the BOM and consumes pipestream libraries without versions:

```groovy
// build.gradle
dependencies {
    implementation platform("ai.pipestream:pipestream-bom:${pipestreamBomVersion}")

    // No version on any of these — the BOM owns it:
    implementation 'ai.pipestream:pipestream-server'
    implementation 'ai.pipestream:pipestream-service-registration'
    implementation 'ai.pipestream:quarkus-dynamic-grpc'
    implementation 'ai.pipestream:quarkus-apicurio-registry-protobuf'
    implementation 'ai.pipestream:pipestream-quarkus-devservices'

    testImplementation 'ai.pipestream:pipestream-test-support'
}
```

The `pipestreamBomVersion` property lives in `gradle.properties` and is the single number a service bumps when it wants new platform capabilities.

### Never
- `implementation 'ai.pipestream:pipestream-server:0.7.16'` — versioned outside the BOM
- `implementation "io.quarkus:quarkus-core:3.34.3"` — pinning Quarkus directly
- Overriding an Apicurio or gRPC version in a service `build.gradle` — the BOM owns these
- Copying a `dependencies { }` block from an old project without checking whether it still pins versions

## Standard plugin stack

Every service or module `build.gradle` uses this plugin block:

```groovy
plugins {
    id 'java'
    alias(libs.plugins.quarkus)
    alias(libs.plugins.proto.toolchain)    // ai.pipestream.proto-toolchain
    alias(libs.plugins.axion.release)
    alias(libs.plugins.maven.publish)
    alias(libs.plugins.nmcp.single)
    alias(libs.plugins.signing)
}
```

- `quarkus` — standard Quarkus Gradle plugin
- `proto.toolchain` — the custom `quarkus-buf-grpc-generator` plugin; disables Quarkus's built-in gRPC codegen (see [`01-protobufs-apicurio-grpc.md`](01-protobufs-apicurio-grpc.md))
- `axion.release` — computes `version` from git tags; never set `version = '0.1.2'` manually in a build script
- `maven.publish` + `nmcp.single` — publishes to Maven Central
- `signing` — GPG signatures on published artifacts

## Java toolchain

```groovy
java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
        vendor = JvmVendorSpec.ADOPTIUM    // Temurin
    }
}
```

Rules:

- **Java 21 minimum.** Not 17, not 23 until the platform explicitly moves.
- **Use virtual threads** for any blocking work that has to happen (see [`02-mutiny-non-blocking.md`](02-mutiny-non-blocking.md)). Prefer `@Blocking` + Quarkus's managed worker pool to explicit `Thread.ofVirtual()` — the platform will grow into virtual thread adoption once Quarkus fully commits.

## Port allocations

Every service has a fixed HTTP port it exposes in dev mode. gRPC shares the HTTP port (`quarkus.grpc.server.use-separate-server=false`), so a single port per service is enough. Known allocations as of April 2026:

| Service | Port |
|---------|------|
| platform-registration-service | 18101 |
| module-chunker | 19002 |
| module-parser (prod) | 19001 |
| module-parser (dev) | 19101 |
| …additional services TBD | see each service's `application.properties` |

When adding a new service, pick an unused port in the same range, document it in the service's README and in the list above, and update the dev container config if applicable. The `18xxx` range is for platform services, the `19xxx` range is for modules. When we move to dev containers on docker, every service will be able to bind to `8080` internally and be addressed by its docker DNS name — these host-port numbers are only an interim concern.

## Authentication for dependencies

Most pipestream libraries and extensions are published to GitHub Packages. A build needs:

```bash
export GITHUB_ACTOR=<your gh username>
export GITHUB_TOKEN=<PAT with read:packages>
```

These are sourced from the environment by `settings.gradle` repository config. Tests and builds will fail without them. `~/.gradle/gradle.properties` is a fine place to set them for personal machines; for CI they come from action secrets.

If a project uses Buf's remote schema registry directly (not the typical case — most go through git-proto-workspace), `BUF_TOKEN` is also needed.

## Version of this document

This file is expected to get out of date every time Quarkus or the BOM moves. When you bump `pipestream-platform`, update the pinned versions here in the same PR. The "pinned versions" section is the one section that is time-sensitive; the rules below it are stable.
