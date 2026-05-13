# 08 — Java code style

This document captures the conventions used in the existing codebase: package layout, CDI scope choice, configuration style, javadoc voice, exception handling, and naming. It is descriptive of what the code does today, not aspirational. Citations point at real files so the conventions can be inspected directly.

For concurrency model, see [`02-virtual-threads.md`](02-virtual-threads.md). For protos and gRPC, see [`01-protobufs-apicurio-grpc.md`](01-protobufs-apicurio-grpc.md). For builds and Java version, see [`07-build-versions.md`](07-build-versions.md).

## Package layout

- Java root package: `ai.pipestream.<area>.<subarea>` — e.g. `ai.pipestream.quarkus.openvino.runtime`, `ai.pipestream.module.embedder.spi`, `ai.pipestream.connector.s3`.
- Quarkus extension repos use the **three-module split**: `runtime/`, `deployment/`, `integration-tests/` — each as its own Gradle subproject. Use explicit `include` + `projectDir` so published artifactIds carry the extension name (`quarkus-openvino-embeddings-deployment`, not the bare directory name `deployment`). Reference: `pipestream-embedder-openvino/settings.gradle`.
- Standalone connectors and microservices skip the split — flat `src/main/java/`. This drift is intentional: only Quarkus extensions need separate runtime/deployment classloaders.

## CDI scopes

The choice between `@Singleton` and `@ApplicationScoped` is intentional and documented inline.

### `@Singleton` for SPI implementations crossing extension classloaders

When the bean implements an interface that lives in a different jar (an api jar, an SPI module), use `@Singleton`. ARC generates a client proxy for `@ApplicationScoped` beans, and that proxy can't be cast to the SPI interface when the interface was loaded by a different classloader — symptom: `ClassCastException: X_ClientProxy cannot be cast to <SPI>` at startup.

The reasoning is recurring enough that it lives in the javadoc of every such impl. Reference: `pipestream-embedder-openvino/runtime/.../OpenVinoBackend.java` and `pipestream-embedder-djl/runtime/.../DjlServingBackend.java` both have a multi-paragraph block explaining the choice.

### `@ApplicationScoped` for in-extension beans

Health checks (`@Readiness`), scheduled poll services, registries, anything that participates in CDI lifecycle but doesn't cross a classloader boundary. Reference: `DjlModelRegistry`.

### `@ConfigMapping` interfaces are not CDI-scoped

Quarkus generates the bean automatically.

## Configuration

- **`@ConfigMapping` for anything more than a single scalar.** Prefix is `pipestream.<area>.*`. Nested interfaces with `@WithName` for kebab-case keys, `@WithDefault` for fallbacks. Reference: `pipestream-embedder-djl/runtime/.../DjlServingRuntimeConfig.java` (`pipestream.djl-serving.*`).
- **Bare `@ConfigProperty` is OK for one-off scalars.** If you find yourself adding a third one for the same area, promote them all to `@ConfigMapping`.
- **gRPC clients configure via the Quarkus stack:** `quarkus.grpc.clients.<name>.host`, `.port`, `.tls-configuration-name`, `.name-resolver=stork`. Don't hand-roll `ManagedChannel` lifecycles. Reference: `OpenVinoBackend.java` javadoc lists the full set of keys it depends on.
- **Per-area prefix discipline:** `pipestream.*` for our own knobs, `quarkus.*` for Quarkus's, `embedder.<x>` for one-off legacy keys (which should be migrated to `pipestream.embedder.<x>` over time).

## Logging

- slf4j via `LoggerFactory`:
  ```java
  private static final Logger log = LoggerFactory.getLogger(Foo.class);
  ```
- Build-time processors (deployment classes) sometimes use JBoss Logger because Quarkus internals do — keep that drift; both are fine inside their layer.
- Levels:
  - `info` — operational milestones (model discovered, registry refreshed, service registered)
  - `debug` — hot-path counters and per-batch stats
  - `warn` — external system unhealthy but we're degrading gracefully
  - `error` — true failures the user needs to see

## Javadoc style — the house voice

This is the most distinctive convention in the codebase, and it's worth matching.

Top-of-class doc has multiple `<p>` blocks. Each block leads with a **bold section header** then explains the WHY in plain prose:

```java
/**
 * OpenVINO Model Server backend. Implements the single
 * {@link EmbeddingBackend} SPI over a KServe v2 gRPC transport using the
 * Quarkus {@link GrpcClient} stack — Stork service discovery, TLS,
 * deadlines, and interceptors are all configurable via
 * {@code quarkus.grpc.clients.ovms.*} keys, not hand-rolled.
 *
 * <p><b>Reactive contract (honest version).</b> Every method on
 * {@link EmbeddingBackend} that does I/O returns a {@link Uni}. There
 * is no {@code .await()}, no blocking stub, no {@code Uni.createFrom().item(...)}
 * wrapper anywhere on the hot path. ...
 *
 * <p>Marked {@link Singleton} (not {@code @ApplicationScoped}) so ARC
 * does not generate a client proxy — required because
 * {@link EmbeddingBackend} is discovered via
 * {@code Instance<EmbeddingBackend>} across a Quarkus extension
 * classloader boundary, and client proxies can't cross that cleanly.
 */
```

Conventions:

- Heavy use of `{@code ...}` for config keys, file paths, exact identifiers
- `{@link ...}` for related types when the reader needs to navigate
- Reasoning paragraphs are honest about tradeoffs (the "honest probe" section in `OpenVinoBackend`, the `@Singleton` rationale block in every SPI impl)
- Don't write a class doc that just restates the class name. The doc earns its place by explaining decisions a reader couldn't reverse-engineer from the code

When the codebase migrates off Mutiny, the "Reactive contract" paragraph above will read differently in the new code — but the **shape** of the doc (bold header, reasoned prose, honest tradeoffs) stays the same.

## Inline comments

- Comments explain WHY, not WHAT. Well-named identifiers do the WHAT.
- Reference for the right voice — the "Honest probe" block in `OpenVinoBackend.embed()`:
  ```java
  // Honest probe: only "this specific model isn't served" signals
  // (gRPC NOT_FOUND / UNIMPLEMENTED) resolve to false. Every other
  // error (UNAVAILABLE, DEADLINE_EXCEEDED, INTERNAL, UNAUTHENTICATED,
  // PERMISSION_DENIED, plain RuntimeException, etc.) propagates so
  // the router, ops, and metrics see the real failure instead of a
  // silent "backend doesn't support this model" that leaves a sick
  // backend silently disabled forever.
  ```
  The comment justifies a non-obvious classification choice and cites the operational consequence. That's what earns inline space.
- Field-level javadoc when the field's lifecycle isn't obvious:
  ```java
  /**
   * Per-servingName memoised {@code Uni<client>}. Resolves when
   * {@code ModelMetadata} discovery completes; subsequent subscriptions
   * skip the RPC thanks to {@code memoize().indefinitely()}.
   */
  private final ConcurrentHashMap<String, Uni<...>> clients = ...;
  ```
- **Don't** reference issue numbers, "added for X flow", "called by Y" — those rot. Reference invariants that survive renames.

## Exception handling

The codebase prefers **honest probe semantics**: classify failures, only swallow the ones that semantically mean "this specific resource isn't here." Everything else (transport failure, timeout, auth, internal) propagates so the router/metrics see real failures and a sick backend isn't silently disabled forever.

For gRPC errors, pattern-match on the status code, not on stringified messages:

```java
catch (StatusRuntimeException sre) {
    Status.Code code = sre.getStatus().getCode();
    if (code == Status.Code.NOT_FOUND || code == Status.Code.UNIMPLEMENTED) {
        log.info("backend does not serve '{}': {}", name, sre.getStatus());
        return false;
    }
    throw sre;   // let UNAVAILABLE, DEADLINE_EXCEEDED, INTERNAL, etc. propagate
}
```

(Pattern shown in post-Mutiny shape; the equivalent Mutiny-era code lives in `OpenVinoBackend.supports()`.)

Retry policy lives in dedicated classifier classes (e.g. `EmbeddingRetryClassifier` in module-embedder), not scattered around call sites. When you find yourself adding a third `if (e instanceof X)` near a retry, extract a classifier.

## Naming

Class suffixes carry meaning. Use them consistently.

| Suffix | Means |
|---|---|
| `*Service` | Business logic CDI bean. |
| `*Backend` | Pluggable provider implementing an SPI. |
| `*Client` | REST/gRPC client wrapper (often the `@RegisterRestClient` interface). |
| `*Registry` | Discovery / lookup bean, usually with a scheduled refresh. |
| `*ReadinessCheck` / `*HealthCheck` | MicroProfile health probe. |
| `*Descriptor` | Immutable metadata snapshot. |
| `*Processor` | Quarkus build-time augmentation (lives in `deployment/`). |
| `*Config` | `@ConfigMapping` interface. |
| `*RuntimeConfig` | `@ConfigMapping` interface that's `@ConfigRoot(phase = ConfigPhase.RUN_TIME)` — phase made visible in the name. |
| `*Request` / `*Response` | HTTP DTO when not using proto-generated types. |

For tests:

- `*UnitTest.java` — pure unit, no Quarkus boot
- `*Test.java` — component test, may use `@QuarkusTest`
- `*IT.java` — integration test, in the `integration-tests/` subproject, typically Testcontainers-based

## Testing

Detail lives in [`05-testing.md`](05-testing.md). Two style points specific to this doc:

- **Testcontainers with optional external override.** If a service can be supplied by a long-lived dev instance, expose `-D<service>.host=...` and `<SERVICE>_HOST` env var. The container starts only when those aren't set. Reference: `OpenVinoBatchingClientsIT.java`'s `USE_EXTERNAL_OVMS` flag.
- **`@DisplayName` on every test** — keeps the run output readable.

## Build files

- Plugins via version catalog: `alias(libs.plugins.axion.release)`, `alias(libs.plugins.nmcp.bundle)`. The catalog source is `gradle/libs.versions.toml`, often pulled from `ai.pipestream:pipestream-bom-catalog` via `from(...)` in `dependencyResolutionManagement`.
- Versioning: `axion-release` with `v` tag prefix; all subprojects inherit one version.
- Maven Central publishing: `nmcp.bundle` aggregation (`publishAllProjectsProbablyBreakingProjectIsolation()`). The per-subproject `nmcp.single` is incompatible with multiple publishing subprojects (gratatouille build-service registration race). Reference: `pipestream-embedder-openvino/build.gradle:34-43`.
- Local snapshots: resolved via `mavenLocal { content { includeGroupByRegex "ai\\.pipestream(\\..*)?" } }`. Keeps third-party deps off mavenLocal; only platform artifacts use it.

## README style for repo roots

- Repo root `README.md` is short — points at `docs/README.md` for the long-form.
- `docs/` is where the real documentation lives: deep `README.md`, `scripts/` (one-shot setup + verify + benchmark), `benchmarks/` (committed CSVs), inline `docker-compose.yml` if the repo defines a deployable stack.
- Top of long-form README: 1-paragraph intent, "Quick start" block (3–5 commands max), then "What gets deployed" before any architecture deep-dive.
- Tables for benchmark numbers; mark the winner per row in bold. Reference: `pipestream-embedder-openvino/docs/README.md`.

## Drift tolerance

These conventions are descriptive, not prescriptive. Where existing code drifts (logger framework, package depth, README structure), favor consistency *within a repo* over consistency *across the platform*. When you start a new repo, match this doc.
