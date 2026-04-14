# ai-pipestream Coding Standards

This directory is the canonical set of conventions for every repo in the `ai-pipestream` GitHub organization. The goal is narrow: a new project (or a new LLM session) should be able to read one page per topic and immediately know how we do things, without reverse-engineering it from another service.

These are **principles + examples**, not CI gates. Where an existing doc in `dev-assets/docs/` is already authoritative on a topic, this directory links to it rather than rewriting it.

## How to use these standards

1. When you start a new service or module, read `00-source-of-truth.md` first, then the topics relevant to what you're building.
2. When reviewing code, cite the specific standard by filename (e.g. "this violates `01-protobufs-apicurio-grpc.md` § UUID keys") so pushback is grounded.
3. When a standard is wrong or out of date, edit the file and send a PR — standards drift if nobody maintains them.

## Topic index

### 00 — Source of truth
[`00-source-of-truth.md`](00-source-of-truth.md). The `reference-code/` folder is the authoritative reference for Quarkus, Apicurio, and wiremock-grpc — read it before web-searching. `pipestream-protos` is the only place `.proto` files live. `pipestream-platform` owns the BOM and every Quarkus extension. When these three disagree with a README, the code wins.

### 01 — Protobufs, Apicurio, and gRPC
[`01-protobufs-apicurio-grpc.md`](01-protobufs-apicurio-grpc.md). Protos are defined in `pipestream-protos` and consumed via the `quarkus-buf-grpc-generator` Gradle plugin (`pipestreamProtos { }` DSL). Apicurio is 100% PROTOBUF — never JSON, never Avro. Kafka keys are deterministic UUIDs, extracted via `UuidKeyExtractor<T>`. gRPC is the primary transport; REST exists only as a developer-convenience wrapper over a gRPC impl. gRPC shares the HTTP port (`quarkus.grpc.server.use-separate-server=false`) and message size limits are raised to 2 GB.

### 02 — Mutiny and non-blocking
[`02-mutiny-non-blocking.md`](02-mutiny-non-blocking.md). Service methods return `Uni<T>` or `Multi<T>`. No `.await()`, no `.await().atMost(...)` outside of `@QuarkusTest`, no ad-hoc thread pools. Genuinely blocking work (Tika, JDBC, file I/O) is offloaded with `Infrastructure.getDefaultWorkerPool()` or `@Blocking`, not with handwritten `Executors.newFixedThreadPool(...)`.

### 03 — pipestream-platform extensions
[`03-platform-extensions.md`](03-platform-extensions.md). A reference of every Quarkus extension shipped by `pipestream-platform` and what it auto-configures so downstream projects stop writing scaffolding. Covers `quarkus-apicurio-registry-protobuf`, `pipestream-quarkus-devservices`, `quarkus-dynamic-grpc`, `pipestream-service-registration`, `pipestream-server`, `pipestream-test-support`, and `pipestream-descriptor`.

### 04 — DevServices and compose
[`04-devservices-compose.md`](04-devservices-compose.md). Quarkus DevServices is **always on**. In `%dev`, it coexists with the compose plugin and yields containers to `pipestream-quarkus-devservices` (this part is still being refined — see the in-flight note in the doc). In `%test`, it uses standard Testcontainers through `pipestream-test-support`. Never turn DevServices off. Never pipe compose into `%test`.

### 05 — Testing
[`05-testing.md`](05-testing.md). Tests use `@QuarkusTest` with `@QuarkusTestResource` fixtures from `pipestream-test-support`. Do not change how tests are run — they rely on docker infrastructure via Testcontainers, not compose. For mocking gRPC dependencies, use `pipestream-wiremock-server` with one of its four patterns. Name integration tests `*IT.java`, unit tests `*UnitTest.java`, component tests `*Test.java`.

### 06 — Frontend
[`06-frontend.md`](06-frontend.md). All user-facing UI lives in `pipestream-frontend` — a Vue 3 monorepo. Backend services do not ship their own frontends (the one small exception is module-parser's Quinoa UI at `/admin`, which is for internal inspection). The frontend talks to backends via connect-es over HTTP/1.1 (Connect-Web). Forms are rendered by JSONForms, and JSON Schemas are served by backend services at `/q/*` endpoints generated from REST DTO annotations.

### 07 — Build and versions
[`07-build-versions.md`](07-build-versions.md). Always on the latest Quarkus (currently 3.34.3). Java 21. Gradle version catalog in `pipestream-platform`. BOM import is mandatory — never pin pipestream library versions individually. `axion-release` drives version numbers from git tags. Publishing to GitHub Packages + Maven Central via `nmcp`.

## Related reference material inside dev-assets

These existing docs are authoritative for their specific topics and are linked from the standards above rather than duplicated:

- [`docs/compose-dev-services-guide.md`](../compose-dev-services-guide.md) — shared compose infrastructure, MySQL/Kafka/Consul/Apicurio/Redis/OpenSearch setup
- [`docs/reference/grpc/GRPC_Build.md`](../reference/grpc/GRPC_Build.md) — gRPC build artifacts, Mutiny stubs, Connect-ES frontend codegen
- [`docs/reference/grpc/GRPC_Communication_Patterns.md`](../reference/grpc/GRPC_Communication_Patterns.md) — unary/server-streaming/client-streaming/bidirectional patterns, 2 GB message handling
- [`docs/design/ADR-001-custom-kafka-message-converter.md`](../design/ADR-001-custom-kafka-message-converter.md) — why the custom Kafka converter exists
- [`docs/archive/testing/Testing_guidelines.md`](../archive/testing/Testing_guidelines.md) — older testing notes; being superseded by `05-testing.md` here

## What's out of scope (for now)

- CI enforcement / linter rules — these are principles + examples, not gates
- Security / auth architecture — separate RFC coming
- Observability / OpenTelemetry wiring — will get a dedicated standard once the OTLP story stabilizes
- Release process — lives in individual project READMEs

## Living documents

Every file here is expected to evolve. When you find a convention this directory is missing, add it. When you find a convention that's aspirational ("this is how we *want* it to work") versus actual ("this is what's in the code today"), label it clearly — avoid letting the two blur.
