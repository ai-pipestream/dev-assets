# 02 — Virtual threads, not Mutiny

> **Direction reversal (2026-05-12).** This document used to require `Uni<T>` / `Multi<T>` returns and forbid `.await()`. That policy is reversed. New code uses **plain blocking Java on virtual threads** (`@RunOnVirtualThread`), and existing Mutiny code is being migrated. The earlier doc lives in git history; do not revive its rules.

The reason for the change is maintainability, not performance. Mutiny pipelines obscured control flow, exploded stack traces, and asked every contributor to learn a second programming model on top of Java. Virtual threads give us cheap concurrency without that cognitive tax — `Thread.sleep`, `synchronized`-with-Lock, `try/catch`, and direct returns all work again.

## The core rule

**Service methods do blocking work on a virtual thread.** Annotate the entry point with `@RunOnVirtualThread`. The method body is plain Java. Inject blocking gRPC stubs and synchronous REST clients. Do not introduce `Uni<T>` returns on new SPIs.

This applies to gRPC service methods, REST endpoints, Kafka consumers, scheduled jobs, and any CDI bean method called from a request path.

### Good — blocking on a virtual thread

```java
@GrpcService
public class GreeterImpl implements Greeter {

    @Inject
    @GrpcClient("downstream")
    DownstreamGrpc.DownstreamBlockingStub downstream;

    @Override
    @RunOnVirtualThread
    public Uni<HelloReply> sayHello(HelloRequest request) {
        DownstreamReply r = downstream.fetch(toFetchRequest(request));   // blocking, on a VT
        return Uni.createFrom().item(HelloReply.newBuilder()
            .setMsg(r.getMessage())
            .build());
    }
}
```

The generated gRPC interface still demands a `Uni<T>` return, so we wrap the final value in `Uni.createFrom().item(...)`. **The body itself is blocking, sequential Java.** No `.map`, no `.flatMap`, no `.onItem`.

### Bad — composing reactively

```java
// DO NOT WRITE THIS in new code.
public Uni<HelloReply> sayHello(HelloRequest request) {
    return downstream.fetch(toFetchRequest(request))
        .onItem().transform(r -> HelloReply.newBuilder().setMsg(r.getMessage()).build())
        .onFailure(NotFoundException.class).recoverWithItem(notFound());
}
```

Reactive composition is the pattern we're leaving. If you find yourself reaching for `.onItem().transformToUni(...)`, stop and write it as straight-line code on a VT instead.

## The five canonical migrations

If you are touching a Mutiny file, one of these five patterns applies. Apply the diff verbatim where possible.

### A. gRPC service returning `Uni<Response>`

Keep the `Uni<Response>` return signature (the generated interface forces it). Add `@RunOnVirtualThread`. Build the response with straight-line blocking code. Wrap in `Uni.createFrom().item(...)`.

```java
// BEFORE
public Uni<HelloReply> sayHello(HelloRequest r) {
    return repo.find(r.getName()).map(n -> HelloReply.newBuilder().setMsg(n).build());
}
// AFTER
@RunOnVirtualThread
public Uni<HelloReply> sayHello(HelloRequest r) {
    String n = repo.findBlocking(r.getName());
    return Uni.createFrom().item(HelloReply.newBuilder().setMsg(n).build());
}
```

### B. gRPC client (was `MutinyXxxStub`)

```java
// BEFORE
@GrpcClient("hello") MutinyGreeterGrpc.MutinyGreeterStub stub;
String n = stub.sayHello(req).await().atMost(Duration.ofSeconds(2)).getMsg();
// AFTER
@GrpcClient("hello") GreeterGrpc.GreeterBlockingStub stub;
String n = stub.sayHello(req).getMsg();
```

Both stub types accept the same `@GrpcClient` qualifier — only the type changes. Per-call deadlines move from `.await().atMost(...)` to `stub.withDeadlineAfter(...)` on the blocking stub.

### C. MicroProfile REST client returning `Uni<JsonObject>`

```java
// BEFORE
@RegisterRestClient interface Weather { @GET Uni<JsonObject> get(); }
JsonObject j = weather.get().await().atMost(D);
// AFTER
@RegisterRestClient interface Weather { @GET JsonObject get(); }
JsonObject j = weather.get();
```

### D. SPI returning `Uni<...>`

Change the SPI to a synchronous return type. **Every implementation and every caller migrate in the same PR.** See "Cross-repo SPIs" below for the SPIs that span multiple repos.

```java
// BEFORE
public interface EmbeddingBackend {
    Uni<Boolean> supports(String servingName);
    Uni<List<float[]>> embed(String servingName, List<String> texts);
}
// AFTER
public interface EmbeddingBackend {
    boolean supports(String servingName);
    List<float[]> embed(String servingName, List<String> texts);
}
```

### E. `@Scheduled` health probe doing `.await().atMost(...)`

```java
// BEFORE
@Scheduled(every = "10s")
void probe() { client.health().await().atMost(Duration.ofSeconds(2)); }
// AFTER
@Scheduled(every = "10s")
@RunOnVirtualThread
void probe() { client.health(); }   // method MUST return void
```

## Where `@RunOnVirtualThread` is valid

- gRPC `@GrpcService` methods (unary and streaming) ✓
- REST endpoints where `@Blocking` would be valid ✓
- `@Scheduled` (method must return `void`) ✓
- Reactive messaging consumers — implies `@Blocking`; do not mix with non-blocking pipelines that expect event-loop affinity

## Forbidden patterns (in new code)

- `.await()` / `.await().atMost(...)` / `.await().indefinitely()` anywhere outside legacy code on its way out
- `.subscribe().asCompletionStage().get()`
- `CompletableFuture.get()` / `CompletableFuture.join()` on a request path — use the blocking call directly
- `Thread.sleep(...)` is fine in test code or on a VT; do not use it on the event loop (you should not be on the event loop in new code)
- Handwritten `Executors.newFixedThreadPool(...)` — Quarkus already manages a VT-friendly pool
- `synchronized` blocks/methods that wrap I/O — these **pin the carrier thread** on Java 21–23. Replace with `java.util.concurrent.locks.ReentrantLock`. (Java 24 removes the pinning issue; until the platform is on 24+, treat it as a hard rule.)
- `ThreadLocal` written in a CDI-scoped path expected to read from a different thread — VTs propagate Quarkus's duplicated context but **not** plain `ThreadLocal`s. Use `@RequestScoped` beans instead.

## Pinning detection

Add the test dep:

```gradle
testImplementation 'io.quarkus:quarkus-junit5-virtual-threads'
```

And mark VT-handled tests:

```java
@QuarkusTest
@VirtualThreadUnit
@ShouldNotPin
class FooTest { ... }
```

For a JVM-level catch in CI, add `-Djdk.tracePinnedThreads` to `argLine` on Java 21–23. (The flag is removed on 24+; rely on `@ShouldNotPin` for the long term.)

## Testing

Tests now call sync methods directly. The historical "single place `.await()` is allowed" carve-out is no longer needed — test code calls the sync method:

```java
@Test
void loadsPipeDocById() {
    PipeDoc doc = repository.findById("pd-123");      // blocking, no .await()
    assertThat(doc.getTitle()).isEqualTo("expected");
}
```

For genuinely async assertions (waiting on a scheduled probe to converge, etc.), use **Awaitility**, not `.await().atMost(...)`:

```java
await().atMost(Duration.ofSeconds(5)).until(() -> registry.isReady("minilm"));
```

## CDI + transactions

- `@RequestScoped` beans work — Quarkus propagates the duplicated context onto the VT.
- `@Transactional` composes fine: the interceptor runs on the VT and JDBC blocking is exactly what VTs are for. Do **not** mix `@Transactional` with `Uni`-returning methods during migration; finish converting the return type to sync first.
- Pool tuning: once a service is fully on VTs, `quarkus.thread-pool.max-threads` becomes irrelevant for VT-handled work.

## Streaming

Server-streaming gRPC methods still return `Multi<T>`. Until the engine ships a synchronous streaming API, the body of a streaming method may still need to use Mutiny for backpressure and emission. When you write one:

- Prefer `Multi.createFrom().items(...)` over emitter-based constructions when you have a finite list.
- Don't buffer unbounded with `.onOverflow().buffer(Integer.MAX_VALUE)` — you'll OOM.
- Do not call `.await()` inside the lambda passed to `transformToUni` — same pinning trap as `synchronized`.

A future revision of this doc will cover the canonical streaming-on-VT pattern once it's pinned down in the engine.

## Cross-repo SPIs that block incremental migration

Some SPIs have implementations and callers in different repos. Migrating them requires coordinated PRs across multiple repos in the same merge window. Currently identified:

- **`EmbeddingBackend`** in `module-embedder/module-embedder-api` → impls in `pipestream-embedder-openvino`, `pipestream-embedder-djl`; callers in `module-embedder`.
- **All proto-generated services in `pipestream-protos`** — Mutiny stubs are generated for every consumer. Switching the generator output to blocking-only stubs (or adding both) is a `pipestream-protos` change with downstream rebuild on every consumer.

When in doubt, grep for `import io.smallrye.mutiny.Uni;` in every consumer of the SPI before opening the PR.

## Migration order recommendation

When converting a single file or service:

1. Flip leaf SPI / REST-client signatures from `Uni<T>` → `T`.
2. Convert call sites in `@Scheduled` and `@GrpcClient` users.
3. Add `@RunOnVirtualThread` to the gRPC service methods and REST endpoints those callers reach from.
4. Run the `@ShouldNotPin` test wrapper under `-Djdk.tracePinnedThreads`.
5. Delete dead Mutiny imports.

When ordering by repo, weigh blast radius (lines/tests changed) against muscle memory (smaller services teach the team the pattern). The platform team's preference is heaviest-first — proves the pattern on the risky code while the migration is still fresh in everyone's head.

## References

Quarkus guides (pin to Quarkus 3.31+; older versions of these guides differ in detail):

- https://quarkus.io/guides/virtual-threads
- https://quarkus.io/guides/rest-virtual-threads
- https://quarkus.io/guides/grpc-virtual-threads
- https://quarkus.io/guides/grpc-service-consumption
- https://quarkus.io/guides/scheduler-reference

Related standards:

- [`08-java-code-style.md`](08-java-code-style.md) — package layout, CDI scopes, javadoc style, exception handling
- [`05-testing.md`](05-testing.md) — `@QuarkusTest` patterns, integration test naming
- [`07-build-versions.md`](07-build-versions.md) — Java 21 baseline, Quarkus version pinning
