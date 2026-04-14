# 02 — Mutiny and non-blocking

Every service on this platform is non-blocking by default. The service loop is Vert.x, which means a blocked event-loop thread is a latency spike for every other request on the process.

## The core rule

**Service methods return `Uni<T>` or `Multi<T>`. Never blocking types.**

That means gRPC service impls, REST endpoints, Kafka consumers, scheduled jobs, and any CDI bean method called from a request path. It also means the body of those methods composes reactively with `.map()`, `.flatMap()`, `.onItem()`, `.onFailure()` — not with `.await()`.

### Good — returning Uni/Multi, composing reactively

```java
@Override
public Uni<ProcessDataResponse> processData(ProcessDataRequest request) {
    return documentLoader.load(request.getDocumentId())
        .onItem().transformToUni(doc -> chunker.chunk(doc))
        .onItem().transform(chunks -> ProcessDataResponse.newBuilder()
            .addAllChunks(chunks)
            .build())
        .onFailure(NotFoundException.class).recoverWithItem(
            ProcessDataResponse.newBuilder().setError("not found").build());
}
```

### Bad — `.await()` on the request path

```java
// NEVER do this in production code:
public ProcessDataResponse processData(ProcessDataRequest request) {
    var doc = documentLoader.load(request.getDocumentId()).await().atMost(Duration.ofSeconds(5));
    return buildResponse(doc);
}
```

`.await().atMost(...)` blocks the current thread until the `Uni` resolves. On the event loop, this deadlocks Vert.x. On a worker thread, it wastes a whole worker waiting on I/O.

### The one place `.await()` is allowed

Inside a `@QuarkusTest`. Test code has no event loop to starve, and assertions often read cleaner when the test is synchronous:

```java
@Test
void loadsPipeDocById() {
    PipeDoc doc = repository.findById("pd-123")
        .await().atMost(Duration.ofSeconds(2));
    assertThat(doc.getTitle()).isEqualTo("expected");
}
```

Outside of tests, `.await()` is a review blocker.

## Forbidden patterns

None of these should appear in new code. If you see them in existing code, flag them.

- `.await()` / `.await().atMost(...)` / `.await().indefinitely()` on a request path
- `.subscribe().asCompletionStage().get()` — blocks just as hard
- `CompletableFuture.get()` / `CompletableFuture.join()` on a request path
- `Thread.sleep(...)` anywhere in service code. For delays, use `Uni.createFrom().item(...).onItem().delayIt().by(Duration...)`.
- Handwritten `Executors.newFixedThreadPool(...)` — see "offloading blocking work" below for the right way
- `synchronized` on a method that returns `Uni<T>` — the semantics are wrong
- `ThreadLocal` that is read or written across `.flatMap()` boundaries — Mutiny doesn't propagate it; use `Context` or `@RequestScoped` beans

## Offloading genuinely blocking work

Some work is inherently blocking: Tika parsing, JDBC drivers without reactive variants, file I/O against spinning disks, `java.util.zip`, shelled-out processes. For these, you have two tools.

### 1. `@Blocking` for method-level offloading

On a gRPC service method or REST endpoint, marking it `@Blocking` tells Quarkus to run the call on a worker thread instead of the event loop:

```java
@Override
@Blocking
public Uni<ParseResponse> parse(ParseRequest request) {
    // Tika is blocking; this whole method now runs on a worker thread.
    String text = tika.parseToString(request.getBytes().newInput());
    return Uni.createFrom().item(ParseResponse.newBuilder().setText(text).build());
}
```

Real example: `platform-registration-service`'s `PlatformRegistrationService.register(RegisterRequest)` is `@Blocking` because it sequences Apicurio schema registration calls that are not reactive.

`@Blocking` is coarse — the entire method runs on the worker pool. Fine for methods that are "mostly blocking".

### 2. `Infrastructure.getDefaultWorkerPool()` for inline offloading

When only part of a reactive chain is blocking, offload the blocking chunk explicitly:

```java
return documentLoader.load(id)   // reactive
    .emitOn(Infrastructure.getDefaultWorkerPool())   // move to worker
    .onItem().transform(doc -> tika.parse(doc))      // blocking work, on worker
    .emitOn(Infrastructure.getDefaultExecutor())     // move back to event loop
    .onItem().transform(text -> buildResponse(text));
```

Don't allocate a new `ExecutorService`. Use `Infrastructure.getDefaultWorkerPool()`, which Quarkus sizes and monitors for us.

## Streaming — `Multi`

For server-streaming gRPC methods or fan-out Kafka reads, use `Multi`:

```java
@Override
public Multi<RegistrationEvent> register(RegisterRequest request) {
    return Multi.createFrom().emitter(emitter -> {
        emitter.emit(event("STARTED"));
        // ...compose with upstream Unis/Multis...
        emitter.complete();
    });
}
```

Prefer combining existing `Multi`/`Uni` instances with `.onItem().transformToMulti(...)`, `.concatMap(...)`, `.merge()` over hand-rolling emitters. Emitters are escape hatches for integrating callback-based libraries.

## Error handling

- Recover with `.onFailure(SpecificException.class).recoverWithItem(...)` or `.recoverWithUni(...)`. Catch only what you can actually handle.
- Let unexpected failures propagate. Quarkus's gRPC runtime translates them to `Status.INTERNAL`.
- For known gRPC errors, fail with `Status.*.asRuntimeException()` directly (see [`01-protobufs-apicurio-grpc.md`](01-protobufs-apicurio-grpc.md)).
- Avoid `.onFailure().invoke(log::error)` as a replacement for real recovery — it still fails, just louder.

## Backpressure

`Multi` respects backpressure. Use it. When bridging a Kafka consumer to a downstream gRPC server-streaming call, let the downstream's demand signal drive the upstream pull rate. Don't buffer unbounded via `.onOverflow().buffer(Integer.MAX_VALUE)` — you'll OOM.

## A known uncomfortable truth

Some existing module code uses `Uni.createFrom().item(() -> blockingCall())` without offloading. That runs the blocking work on whatever thread `createFrom().item()` was subscribed on — typically the event loop for gRPC requests. This is a latent bug. If you touch such a file, convert it to `@Blocking` or an explicit `emitOn(workerPool)`. Don't perpetuate the pattern in new code.
