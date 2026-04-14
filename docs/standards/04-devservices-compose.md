# 04 — DevServices and compose

This is one of the two files LLMs get wrong most often (the other is `01-protobufs-apicurio-grpc.md`). The short version: **Quarkus DevServices is always on**. What it's talking to depends on the profile.

## The rule in one sentence

In `%dev`, DevServices is on *and* the compose plugin is on, and the `pipestream-quarkus-devservices` extension is wired so DevServices yields ownership of the containers to compose. In `%test`, DevServices is on *and* compose is off — tests use standard Testcontainers-backed DevServices through `pipestream-test-support` fixtures. **Never turn DevServices off in either profile.**

## The two profiles

### `%dev` — devservices on + compose on, compose owns containers

This is the pattern the platform is moving toward. The `pipestream-quarkus-devservices` extension in `pipestream-platform/pipestream-quarkus-devservices` hard-codes the behavior:

```java
// PipelineDevServicesProcessor.java
private static final boolean DEFAULT_STOP_SERVICES = false;       // line 45
private static final boolean DEFAULT_REUSE_PROJECT_FOR_TESTS = true;  // line 46
```

`DEFAULT_STOP_SERVICES = false` tells Quarkus DevServices not to kill compose-owned containers when a single Quarkus app shuts down. That's the behavior you need when half a dozen services on a dev machine are sharing one Kafka instance, one Consul, and one Apicurio — you don't want one service exiting to take down the others.

At runtime, the extension sets:

- `quarkus.devservices.launch-on-shared-network=true` — Quarkus joins the compose bridge network
- Apicurio Registry URL is *not* set explicitly; it's discovered via `ComposeLocator` at runtime
- Kafka bootstrap, Consul, OpenSearch, OTLP URLs — same deal, discovered from the compose project

**What a service's `application.properties` looks like in `%dev`:**

```properties
%dev.quarkus.devservices.enabled=true
%dev.quarkus.compose.devservices.enabled=true

# Example platform-registration-service — reactive datasource
%dev.quarkus.datasource.reactive.url=postgresql://localhost:5432/platform_registration
%dev.kafka.bootstrap.servers=localhost:9094

# Do NOT set apicurio.registry.url in %dev — the extension discovers it
# Do NOT set consul.host in %dev beyond the default localhost:8500
```

Notice what's *not* there: no manual Apicurio URL, no container IP addresses, no shared-network opt-ins. The extension handles it.

**In-flight caveat.** As of April 2026 the `%dev` + compose story is still being refined across services. Not every project is fully on the pattern. When you touch `%dev` config in an older service, migrate it toward this pattern, don't propagate the older manual overrides. Kristian has flagged this as the next area of focus after these standards settle.

### `%test` — devservices on, compose off, Testcontainers only

Tests on this platform **do not use compose**. They use standard Quarkus DevServices and `@QuarkusTestResource` fixtures from `pipestream-test-support`. The standard setup in a service's `application.properties`:

```properties
%test.quarkus.devservices.enabled=true
%test.quarkus.compose.devservices.enabled=false

# If the service needs kafka tests:
%test.quarkus.kafka.devservices.enabled=true

# Service registration is disabled in tests — ConsulTestResource is per-test:
%test.pipestream.registration.enabled=false
```

And in the test class:

```java
@QuarkusTest
@QuarkusTestResource(ConsulTestResource.class)
class PlatformRegistrationIT { ... }
```

This is the correct pattern. Seeing `%test.quarkus.compose.devservices.enabled=false` in a service is **not** a legacy smell — it's the rule.

**Why the split?** Compose is a shared-infrastructure model (one Kafka across many services on a dev machine). Tests want per-run isolation so a stray stopped/started state doesn't leak between test classes. Testcontainers-backed DevServices gives you that; compose would not.

**Rule for test-writing:** lean into DevServices. Don't mock infrastructure by hand, don't wire a `GenericContainer` from scratch, don't add `testImplementation("org.testcontainers:kafka")` to the project. Use `@QuarkusTest` + `@QuarkusTestResource` + the fixtures in `pipestream-test-support`. If a fixture is missing, add it to `pipestream-test-support`. See [`05-testing.md`](05-testing.md) for the rest of the test conventions.

## Things LLMs keep getting wrong (do not do these)

1. **"Turn devservices off because compose is running."** No. `pipestream-quarkus-devservices` exists specifically to make them coexist. If something looks broken, fix the config — don't disable devservices.
2. **"Add `%dev.quarkus.compose.devservices.enabled=false` to make devservices happy."** Backwards. In `%dev` you want compose on, not off.
3. **"Add `%test.quarkus.compose.devservices.enabled=true` to match production."** Backwards. Tests don't use compose.
4. **"Set `%dev.apicurio.registry.url=http://localhost:8081` manually."** The extension discovers it. If you're setting it by hand, you're fighting the platform.
5. **"Use Testcontainers directly in `%dev`."** Testcontainers is the `%test` tool. In `%dev`, compose owns infrastructure.

## Related reference

The authoritative guide for what's inside the shared compose file (MySQL, Kafka, Consul, Apicurio, Redis, OpenSearch) and how service discovery works end-to-end is [`../compose-dev-services-guide.md`](../compose-dev-services-guide.md). Read it in full if you're new to the platform.

## Where this intersects with dev containers

When we set up IntelliJ 2026.1 Dev Containers (see Kristian's `platform-registration-service` dev container plan), the pattern is "Quarkus runs inside a devbox container that shares the Docker socket with compose". Compose still owns infrastructure; the devbox is just one more compose-network-attached container. The `%dev` config above doesn't change — from inside the devbox, `localhost:5432` and `localhost:9094` still work because the devbox joins the shared network. This is intentional.
