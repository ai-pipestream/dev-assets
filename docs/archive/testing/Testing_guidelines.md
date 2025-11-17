# Testing Guidelines

This document outlines the comprehensive testing strategy for the pipeline-engine-refactor project, covering unit tests, component tests, integration tests, and end-to-end tests.

## Test Hierarchy

### 1. Unit Tests (`*UnitTest.java`)
- **Location**: `src/test/java`
- **Framework**: Pure JUnit 5, no Quarkus framework
- **Purpose**: Test individual classes in isolation
- **Dependencies**: Mock all external dependencies using Mockito
- **Scope**: Fast, isolated, no infrastructure

### 2. Component Tests (`*Test.java`)
- **Location**: `src/test/java`
- **Framework**: `@QuarkusComponentTest`
- **Purpose**: Test CDI components with mocked dependencies
- **Dependencies**: Use `@InjectMock` for external services
- **Scope**: Medium speed, CDI context, mocked infrastructure

### 3. Integration Tests (`*IT.java`)
- **Location**: `src/integrationTest/java`
- **Framework**: `@QuarkusTest`
- **Purpose**: Test full Quarkus stack with real infrastructure
- **Dependencies**: Real infrastructure via Compose Dev Services
- **Scope**: Slower, full stack, real infrastructure

### 4. End-to-End Integration Tests (`*E2ETest.java`)
- **Location**: `src/integrationTest/java`
- **Framework**: `@QuarkusIntegrationTest`
- **Purpose**: Test built artifact (JAR/native/container) via HTTP clients
- **Dependencies**: External HTTP clients, no CDI injection
- **Scope**: Slowest, production-like, external clients

## Test Infrastructure

### Compose Dev Services
- **Development**: `src/test/resources/compose-devservices.yml`
- **Testing**: `src/test/resources/compose-test-services.yml`
- **Purpose**: Manage test infrastructure (MySQL, Kafka, MinIO)
- **Configuration**: Single instance to prevent long startup times

### WireMock for External Services
- **Purpose**: Mock external gRPC services (e.g., Platform Registration Service)
- **Usage**: `@QuarkusTestResource(WireMockGrpcTestResource.class)`
- **Profile**: `@TestProfile(MockGrpcProfile.class)`

## Property Management

### Single Properties File Strategy
- **Location**: `src/main/resources/application.properties`
- **Profiles**: Use `%dev` and `%test` profiles
- **Constraint**: NO `src/test/resources/application.properties`
- **Purpose**: Prevent property spillover between test and main

### Profile Examples
```properties
# Development profile
%dev.quarkus.datasource.jdbc.url=jdbc:mysql://localhost:3306/repo_service_dev

# Test profile  
%test.quarkus.datasource.jdbc.url=jdbc:mysql://localhost:3306/repo_service_test
```

## Testing Constraints

### @QuarkusIntegrationTest Constraints
- **No CDI Injection**: Cannot inject beans directly
- **HTTP Client Only**: Must use HTTP clients to test endpoints
- **Built Artifact**: Tests against the built JAR/native/container
- **Separate Source Set**: Lives in `src/integrationTest/java`
- **No Test Resources**: Cannot use `src/test/resources` properties
- **Production Profile**: Runs with `prod` profile by default

### Base Test Patterns
- **Abstract Base Classes**: Common test functionality
- **Shared Utilities**: Reusable test helpers
- **Consistent Setup**: Standardized test initialization

## Assertion Libraries

### Primary: Hamcrest
- **Usage**: Descriptive, readable assertions
- **Examples**: `assertThat(actual, is(expected))`
- **Benefits**: Clear failure messages, fluent API

### Secondary: AssertJ
- **Usage**: Complex object validation
- **Examples**: `assertThat(actual).isEqualTo(expected)`
- **Benefits**: Rich assertion methods, good for collections

## Mocking Strategy

### Mockito Usage
- **Unit Tests**: Mock all external dependencies
- **Component Tests**: Use `@InjectMock` for Quarkus beans
- **Integration Tests**: Real dependencies, mocked external services

### S3 Testing
- **Interface Pattern**: Create `S3Operations` interface
- **Mocking**: Mock S3 operations for unit tests
- **Integration**: Use MinIO for integration tests

## Database Testing

### Hibernate Panache
- **Repository Testing**: Test Panache repositories
- **Entity Testing**: Test JPA entities
- **Transaction Management**: Proper transaction handling

### Migration Testing
- **Flyway**: Test database migrations
- **Schema Validation**: Ensure schema consistency

## Kafka Testing

### Event Publishing
- **Producer Testing**: Test Kafka producers
- **Schema Registry**: Test Apicurio Registry integration
- **Event Validation**: Ensure proper event structure

## gRPC Testing

### Service Testing
- **gRPC Services**: Test gRPC service implementations
- **Client Testing**: Test gRPC client calls
- **WireMock**: Mock external gRPC services

### Stub Management
- **Shared Stubs**: Use shared gRPC stubs library
- **Descriptor Files**: Use `META-INF/grpc/services.dsc`
- **Build Optimization**: Avoid per-module gRPC compilation

## Test Organization

### Directory Structure
```
src/
├── test/java/                    # Unit and Component tests
│   ├── io/pipeline/repository/
│   │   ├── services/
│   │   │   ├── S3ServiceTest.java
│   │   │   └── S3ServiceUnitTest.java
│   │   └── BaseTest.java
└── integrationTest/java/         # Integration tests
    ├── io/pipeline/repository/
    │   ├── S3ServiceIT.java
    │   └── S3ServiceE2ETest.java
```
TODO: add integration test constraints!!


### Naming Conventions
- **Unit Tests**: `*UnitTest.java`
- **Component Tests**: `*Test.java`
- **Integration Tests**: `*IT.java`
- **E2E Tests**: `*E2ETest.java`

## Best Practices

### Test Descriptions
- **Descriptive Names**: Clear, descriptive test method names
- **Given-When-Then**: Structure tests with clear sections
- **Documentation**: Comment complex test scenarios

### Test Isolation
- **Independent Tests**: Each test should be independent
- **Clean State**: Reset state between tests
- **No Side Effects**: Tests should not affect each other

### Performance
- **Fast Unit Tests**: Keep unit tests fast
- **Parallel Execution**: Enable parallel test execution
- **Resource Cleanup**: Properly clean up test resources

## Service Registration Testing

### Consul Integration
- **Registration Testing**: Test service registration with Consul
- **Health Checks**: Test health check endpoints
- **Discovery Testing**: Test service discovery

### Health Endpoints
- **Liveness**: Test liveness probes
- **Readiness**: Test readiness probes
- **Metrics**: Test metrics endpoints

## Continuous Integration

### Test Execution
- **All Tests**: Run all test types in CI
- **Parallel Execution**: Run tests in parallel
- **Test Reports**: Generate test reports

### Quality Gates
- **Coverage**: Maintain test coverage thresholds
- **Performance**: Monitor test performance
- **Reliability**: Ensure test reliability
