# Testing Strategy for Pipeline Engine

**Date**: 2025-10-23
**Purpose**: Define comprehensive testing approach for independent microservices builds

---

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Pyramid](#test-pyramid)
3. [Unit Testing](#unit-testing)
4. [Integration Testing](#integration-testing)
5. [Dev Mode Testing](#dev-mode-testing)
6. [End-to-End Testing](#end-to-end-testing)
7. [Testing per Service](#testing-per-service)
8. [Testcontainers Setup](#testcontainers-setup)
9. [WireMock for gRPC](#wiremock-for-grpc)
10. [Frontend Testing](#frontend-testing)
11. [Performance Testing](#performance-testing)

---

## Testing Philosophy

### Core Principles

1. **Fast Feedback**: Unit tests run in seconds, not minutes
2. **Independence**: Each service tests in isolation
3. **Realistic**: Integration tests use real infrastructure (via Testcontainers)
4. **Maintainable**: Tests are easy for LLMs and developers to understand and modify
5. **Automated**: All tests run in CI/CD pipelines

### What Changed from Old Approach

**Before**:
- Shared `compose-devservices.yml` for integration tests
- Tests were interdependent (service A needed service B running)
- Flaky tests due to shared state
- Difficult to debug failures
- Hard for LLMs to maintain

**After**:
- Each service uses Testcontainers for its infrastructure needs
- WireMock stubs for external service calls
- Independent, reproducible tests
- Clear separation: unit vs integration vs E2E
- Shared dev services only for Quarkus dev mode (not tests)

---

## Test Pyramid

```
           /\
          /  \      E2E Tests
         /    \     - Full system integration
        /  10% \    - Playwright (frontend)
       /________\   - Slow, expensive
      /          \
     /            \  Integration Tests
    /     20%     \ - Real infrastructure (Testcontainers)
   /              \ - Medium speed
  /________________\
 /                  \
/        70%        \ Unit Tests
/____________________\ - Fast, isolated
                       - JUnit + WireMock
```

### Test Distribution Goals

- **70% Unit Tests**: Fast (< 30 seconds total per service)
- **20% Integration Tests**: Medium (< 2 minutes total per service)
- **10% E2E Tests**: Slow (nightly or on-demand)

---

## Unit Testing

### Goal

Fast, isolated tests with no external dependencies.

### Technology Stack

- **JUnit 5** (Jupiter)
- **AssertJ** (fluent assertions)
- **WireMock** (HTTP/gRPC mocking)
- **grpc-wiremock** (our custom library for gRPC stubbing)
- **Quarkus Test** (for DI and test resources)

### Example: Service with gRPC Dependencies

```java
// applications/account-manager/src/test/java/io/pipeline/app/account/AccountServiceTest.java
package io.pipeline.app.account;

import io.pipeline.grpc.wiremock.GrpcWireMock;
import io.quarkus.test.junit.QuarkusTest;
import io.quarkus.test.junit.TestProfile;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import jakarta.inject.Inject;

import static org.assertj.core.api.Assertions.assertThat;

@QuarkusTest
@TestProfile(UnitTestProfile.class)
class AccountServiceTest {

    @Inject
    AccountService accountService;

    @Inject
    GrpcWireMock grpcWireMock;  // Provided by grpc-wiremock library

    @BeforeEach
    void setup() {
        grpcWireMock.reset();
    }

    @Test
    void createAccount_shouldRegisterWithRegistrationService() {
        // Given: Mock registration service response
        grpcWireMock.stubFor(
            "registration.RegistrationService/RegisterAccount",
            RegisterAccountResponse.newBuilder()
                .setAccountId("account-123")
                .setStatus(Status.SUCCESS)
                .build()
        );

        // When: Create account
        Account account = accountService.createAccount("test@example.com");

        // Then: Account created with ID from registration service
        assertThat(account).isNotNull();
        assertThat(account.getExternalId()).isEqualTo("account-123");

        // Verify: Registration service was called
        grpcWireMock.verify(
            1,
            "registration.RegistrationService/RegisterAccount"
        );
    }

    @Test
    void getAccount_whenNotFound_shouldReturnNull() {
        // When: Try to get non-existent account
        Account account = accountService.getAccount("nonexistent@example.com");

        // Then: Should return null
        assertThat(account).isNull();
    }
}
```

### Test Profile for Unit Tests

```java
// applications/account-manager/src/test/java/io/pipeline/app/account/UnitTestProfile.java
package io.pipeline.app.account;

import io.quarkus.test.junit.QuarkusTestProfile;
import java.util.Map;

public class UnitTestProfile implements QuarkusTestProfile {

    @Override
    public Map<String, String> getConfigOverrides() {
        return Map.of(
            // Disable database for unit tests
            "quarkus.datasource.devservices.enabled", "false",
            "quarkus.hibernate-orm.database.generation", "none",

            // Use WireMock for gRPC
            "quarkus.grpc.clients.registration.host", "localhost",
            "quarkus.grpc.clients.registration.port", "9999",  // WireMock port

            // Disable Consul for unit tests
            "quarkus.stork.registration-service.service-discovery.type", "static",
            "quarkus.stork.registration-service.service-discovery.address-list", "localhost:9999"
        );
    }
}
```

### Running Unit Tests

```bash
cd applications/account-manager
./gradlew test

# Expected output:
# AccountServiceTest > createAccount_shouldRegisterWithRegistrationService() PASSED
# AccountServiceTest > getAccount_whenNotFound_shouldReturnNull() PASSED
#
# BUILD SUCCESSFUL in 15s
```

### Best Practices

1. **No Real External Dependencies**: Use WireMock for all external calls
2. **Fast**: All unit tests should complete in < 30 seconds
3. **Deterministic**: No timing issues, no random data
4. **Clear Names**: Test names describe what they test
5. **AAA Pattern**: Arrange, Act, Assert (Given, When, Then)

---

## Integration Testing

### Goal

Test with real infrastructure (databases, message queues, S3, etc.) but still isolated per service.

### Technology Stack

- **Testcontainers** (Docker-based infrastructure)
- **JUnit 5**
- **AssertJ**
- **WireMock** (for external services still)

### Example: Database Integration Test

```java
// applications/account-manager/src/test/java/io/pipeline/app/account/AccountRepositoryIT.java
package io.pipeline.app.account;

import io.quarkus.test.junit.QuarkusTest;
import io.quarkus.test.junit.TestProfile;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import jakarta.inject.Inject;
import jakarta.transaction.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

@QuarkusTest
@TestProfile(IntegrationTestProfile.class)
@Testcontainers
class AccountRepositoryIT {

    @Container
    static MySQLContainer<?> mysql = new MySQLContainer<>("mysql:8.0")
        .withDatabaseName("accountdb")
        .withUsername("test")
        .withPassword("test")
        .withReuse(true);  // Reuse container across test classes for speed

    @Inject
    AccountRepository repository;

    @Test
    @Transactional
    void persistAccount_shouldSaveToDatabase() {
        // Given: New account
        Account account = new Account();
        account.setEmail("test@example.com");
        account.setName("Test User");

        // When: Persist account
        repository.persist(account);

        // Then: Account should have ID assigned
        assertThat(account.getId()).isNotNull();
    }

    @Test
    void findByEmail_shouldReturnAccount() {
        // Given: Account exists in DB
        Account account = new Account();
        account.setEmail("find@example.com");
        repository.persist(account);

        // When: Search by email
        Account found = repository.findByEmail("find@example.com");

        // Then: Should find the account
        assertThat(found).isNotNull();
        assertThat(found.getEmail()).isEqualTo("find@example.com");
    }

    @Test
    void findByEmail_whenNotExists_shouldReturnNull() {
        // When: Search for non-existent email
        Account found = repository.findByEmail("nonexistent@example.com");

        // Then: Should return null
        assertThat(found).isNull();
    }
}
```

### Integration Test Profile

```java
// applications/account-manager/src/test/java/io/pipeline/app/account/IntegrationTestProfile.java
package io.pipeline.app.account;

import io.quarkus.test.junit.QuarkusTestProfile;
import org.testcontainers.containers.MySQLContainer;

import java.util.Map;

public class IntegrationTestProfile implements QuarkusTestProfile {

    @Override
    public Map<String, String> getConfigOverrides() {
        // Testcontainer is started via @Container annotation
        // Quarkus will auto-detect and configure datasource
        return Map.of(
            // Disable Dev Services (we're using Testcontainers explicitly)
            "quarkus.datasource.devservices.enabled", "false",

            // Use WireMock for external gRPC services
            "quarkus.grpc.clients.registration.host", "localhost",
            "quarkus.grpc.clients.registration.port", "9999"
        );
    }
}
```

### Running Integration Tests

```bash
cd applications/account-manager
./gradlew integrationTest

# Or if you prefer separate Gradle task:
./gradlew test --tests '*IT'

# Expected output:
# AccountRepositoryIT > persistAccount_shouldSaveToDatabase() PASSED
# AccountRepositoryIT > findByEmail_shouldReturnAccount() PASSED
# AccountRepositoryIT > findByEmail_whenNotExists_shouldReturnNull() PASSED
#
# BUILD SUCCESSFUL in 1m 45s
```

### Gradle Configuration for Integration Tests

```gradle
// applications/account-manager/build.gradle

// Option 1: Use same test source set
test {
    useJUnitPlatform()
    systemProperty "java.util.logging.manager", "org.jboss.logmanager.LogManager"

    // Separate test execution for faster feedback
    include '**/*Test.class'  // Unit tests first
}

tasks.register('integrationTest', Test) {
    useJUnitPlatform()
    systemProperty "java.util.logging.manager", "org.jboss.logmanager.LogManager"

    include '**/*IT.class'  // Integration tests
    shouldRunAfter test
}

check.dependsOn integrationTest


// Option 2: Separate source set (more advanced)
sourceSets {
    integrationTest {
        java {
            compileClasspath += main.output + test.output
            runtimeClasspath += main.output + test.output
            srcDir 'src/integrationTest/java'
        }
        resources {
            srcDir 'src/integrationTest/resources'
        }
    }
}

configurations {
    integrationTestImplementation.extendsFrom testImplementation
    integrationTestRuntimeOnly.extendsFrom testRuntimeOnly
}

tasks.register('integrationTest', Test) {
    testClassesDirs = sourceSets.integrationTest.output.classesDirs
    classpath = sourceSets.integrationTest.runtimeClasspath
}
```

---

## Dev Mode Testing

### Goal

Manual testing with real services running via Quarkus Dev Mode and Docker Compose.

### Use Cases

- Visual frontend testing
- Manual API testing
- Debugging complex flows
- Exploratory testing

### Setup

```bash
# Terminal 1: Start infrastructure
cd dev-infrastructure
docker compose -f compose-devservices.yml up -d

# Terminal 2: Start backend service
cd applications/account-manager
./gradlew quarkusDev

# Terminal 3: Start web-proxy (if testing frontend)
cd node/web-proxy
pnpm run dev

# Terminal 4: Start platform-shell (if testing frontend)
cd node/platform-shell
pnpm run dev
```

### Access Points

- Application API: http://localhost:8080 (or configured port)
- Quarkus Dev UI: http://localhost:8080/q/dev
- Swagger UI: http://localhost:8080/q/swagger-ui
- Platform Shell: http://localhost:37200
- Traefik Dashboard: http://localhost:8081

### Testing Workflow

1. **Make code changes**
2. **Quarkus auto-reloads** (hot reload)
3. **Test via UI or curl**:
   ```bash
   curl -X POST http://localhost:8080/api/accounts \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","name":"Test User"}'
   ```
4. **Check logs** in terminal
5. **Repeat**

### Best For

- Frontend development
- API contract validation
- Multi-service flow testing
- Performance profiling

---

## End-to-End Testing

### Goal

Test complete user workflows across multiple services and frontend.

### Technology Stack

- **Playwright** (browser automation)
- **TypeScript**
- **Docker Compose** (for full environment)

### Example: Account Creation Flow

```typescript
// e2e-tests/specs/account-creation.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Account Creation Flow', () => {

  test.beforeEach(async ({ page }) => {
    // Navigate to platform shell
    await page.goto('http://localhost:37200');
  });

  test('should create new account via UI', async ({ page }) => {
    // Given: User is on accounts page
    await page.click('nav >> text=Accounts');
    await page.click('button >> text=Create Account');

    // When: User fills form and submits
    await page.fill('input[name="email"]', 'e2e-test@example.com');
    await page.fill('input[name="name"]', 'E2E Test User');
    await page.click('button[type="submit"]');

    // Then: Success message appears
    await expect(page.locator('.success-message')).toBeVisible();
    await expect(page.locator('.success-message')).toContainText('Account created successfully');

    // And: Account appears in list
    await page.goto('http://localhost:37200/accounts');
    await expect(page.locator('text=e2e-test@example.com')).toBeVisible();
  });

  test('should show validation error for invalid email', async ({ page }) => {
    // Given: User is on create account page
    await page.click('nav >> text=Accounts');
    await page.click('button >> text=Create Account');

    // When: User enters invalid email
    await page.fill('input[name="email"]', 'not-an-email');
    await page.click('button[type="submit"]');

    // Then: Validation error appears
    await expect(page.locator('.error-message')).toBeVisible();
    await expect(page.locator('.error-message')).toContainText('Invalid email address');
  });

});
```

### Playwright Configuration

```typescript
// e2e-tests/playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './specs',
  timeout: 30000,
  retries: 2,
  workers: 4,

  use: {
    baseURL: 'http://localhost:37200',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
  ],

  // Start services before tests
  webServer: [
    {
      command: 'docker compose -f dev-infrastructure/compose-devservices.yml up',
      port: 3306,  // MySQL port (wait for infrastructure)
      reuseExistingServer: true,
    },
    {
      command: 'cd applications/account-manager && ./gradlew quarkusDev',
      port: 8080,
      reuseExistingServer: true,
    },
    {
      command: 'cd node/web-proxy && pnpm run dev',
      port: 37201,
      reuseExistingServer: true,
    },
    {
      command: 'cd node/platform-shell && pnpm run dev',
      port: 37200,
      reuseExistingServer: true,
    },
  ],
});
```

### Running E2E Tests

```bash
# Install Playwright
cd e2e-tests
pnpm install
npx playwright install

# Run tests (headless)
pnpm run test:e2e

# Run tests (headed, with UI)
pnpm run test:e2e:ui

# Run specific test
pnpm run test:e2e account-creation.spec.ts
```

### When to Run

- **Locally**: On-demand before releasing
- **CI/CD**: Nightly builds or on main branch only
- **Not on**: Every PR (too slow)

---

## Testing per Service

### account-manager

| Test Type | Focus | Tools | Duration |
|-----------|-------|-------|----------|
| Unit | Business logic, service layer | JUnit, WireMock | 20s |
| Integration | Database ops (MySQL) | Testcontainers | 1m 30s |
| Dev Mode | UI testing, manual flows | Quarkus Dev | Manual |
| E2E | Account CRUD via frontend | Playwright | 5m |

**Testcontainers Used**:
- MySQL 8.0

**External Services Mocked**:
- Registration Service (gRPC)

### connector-service

| Test Type | Focus | Tools | Duration |
|-----------|-------|-------|----------|
| Unit | Connector config, validation | JUnit, WireMock | 25s |
| Integration | Kafka messaging, database | Testcontainers | 2m |
| Dev Mode | Connector creation flows | Quarkus Dev | Manual |

**Testcontainers Used**:
- Kafka + Zookeeper
- MySQL 8.0

**External Services Mocked**:
- Account Manager (gRPC)

### repo-service

| Test Type | Focus | Tools | Duration |
|-----------|-------|-------|----------|
| Unit | Repository logic | JUnit, WireMock | 30s |
| Integration | S3 (MinIO), chunked uploads | Testcontainers | 2m 30s |
| Dev Mode | File upload testing | Quarkus Dev | Manual |

**Testcontainers Used**:
- MinIO (S3-compatible)
- MySQL 8.0

**External Services Mocked**:
- Multiple gRPC services

### opensearch-manager

| Test Type | Focus | Tools | Duration |
|-----------|-------|-------|----------|
| Unit | Index management logic | JUnit | 15s |
| Integration | OpenSearch operations, Kafka | Testcontainers | 3m |
| Dev Mode | Search testing | Quarkus Dev | Manual |

**Testcontainers Used**:
- OpenSearch 2.x
- Kafka + Zookeeper
- Apicurio Registry

**External Services Mocked**:
- None (mostly infrastructure)

### parser (Module)

| Test Type | Focus | Tools | Duration |
|-----------|-------|-------|----------|
| Unit | Document parsing, Tika | JUnit | 45s |
| Integration | (Optional) Large file parsing | Testcontainers | 2m |
| Dev Mode | Parse various file types | Quarkus Dev | Manual |

**Testcontainers Used**:
- (Optional) For large file testing

**External Services Mocked**:
- None (stateless module)

### web-proxy

| Test Type | Focus | Tools | Duration |
|-----------|-------|-------|----------|
| Unit | gRPC-Web translation | Jest | 10s |
| Integration | N/A | - | - |
| Dev Mode | API proxying | Node dev | Manual |
| E2E | Full frontend flows | Playwright | 5m |

**No Testcontainers** (Node.js service, mostly proxying)

---

## Testcontainers Setup

### Gradle Dependencies

```gradle
// build.gradle
dependencies {
    // Testcontainers BOM
    testImplementation platform('org.testcontainers:testcontainers-bom:1.21.3')

    // Core Testcontainers
    testImplementation 'org.testcontainers:testcontainers'
    testImplementation 'org.testcontainers:junit-jupiter'

    // Specific containers
    testImplementation 'org.testcontainers:mysql'
    testImplementation 'org.testcontainers:kafka'
    testImplementation 'org.testcontainers:minio'
    // ... etc
}
```

### Docker Configuration

Testcontainers requires Docker running locally:

```bash
# Verify Docker is running
docker ps

# Configure Testcontainers (optional)
# Create ~/.testcontainers.properties
testcontainers.reuse.enable=true  # Reuse containers across test runs
```

### Container Reuse Pattern

```java
@Container
static MySQLContainer<?> mysql = new MySQLContainer<>("mysql:8.0")
    .withDatabaseName("testdb")
    .withUsername("test")
    .withPassword("test")
    .withReuse(true);  // Keep container running between test classes

static {
    mysql.start();  // Start once for all tests
}
```

### Custom Container Configuration

```java
// Custom MinIO container for repo-service
@Container
static GenericContainer<?> minio = new GenericContainer<>("minio/minio:latest")
    .withExposedPorts(9000)
    .withEnv("MINIO_ROOT_USER", "minioadmin")
    .withEnv("MINIO_ROOT_PASSWORD", "minioadmin")
    .withCommand("server /data")
    .waitingFor(Wait.forHttp("/minio/health/ready").forPort(9000));

@BeforeAll
static void setupMinio() {
    // Configure Quarkus to use MinIO from container
    System.setProperty("quarkus.s3.endpoint-override",
        "http://" + minio.getHost() + ":" + minio.getMappedPort(9000));
    System.setProperty("quarkus.s3.aws.credentials.static-provider.access-key-id", "minioadmin");
    System.setProperty("quarkus.s3.aws.credentials.static-provider.secret-access-key", "minioadmin");
}
```

---

## WireMock for gRPC

### Using grpc-wiremock Library

Our custom `grpc-wiremock` library simplifies mocking gRPC services:

```java
@QuarkusTest
class ServiceTest {

    @Inject
    GrpcWireMock grpcWireMock;

    @BeforeEach
    void setup() {
        grpcWireMock.reset();
    }

    @Test
    void testGrpcCall() {
        // Stub gRPC response
        grpcWireMock.stubFor(
            "registration.RegistrationService/RegisterAccount",
            RegisterAccountResponse.newBuilder()
                .setAccountId("123")
                .build()
        );

        // Call service that makes gRPC call
        Account account = accountService.createAccount("test@example.com");

        // Verify
        assertThat(account.getExternalId()).isEqualTo("123");

        grpcWireMock.verify(
            1,
            "registration.RegistrationService/RegisterAccount"
        );
    }
}
```

### Configuration

```properties
# src/test/resources/application-test.properties
quarkus.grpc.clients.registration.host=localhost
quarkus.grpc.clients.registration.port=9999  # WireMock port
```

### Advanced Scenarios

```java
// Conditional responses
grpcWireMock.stubFor(
    "registration.RegistrationService/RegisterAccount",
    request -> {
        RegisterAccountRequest req = (RegisterAccountRequest) request;
        if (req.getEmail().contains("error")) {
            throw Status.INVALID_ARGUMENT.asRuntimeException();
        }
        return RegisterAccountResponse.newBuilder()
            .setAccountId(UUID.randomUUID().toString())
            .build();
    }
);

// Delayed responses
grpcWireMock.stubFor(
    "registration.RegistrationService/RegisterAccount",
    RegisterAccountResponse.getDefaultInstance(),
    Duration.ofSeconds(2)  // Simulate slow service
);
```

---

## Frontend Testing

### Jest for Unit Tests

```typescript
// node/web-proxy/src/__tests__/grpc-translator.test.ts
import { GrpcTranslator } from '../grpc-translator';

describe('GrpcTranslator', () => {
  it('should translate REST request to gRPC', () => {
    const translator = new GrpcTranslator();
    const restRequest = {
      email: 'test@example.com',
      name: 'Test User'
    };

    const grpcRequest = translator.toGrpc('CreateAccount', restRequest);

    expect(grpcRequest.email).toBe('test@example.com');
    expect(grpcRequest.name).toBe('Test User');
  });
});
```

### Component Testing (Future)

Using Vitest + Vue Test Utils:

```typescript
// node/platform-shell/src/components/__tests__/AccountForm.spec.ts
import { mount } from '@vue/test-utils';
import AccountForm from '../AccountForm.vue';

describe('AccountForm', () => {
  it('should validate email format', async () => {
    const wrapper = mount(AccountForm);

    await wrapper.find('input[name="email"]').setValue('invalid-email');
    await wrapper.find('form').trigger('submit');

    expect(wrapper.find('.error-message').text()).toContain('Invalid email');
  });
});
```

### Visual Regression Testing (Future)

Using Percy or Chromatic:

```typescript
// Take screenshot for visual comparison
await page.goto('http://localhost:37200/accounts');
await percySnapshot(page, 'Accounts List');
```

---

## Performance Testing

### Load Testing with Gatling

```scala
// performance-tests/src/gatling/scala/AccountSimulation.scala
import io.gatling.core.Predef._
import io.gatling.http.Predef._

class AccountSimulation extends Simulation {

  val httpProtocol = http
    .baseUrl("http://localhost:8080")
    .acceptHeader("application/json")

  val scn = scenario("Account Creation")
    .exec(http("Create Account")
      .post("/api/accounts")
      .body(StringBody("""{"email":"test@example.com","name":"Test"}"""))
      .check(status.is(201)))

  setUp(
    scn.inject(
      rampUsersPerSec(10) to 100 during (60 seconds),
      constantUsersPerSec(100) during (120 seconds)
    )
  ).protocols(httpProtocol)
}
```

### Performance Benchmarks

Target metrics:
- **API Response Time**: p95 < 100ms
- **gRPC Call Latency**: p95 < 50ms
- **Database Query Time**: p95 < 20ms
- **Throughput**: > 1000 req/sec per service

---

## CI/CD Integration

### GitHub Actions Test Configuration

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4

      # Unit tests (fast)
      - name: Run Unit Tests
        run: cd applications/account-manager && ./gradlew test

      # Integration tests (slower)
      - name: Run Integration Tests
        run: cd applications/account-manager && ./gradlew integrationTest

      # Upload test results
      - name: Publish Test Results
        uses: EnricoMi/publish-unit-test-result-action@v2
        if: always()
        with:
          files: '**/build/test-results/**/*.xml'

      # Upload coverage
      - name: Upload Coverage
        uses: codecov/codecov-action@v3
        with:
          files: '**/build/jacoco/test.exec'
```

### Test Failure Handling

```yaml
      - name: Archive Test Results
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: |
            **/build/reports/tests/
            **/build/test-results/
```

---

## Summary

### Key Takeaways

1. **70/20/10 Split**: Focus on unit tests, support with integration, validate with E2E
2. **Testcontainers**: Real infrastructure in tests, isolated per service
3. **WireMock/grpc-wiremock**: Mock external services, not infrastructure
4. **Dev Mode**: For visual and manual testing only
5. **Fast Feedback**: Unit tests in seconds, integration in minutes
6. **CI/CD**: All tests automated in pipelines

### Success Metrics

- [ ] All services have > 70% unit test coverage
- [ ] Integration tests run in < 3 minutes per service
- [ ] E2E tests exist for critical user flows
- [ ] All tests pass in CI/CD before merge
- [ ] Zero shared test infrastructure (except dev mode)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-23
