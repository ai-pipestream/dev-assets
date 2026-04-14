# 05 — Testing

Tests on this platform are `@QuarkusTest` driven, lean on Quarkus DevServices and Testcontainers, and use `pipestream-test-support` fixtures for anything non-trivial. **Do not change how tests are run.** This is a hard rule.

## Test taxonomy

| Type | Suffix | Annotation | Infrastructure | Purpose |
|------|--------|-----------|---------------|---------|
| Unit | `*UnitTest.java` | *(none — plain JUnit 5)* | none | Pure logic, no Quarkus bootstrap |
| Component | `*Test.java` | `@QuarkusTest` | DevServices (in-process) | Single service with its CDI wiring |
| Integration | `*IT.java` | `@QuarkusTest` + `@QuarkusTestResource` | Testcontainers via fixtures | Service + real infrastructure (Consul, OpenSearch, Kafka…) |
| End-to-end | `*E2ETest.java` | `@QuarkusIntegrationTest` | external (docker-integration-tests repo) | Multiple services cooperating |

**Naming matters.** Gradle's `test` task runs `*UnitTest` / `*Test` / `*IT`; `quarkusIntTest` runs `*E2ETest`. Misnamed tests run at the wrong time or not at all.

## The hard rule: don't change how tests run

Tests use docker infrastructure through Quarkus DevServices and `@QuarkusTestResource`. Specifically:

- `%test.quarkus.devservices.enabled=true`
- `%test.quarkus.compose.devservices.enabled=false`
- `%test.pipestream.registration.enabled=false`
- `testImplementation 'ai.pipestream:pipestream-test-support'` for fixtures

This is the pattern. When someone proposes "let's move integration tests to GitHub Actions services" or "let's run tests against compose like dev", push back. The current pattern gives us:

- Per-test isolation (no cross-test container state)
- The same test code working on a laptop, a CI runner, and `krick`
- No extra machinery to debug when a test fails

## Component test: `@QuarkusTest`

```java
@QuarkusTest
class ChunkerServiceTest {

    @GrpcClient("chunker") ChunkerGrpc chunker;

    @Test
    void chunksAPipeDoc() {
        ProcessDataResponse response = chunker
            .processData(ProcessDataRequest.newBuilder().setPipeDoc(samplePipeDoc()).build())
            .await().atMost(Duration.ofSeconds(5));    // .await() is OK inside tests

        assertThat(response.getChunksCount()).isGreaterThan(0);
    }
}
```

Rules:

- `@GrpcClient("name")` injects a Mutiny stub pointed at the in-process gRPC server
- `.await().atMost(...)` is fine in test code, nowhere else (see [`02-mutiny-non-blocking.md`](02-mutiny-non-blocking.md))
- Assertions use AssertJ (`assertThat(...)`) — not Hamcrest matchers, not JUnit's `assertEquals`

## Integration test: real infrastructure via fixtures

```java
@QuarkusTest
@QuarkusTestResource(ConsulTestResource.class)
@QuarkusTestResource(RepositoryWireMockTestResource.class)
class PlatformRegistrationIT {

    @Inject PlatformRegistrationService service;

    @Test
    void registersANewServiceWithConsul() {
        var response = service.registerService(RegisterRequest.newBuilder()
                .setServiceName("test-service")
                .setType(ServiceType.SERVICE)
                .build())
            .collect().asList()
            .await().atMost(Duration.ofSeconds(10));

        assertThat(response).anyMatch(event -> event.getState() == State.COMPLETED);
    }
}
```

Rules:

- Prefer existing fixtures in `pipestream-test-support` — `ConsulTestResource`, `OpensearchContainerTestResource`, `S3TestResource`, the WireMock test resources listed in [`03-platform-extensions.md`](03-platform-extensions.md)
- If you need a new fixture, add it to `pipestream-test-support` in the same PR (don't hand-roll a `GenericContainer` inside your service)
- Tests are isolated by default. If you need shared state, use `@TestProfile(IsolatedKafkaTopicsProfile.class)` rather than per-test cleanup

## Mocking gRPC dependencies: `pipestream-wiremock-server`

When your service calls another gRPC service, mock the dependency with `pipestream-wiremock-server`. It supports four patterns — pick the right one for the test.

### Pattern 1: `ServiceMockRegistry` + `ServiceMockInitializer`

For static default responses discovered via `ServiceLoader`. Drop a class implementing `ServiceMockInitializer` into the test classpath and declare it in `META-INF/services/ai.pipestream.wiremock.client.ServiceMockInitializer`. The registry picks it up and applies stubs before the test runs. Use when every test in a suite needs the same baseline mocks.

### Pattern 2: `WireMockGrpcClient` per-test overrides

For case-by-case stubbing inside a test. `WireMockGrpcClient` bridges protobuf `MessageOrBuilder` to JSON for matching:

```java
wiremock.stubFor(
    grpcStubFor(AccountService.class, "GetAccount")
        .withRequestBody(equalToGrpcMessage(GetAccountRequest.newBuilder().setId("id-1").build()))
        .willReturn(aGrpcResponseWith(GetAccountResponse.newBuilder().setAccount(account1).build()))
);
```

Use inside a specific test to override baseline stubs.

### Pattern 3: Direct Netty gRPC server impls

For streaming scenarios (server-streaming, client-streaming, bidi) WireMock's HTTP stub engine can't model cleanly. The direct server in `pipestream-wiremock-server` runs on port 50052 and accepts hand-written `*ImplBase` subclasses — e.g. `PlatformRegistrationServiceImpl` emits a deterministic sequence of `RegistrationEvent`s. Use when the dependency you're mocking is streaming.

### Pattern 4: Test metadata headers

For driving dynamic mock behavior without rebuilding stubs. The direct server extracts headers (`x-test-scenario`, `x-test-doc-id`, `x-test-delay-ms`, `x-force-error`) from the inbound gRPC context and routes the response accordingly. Use when one test class runs many parameterized scenarios.

**Rule of thumb:** start with Pattern 1 or 2. Reach for 3 only when streaming is involved. Reach for 4 only when parameterized scenarios would otherwise require a lot of stubbing.

## What *not* to use

- **Mockito** is not our default mocking tool for infrastructure. Use WireMock fixtures. Mockito is fine for pure-logic unit tests where there's no bean graph.
- **`@InjectMock`** — only for test-local beans. Don't mock infrastructure clients (`GrpcClientFactory`, Apicurio client, etc.). Use the real extension wiring and point it at a fixture.
- **`@QuarkusIntegrationTest`** for component tests — reserve it for true end-to-end tests where the service runs in a separate JVM.
- **Manual `GenericContainer<>`s** in a service repo when a fixture exists in `pipestream-test-support`.

## Coverage expectations (for now)

No hard threshold. Focus on:

- Every gRPC method has at least one component test
- Every integration with Consul, Kafka, Apicurio, OpenSearch, or S3 has at least one `*IT` test using the corresponding fixture
- Failure paths are tested — `@QuarkusTest` makes this easy for unary responses, and the wiremock "x-force-error" metadata header makes it easy for streams

Once the fleet stabilizes, we'll set a hard coverage gate in CI. Not yet.
