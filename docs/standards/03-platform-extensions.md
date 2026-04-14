# 03 — pipestream-platform extensions

This is the reference page for the Quarkus extensions shipped by `pipestream-platform`. The purpose of the whole platform module is that downstream projects stop writing scaffolding — they pull in an extension, and the extension does the wiring.

All extensions are added to a project with:

```groovy
dependencies {
    implementation platform("ai.pipestream:pipestream-bom:${pipestreamBomVersion}")
    implementation 'ai.pipestream:<extension-name>'
}
```

No versions. The BOM handles them.

## Which extensions does a typical service need?

**Any backend service:**

```groovy
implementation 'ai.pipestream:pipestream-server'
implementation 'ai.pipestream:pipestream-service-registration'
implementation 'ai.pipestream:quarkus-dynamic-grpc'
implementation 'ai.pipestream:pipestream-quarkus-devservices'
```

**A service that produces/consumes Kafka protobuf messages:**

```groovy
implementation 'ai.pipestream:quarkus-apicurio-registry-protobuf'
```

**A service that handles dynamic protobuf types:**

```groovy
implementation 'ai.pipestream:pipestream-descriptor-apicurio'
```

**Test dependencies (always):**

```groovy
testImplementation 'ai.pipestream:pipestream-test-support'
```

---

## `quarkus-apicurio-registry-protobuf`

**What it gives you:** Every Kafka channel carrying a Protobuf message type is auto-configured with `ProtobufKafkaSerializer` / `PipestreamProtobufDeserializer`, schemas are auto-registered in Apicurio, and UUID-key enforcement is wired via `ProtobufKafkaHelper` and `UuidKeyExtractorRegistry`.

**Key config (`quarkus.apicurio-registry.protobuf.*`):**

| Property | Default | Notes |
|----------|---------|-------|
| `deriveClass` | `true` | Load proto classes via TCCL — fixes Quarkus classloader quirks |
| `autoRegister` | `true` | Register schemas on first publish |
| `artifactResolverStrategy` | `SimpleTopicIdStrategy` | Artifact ID derived from Kafka topic |
| `findLatest` | `true` | Deserializer resolves to the latest artifact version |
| `explicitGroupId` | *(unset)* | Override Apicurio group ID |

**SPI:**

- `UuidKeyExtractor<T extends Message>` — implement per protobuf type to provide a deterministic UUID key
- `@ProtobufChannel` — qualifier for injecting channels with the extension's wiring applied
- `ProtobufKafkaHelper` — inject and use `send(emitter, key, message)`; enforces UUID keys at the API level
- `ProtobufEmitter` — `Emitter`-compatible abstraction scoped to Protobuf types

**Non-negotiable:** this extension enforces PROTOBUF + UUID. See [`01-protobufs-apicurio-grpc.md`](01-protobufs-apicurio-grpc.md) for the rules and anti-patterns.

---

## `pipestream-quarkus-devservices`

**What it gives you:** A compose file (`compose-devservices.yml`) is extracted to `~/.pipeline/` at build time. Quarkus DevServices is kept ON, but the extension tells it not to stop containers on app shutdown so a shared compose project can own them across services.

**Key build-time config (`quarkus.pipeline-devservices.*`):**

| Property | Default | Notes |
|----------|---------|-------|
| `enabled` | `true` | Enable the extension |
| `target-dir` | `~/.pipeline` | Where the compose file is extracted |
| `project-name` | *(unset)* | Compose project name override |

**Runtime config (`quarkus.pipeline-devservices.infisical.*`)** for the Infisical admin auto-setup used in dev mode. Defaults are fine unless you've changed Infisical credentials.

**Hard-coded behavior to know about:**

- `DEFAULT_STOP_SERVICES = false` (`PipelineDevServicesProcessor.java:45`) — never tear down compose containers
- `DEFAULT_REUSE_PROJECT_FOR_TESTS = true` (line 46)
- `quarkus.devservices.launch-on-shared-network=true` is set at runtime so Quarkus joins the compose bridge network
- Apicurio/Consul/Kafka URLs are discovered via `ComposeLocator` — **don't set them manually in `%dev`**

See [`04-devservices-compose.md`](04-devservices-compose.md) for the full dev-vs-test story.

---

## `quarkus-dynamic-grpc`

**What it gives you:** A `GrpcClientFactory` that resolves service names through Consul/Stork and caches channels. You never construct `ManagedChannel`s by hand.

**Key config (`quarkus.dynamic-grpc.*`):**

Channel:

| Property | Default | Notes |
|----------|---------|-------|
| `channel.idle-ttl-minutes` | `15` | Cache eviction TTL |
| `channel.max-size` | `1000` | Max cached channels |
| `channel.shutdown-timeout-seconds` | `2` | |
| `channel.max-inbound-message-size` | `2147483647` (2 GB) | Large payload support |
| `channel.max-outbound-message-size` | `2147483647` (2 GB) | |
| `channel.deadline-ms` | `15000` | gRPC call deadline |

TLS:

| Property | Default | Notes |
|----------|---------|-------|
| `tls.enabled` | `false` | |
| `tls.trust-all` | `false` | Dev only — reviewer must flag any `true` in `%prod` |
| `tls.trust-certificate-pem.certs` | *(unset)* | PEM file paths |
| `tls.key-certificate-pem.*` | *(unset)* | mTLS |
| `tls.verify-hostname` | `true` | |

Auth:

| Property | Default | Notes |
|----------|---------|-------|
| `auth.enabled` | `false` | |
| `auth.header-name` | `Authorization` | |
| `auth.scheme-prefix` | `Bearer ` | |

Consul:

| Property | Default | Notes |
|----------|---------|-------|
| `consul.host` | `localhost` | |
| `consul.port` | `8500` | |
| `consul.refresh-period` | `10s` | |
| `consul.use-health-checks` | `false` | Flip to `true` once health checks stabilize across the fleet |

**SPI:**

- `GrpcClientFactory` — inject and call `create(serviceName, mutinyStubClass)` to get a Mutiny stub
- `ServiceDiscovery` / `ServiceDiscoveryProducer` — implement for custom discovery backends
- `AuthTokenProvider` — implement to supply bearer tokens dynamically

---

## `pipestream-service-registration`

**What it gives you:** Automatic registration with Consul on startup, health check registration, re-registration on reconnect, and a `%test` escape hatch that disables registration.

**Key config (`pipestream.registration.*`):**

Top-level:

| Property | Default | Notes |
|----------|---------|-------|
| `enabled` | `true` | |
| `mode` | `direct` | `direct` (Consul) or `grpc` (legacy, avoid) |
| `required` | `false` | Fail startup on registration failure |
| `required-timeout` | `10m` | |
| `service-name` | *(fallback: `quarkus.application.name`)* | |
| `type` | `SERVICE` | One of `SERVICE`, `MODULE`, `CONNECTOR` — choose based on what the project actually is |
| `version` | *(fallback: `quarkus.application.version`)* | |

Advertised vs. internal addressing:

| Property | Default | Notes |
|----------|---------|-------|
| `advertised-host` | `0.0.0.0` | Client-facing address |
| `advertised-port` | *(fallback: Quarkus gRPC port)* | |
| `internal-host` | *(unset)* | Actual bind in Docker/K8s |
| `internal-port` | *(unset)* | |

Retry + re-registration:

| Property | Default |
|----------|---------|
| `retry.max-attempts` | `5` |
| `retry.initial-delay` | `1s` |
| `retry.max-delay` | `30s` |
| `retry.multiplier` | `2.0` |
| `re-registration.enabled` | `true` |
| `re-registration.interval` | `30s` |

HTTP health registration:

| Property | Default |
|----------|---------|
| `http.enabled` | `true` |
| `http.health-path` | `/q/health` |
| `http.scheme` | `http` |
| `http.tls-enabled` | `false` |

**Standard `%test` pattern:**

```properties
%test.pipestream.registration.enabled=false
```

Tests do not register with a real Consul — the `@QuarkusTestResource(ConsulTestResource.class)` fixture doesn't pretend to be the production registry.

---

## `pipestream-server`

**What it gives you:** Opinionated HTTP/gRPC server defaults, three health checks auto-registered (gRPC readiness, HTTP readiness, liveness), a build-info REST endpoint at `/api/meta/build`, and an admin auth fallback filter.

**Config (`pipestream.server.*`, `pipestream.server.health.*`, `pipestream.security.*`):**

| Property | Default | Notes |
|----------|---------|-------|
| `pipestream.server.class` | `core` | Server class identifier |
| `pipestream.server.capabilities` | *(unset)* | Advertised capabilities |
| `pipestream.server.host-mode` | `auto` | |
| `pipestream.server.http2.connection-window-size` | *(unset)* | HTTP/2 tuning |
| `pipestream.server.health.enabled` | `true` | Enable all health checks |
| `pipestream.server.health.grpc.enabled` | `true` | |
| `pipestream.server.health.http.enabled` | `true` | |
| `pipestream.security.admin-fallback-enabled` | `false` | Security-first default |

**Do not disable the health checks.** The service-registration extension uses them to decide whether the service is actually ready, and Consul won't mark us alive without them.

---

## `pipestream-test-support`

**What it gives you:** Pre-built `@QuarkusTestResource` implementations and test profiles so you don't hand-roll Testcontainers fixtures in every project.

**Test resources:**

- `ConsulTestResource` — starts a Consul container
- `OpensearchContainerTestResource` — OpenSearch container
- `S3TestResource` / `S3WithSampleDataTestResource` — `moto` S3 container
- `ConnectorAdminWireMockTestResource` — mocks the connector admin service
- `ConnectorIntakeWireMockTestResource` — mocks the connector intake service
- `EngineWireMockTestResource` — mocks the pipeline engine
- `RepositoryWireMockTestResource` — mocks the repository service
- `OpenSearchSinkWireMockTestResource` — mocks the opensearch sink module
- `IsolatedKafkaTopicsProfile` — `@TestProfile` that gives each test class its own Kafka topics

**Standard usage:**

```java
@QuarkusTest
@QuarkusTestResource(ConsulTestResource.class)
@QuarkusTestResource(RepositoryWireMockTestResource.class)
class MyServiceIT {
    @Inject MyService service;

    @Test
    void scenario() {
        // ...
    }
}
```

**Rule:** if a fixture exists in `pipestream-test-support`, use it. Don't hand-write a Testcontainers `@QuarkusTestResourceLifecycleManager` in your service for a case that's already covered. If the fixture is missing, add it to `pipestream-test-support` in the same PR.

---

## `pipestream-descriptor` (api + apicurio)

**What it gives you:** A runtime registry of Protobuf `FileDescriptor`s with pluggable loaders. Used by services that need to handle dynamic protobuf types at runtime (a generic transformer that accepts any pipedoc schema, a debug UI inspecting Kafka messages, etc.).

**Config (`pipestream.descriptor.apicurio.*`):**

| Property | Default |
|----------|---------|
| `enabled` | `true` |
| `registry-url` | *(unset — discovered)* |
| `group-id` | `default` |
| `auto-load-on-startup` | `false` |

Leave `auto-load-on-startup` false unless you need all descriptors present at boot — on-demand loading is cheaper.

**SPI:**

- `DescriptorRegistry` — inject and call `findDescriptorByFullName(String)`, `register(Descriptor)`, `autoLoadDescriptors()`
- `DescriptorLoader` — implement for custom descriptor sources (classpath, S3, etc.) and expose via `ServiceLoader`

Google well-known types (`Timestamp`, `Duration`, `Struct`, `Any`, `Empty`, etc.) are pre-registered; you don't need to load them.
