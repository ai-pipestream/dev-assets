# 01 — Protobufs, Apicurio, and gRPC

This is the longest file in the standards directory because it covers the three things most often done wrong: how protos are pulled into a project, how Apicurio is configured, and how gRPC services are exposed. If you're starting a new project, read this file end-to-end.

## Proto workflow

### Where protos live

Every `.proto` file is in [`pipestream-protos`](../../../core-projects/pipestream-protos). Never in a service or module repo. See [`00-source-of-truth.md`](00-source-of-truth.md) for the rule.

### How a consumer pulls them: `quarkus-buf-grpc-generator`

We have a custom Gradle plugin (`ai.pipestream:quarkus-buf-grpc-generator`, also registered as `id 'ai.pipestream.proto-toolchain'`) that does everything the built-in Quarkus gRPC codegen would do, *and* fetches protos from the Buf Schema Registry or a git workspace, *and* generates Mutiny stubs, *and* produces descriptor sets. It explicitly **disables** Quarkus's built-in gRPC codegen to avoid duplicate classes.

Standard consumer configuration in a project's `build.gradle`:

```groovy
plugins {
    id 'java'
    alias(libs.plugins.quarkus)
    alias(libs.plugins.proto.toolchain)  // the pipestream plugin
    alias(libs.plugins.axion.release)
}

pipestreamProtos {
    sourceMode = 'git-proto-workspace'
    gitRepo = "https://github.com/ai-pipestream/pipestream-protos.git"
    gitRef = "main"
    generateMutiny = true
    generateDescriptors = true

    modules {
        register("common")
        register("pipeline-module")
        register("registration")   // add whichever modules you actually need
    }
}
```

**Defaults to rely on, not override:**

- `generateMutiny = true` — we always want Mutiny stubs. Don't disable.
- `generateDescriptors = true` — the `.pb` descriptor set ends up in test resources and is consumed by `pipestream-wiremock-server`. Don't disable.
- `sourceMode = 'git-proto-workspace'` — pulls from the `pipestream-protos` git repo directly. The alternative is BSR, which is fine for experiments but adds a BSR auth dependency.

### Branch-based proto experimentation is encouraged

When you need to change a proto (add a field, add an RPC, prototype a new service) you do **not** have to merge to `pipestream-protos` `main` first. Cut a branch in `pipestream-protos`, push it, and point the consuming project at that branch by changing `gitRef` in its `pipestreamProtos { }` block:

```groovy
pipestreamProtos {
    sourceMode = 'git-proto-workspace'
    gitRepo    = "https://github.com/ai-pipestream/pipestream-protos.git"
    gitRef     = "feature/platform-registration-add-health-rpc"   // your branch
    // ...
}
```

The `quarkus-buf-grpc-generator` plugin re-fetches on every build, so iterating is just `git push` in the proto repo followed by `./gradlew build` in the consumer. Once the proto change is reviewed, merge it to `main` and bump `gitRef` back to `"main"` in the same PR that lands the consumer code.

Rules for this workflow:

- **Branch names should be scoped**, e.g. `feature/<service>-<what>`, so it's obvious from the consumer's `build.gradle` what proto branch is being pinned and why.
- **Never merge consumer code that still points at a feature branch.** CI on the consumer should fail the build if `gitRef != "main"` on a release branch.
- **Breaking changes still run through `buf breaking`.** The branch workflow is for iterating quickly, not for skipping the contract check.
- **When iterating, commit+push protos from a real branch — don't use `gitRef = "HEAD"` or a shallow SHA that can't be recreated later.** Reviewers need to be able to check out the exact protos your PR was built against.

The plugin handles:

- Downloading `protoc`, `protoc-gen-grpc-java`, and the Quarkus gRPC codegen plugin
- Running `buf generate` with our standard `buf.gen.yaml`
- Building `services.dsc` descriptor files
- Copying descriptors into `src/test/resources` for wiremock consumption
- Linting, formatting, and breaking-change checks

**What you should not do:**

- Don't use the built-in Quarkus gRPC codegen — our plugin disables it on purpose
- Don't check `.proto` files into a consuming project
- Don't hand-edit generated Java

## Apicurio Registry — always PROTOBUF, always deterministic UUIDs

This is the section LLMs get wrong most often. Apicurio Registry on this platform is configured for Protobuf schemas, and Kafka record keys are deterministic UUIDs. The `quarkus-apicurio-registry-protobuf` extension wires all of this automatically — you should not be writing Kafka serde config by hand.

### What the extension does for you

Add this to `build.gradle`:

```groovy
implementation 'ai.pipestream:quarkus-apicurio-registry-protobuf'
```

And the extension:

1. Auto-configures every `@Incoming`/`@Outgoing` channel carrying a Protobuf message type with:
   - `value.serializer = io.apicurio.registry.serde.protobuf.ProtobufKafkaSerializer`
   - `value.deserializer = ai.pipestream.apicurio.runtime.PipestreamProtobufDeserializer` (a subclass of the Apicurio deserializer that fixes Quarkus classloader quirks and falls back to direct protobuf parsing on registry hiccups)
2. Registers `ProtobufKafkaHelper`, `ProtobufEmitter`, and `UuidKeyExtractorRegistry` as CDI beans
3. Forces `apicurio.registry.auto-register=true` and `find-latest=true` by default
4. Uses `SimpleTopicIdStrategy` for artifact IDs (derived from the Kafka topic name)

You do **not** write any of this in `application.properties`. The only thing you typically set is the topic name if it differs from the channel name:

```properties
mp.messaging.outgoing.ingest-out.topic=ingest-protobuf-topic
mp.messaging.incoming.ingest-in.topic=ingest-protobuf-topic
```

### Never default to JSON

Do not suggest, configure, or auto-generate any of the following:

- `quarkus.kafka.snappy.enabled` plus a `JsonObject` serializer
- `@JsonbProperty` / `@JsonProperty` on Kafka payload classes
- `StringSerializer` or `JsonSerializer` in `application.properties`
- `artifactType=JSON` or `artifactType=AVRO` in Apicurio config
- "JSON for quick prototyping, protobuf later" — we do not do this

If a feature requires JSON (e.g. a webhook body from an external source), you deserialize the JSON **into a protobuf** before it hits a Kafka topic. The Kafka topic is always Protobuf.

### UUID keys — `UuidKeyExtractor`

All Kafka records use UUID keys. The UUID must be deterministic — derived from message content, external IDs, or UUIDv5 of a business-meaningful field. Random UUIDs break idempotency and compaction.

Implement the extractor for your message type:

```java
@ApplicationScoped
public class PipeDocKeyExtractor implements UuidKeyExtractor<PipeDoc> {
    @Override
    public UUID extractKey(PipeDoc message) {
        // Deterministic: UUIDv5 from the document's logical ID
        return UUIDv5.fromString(NAMESPACE_PIPEDOC, message.getLogicalId());
    }
}
```

Then produce via `ProtobufKafkaHelper` (which enforces UUID keys at the API level) or via an injected `ProtobufEmitter`:

```java
@Inject
ProtobufKafkaHelper kafkaHelper;

@Inject @Channel("ingest-out")
Emitter<PipeDoc> emitter;

public void send(PipeDoc doc) {
    kafkaHelper.send(emitter, doc, new PipeDocKeyExtractor());
    // or, with an explicit key:
    // kafkaHelper.send(emitter, UUID.fromString(...), doc);
}
```

**Anti-patterns to flag in review:**

- `@Inject Emitter<PipeDoc> emitter; emitter.send(doc);` — bypasses the UUID key extractor. Use `ProtobufKafkaHelper`.
- Implementing `UuidKeyExtractor<T>` and returning `UUID.randomUUID()` — defeats the purpose. We have `RandomUuidKeyExtractor` as a diagnostic fallback that logs a loud warning; it is not a template.
- `Emitter<Record<String, PipeDoc>>` — the key type is always `UUID` on this platform.

### Well-known descriptor loading

If a service needs to handle dynamic Protobuf types at runtime (e.g. a generic transformer that accepts any pipedoc schema), use `pipestream-descriptor`:

```java
@Inject DescriptorRegistry descriptorRegistry;

Descriptor descriptor = descriptorRegistry.findDescriptorByFullName(
    "ai.pipestream.data.v1.PipeDoc"
).orElseThrow();
```

`pipestream-descriptor-apicurio` auto-loads descriptors from Apicurio on demand. Turn on `pipestream.descriptor.apicurio.auto-load-on-startup=true` only if you genuinely need all descriptors present at boot.

## gRPC — the primary transport

### gRPC-first rule

Services communicate over gRPC. We do not write REST as a default. If you catch yourself typing `@Path` in a new service, stop.

**The one exception:** modules (chunker, parser, etc.) may expose a small REST wrapper at `/api/<module>/process` whose only job is to call the gRPC impl. These exist so developers can `curl` a dev instance for quick inspection. They are not to be used by other services.

### Standard server config

Every service running the `pipestream-server` extension gets these defaults:

```properties
# gRPC shares the HTTP port — no separate port
quarkus.grpc.server.use-separate-server=false
quarkus.grpc.codegen.skip=false    # but note: our proto-toolchain plugin owns codegen

# 2 GB message limits for large payload support
quarkus.grpc.server.max-inbound-message-size=2147483647
quarkus.grpc.server.max-outbound-message-size=2147483647

# Standard HTTP port per service (see 07-build-versions.md for port allocations)
quarkus.http.port=18101    # platform-registration-service; each service has its own
```

The 2 GB limit is load-bearing — ML embeddings and chunked document streams run large. Don't lower it.

### gRPC patterns in use

We use all four gRPC patterns. Pick the right one:

- **Unary** — simple request/response. Default pick. Example: `AccountService.GetAccount(request) → response`.
- **Server streaming** — long-running operation with progress events. Example: `PlatformRegistrationService.Register(request) → stream<RegistrationEvent>`, which emits STARTED → VALIDATED → APICURIO_REGISTERED → CONSUL_REGISTERED → COMPLETED.
- **Client streaming** — bulk upload of chunks with a single summary response. Example: `NodeUploadService.NodeUpload(stream<Chunk>) → UploadResponse`.
- **Bidirectional streaming** — both sides stream independently. Used rarely; justify in the PR.

For the implementation details and error-handling patterns, see [`../reference/grpc/GRPC_Communication_Patterns.md`](../reference/grpc/GRPC_Communication_Patterns.md). It's the authoritative doc for "how to write these".

### Service implementation skeleton

```java
@GrpcService
public class AccountServiceImpl extends MutinyAccountServiceGrpc.AccountServiceImplBase {

    @Inject AccountRepository repository;

    @Override
    public Uni<GetAccountResponse> getAccount(GetAccountRequest request) {
        return repository.findById(request.getId())
            .onItem().ifNull().failWith(() -> Status.NOT_FOUND
                .withDescription("account " + request.getId() + " not found")
                .asRuntimeException())
            .onItem().transform(account -> GetAccountResponse.newBuilder()
                .setAccount(account.toProto())
                .build());
    }
}
```

Rules:

- Extend the generated Mutiny base class (`Mutiny<Service>Grpc.<Service>ImplBase`), never the blocking base class.
- Return `Uni<T>` for unary, `Multi<T>` for server-streaming. See [`02-mutiny-non-blocking.md`](02-mutiny-non-blocking.md).
- Fail with `Status.*.asRuntimeException()`. Never return an HTTP status code. Never throw arbitrary exceptions.
- Do not add `@Blocking` unless the method genuinely has CPU-bound work. Then see `02-mutiny-non-blocking.md` for how to offload correctly.

### Calling other services — dynamic gRPC

For service-to-service calls, use `quarkus-dynamic-grpc`, not static `@GrpcClient`. It discovers services through Consul (via Stork) and caches channels. See the section in [`03-platform-extensions.md`](03-platform-extensions.md) for configuration options.

Simplified example:

```java
@Inject GrpcClientFactory grpcClientFactory;

public Uni<Account> fetchAccount(String id) {
    MutinyAccountServiceGrpc.MutinyAccountServiceStub stub =
        grpcClientFactory.create("account-service", MutinyAccountServiceGrpc.MutinyAccountServiceStub.class);
    return stub.getAccount(GetAccountRequest.newBuilder().setId(id).build())
        .onItem().transform(GetAccountResponse::getAccount);
}
```

Never hand-write a `ManagedChannelBuilder.forAddress(...)` — it bypasses discovery, TLS policy, and channel pooling.
