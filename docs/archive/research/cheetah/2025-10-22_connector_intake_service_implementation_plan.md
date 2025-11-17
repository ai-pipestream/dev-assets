# Connector Intake Service Implementation Plan

**Date:** 2025-10-22  
**Owner:** Cheetah (AI Assistant)  
**Status:** Planning Phase - No Coding Yet

## Executive Summary

This document outlines the complete implementation plan for the Connector Intake Service, a high-volume document ingestion service that validates connectors and streams documents to the repository service for processing. The service will handle 1MM+ documents in production, with some connectors processing millions of documents while others process thousands.

## Architecture Decisions

### Service Separation

**Decision:** Connector Intake Service will be a separate service from Connector Admin Service.

**Rationale:**
- **Security boundaries:** Admin operations (CRUD, API key rotation) are sensitive and protected; intake is public-facing and handles untrusted data
- **Scaling:** Admin is low-volume; intake can be high-volume and needs horizontal scaling
- **Deployment:** Intake can sit in a different network (DMZ) while admin stays internal
- **Dependencies:** Intake is stateless (no DB); admin manages state
- **Failure isolation:** Intake issues don't affect admin operations

**Trade-offs:**
- Inter-service calls: Intake calls `ConnectorAdminService.GetConnector` for each session
- Code duplication: Both services need connector validation logic
- Operational complexity: Two services to deploy and monitor

**Mitigation:**
- Use `DynamicGrpcClientFactory` for efficient gRPC calls
- Consider caching connector configs later if needed (not in MVP)
- Same VPC/network means low latency (~1-5ms)

### Caching Strategy

**Decision:** No caching in MVP.

**Rationale:**
- Only 30 connectors in production
- Same VPC means low latency
- gRPC is efficient for small payloads
- Can add caching later if needed

**When to add caching:**
- High session start rate
- Latency issues
- Load on connector-service

## Service Details

### Connector Intake Service

**Location:** `applications/connector-intake-service`  
**Port:** 38108  
**Framework:** Quarkus  
**Database:** None (stateless)  
**Dependencies:** 
- `connector-service` (via gRPC)
- `repo-service` (via gRPC)
- Kafka (dependencies only, implementation deferred)

**Proto File:** `grpc/grpc-stubs/src/main/proto/module/connectors/connector_intake_service.proto`

**Endpoints to Implement (MVP):**
- `StreamDocuments` (bidirectional streaming) - **CORE MVP**
- `StartCrawlSession` - Deferred
- `EndCrawlSession` - Deferred
- `Heartbeat` - Deferred

**Registration:**
- Consul: Yes (auto-registration)
- Traefik: Yes (auto-registration)

### Connector Admin Service

**Location:** `applications/connector-service`  
**Status:** Already implemented  
**Endpoints:** All CRUD operations complete

## Implementation Plan

### Task 1: Fix Repo-Service (Highest Priority Blocker)

**Objective:** Get repo-service running successfully by removing old account management and integrating with account-service.

**Status:** ✅ COMPLETED (2025-10-22)

**TODOs:**

1. **Remove Account Entity and Service**
   - [x] Delete `applications/repo-service/src/main/java/io/pipeline/repository/entity/Account.java`
   - [x] Remove `Account.AccountService` inner class
   - [x] Remove account-related imports from `DriveManager.java`

2. **Create AccountValidationService**
   - [x] Create `applications/repo-service/src/main/java/io/pipeline/repository/service/AccountValidationService.java`
   - [x] Use `DynamicGrpcClientFactory` to call `account-manager` service
   - [x] Implement `validateAccountExistsAndActive(String accountId)` method
   - [x] Implement `validateAccountExists(String accountId)` method
   - [x] Handle gRPC errors (NOT_FOUND → RuntimeException)
   - [x] Follow the same pattern as `connector-service`'s `AccountValidationService`

3. **Update DriveManager**
   - [x] Replace `Account.AccountService` injection with `AccountValidationService`
   - [x] Update both `createDrive` methods to use `AccountValidationService.validateAccountExistsAndActive`
   - [x] Handle validation errors appropriately (async via Uni)

4. **Remove Account Migration**
   - [x] Delete `V11__create_accounts_table.sql` from `applications/repo-service/src/main/resources/db/migration/`
   - [x] Verify no other migrations reference accounts table (V12 has no FK constraint)

5. **Update Tests**
   - [x] Review and update `repo-service` integration tests
   - [x] No tests require changes (AccountManagerIntegrationTest already uses WireMock)
   - [x] Compilation succeeds

**Notes:**
- Test failures are due to pre-existing Kafka/Apicurio configuration issues, not related to this refactoring
- DriveManager now properly validates accounts via gRPC before creating drives
- No database coupling between repo-service and accounts

**Dependencies:** None
**Actual Time:** 1.5 hours

### Task 2: Create Connector Intake Service Structure

**Objective:** Set up the basic Quarkus application structure for connector-intake-service.

**TODOs:**

1. **Create Directory Structure**
   - [ ] Create `applications/connector-intake-service/` directory
   - [ ] Create `src/main/java/io/pipeline/connector/intake/` package structure
   - [ ] Create `src/main/resources/` directory
   - [ ] Create `src/test/java/io/pipeline/connector/intake/` package structure

2. **Create build.gradle**
   - [ ] Copy from `connector-service/build.gradle` as template
   - [ ] Update dependencies:
     - `quarkus-grpc` (for gRPC server)
     - `io.pipeline:dynamic-grpc` (for gRPC clients)
     - `io.pipeline:dynamic-grpc-registration-clients` (for service discovery)
     - `quarkus-smallrye-reactive-messaging-kafka` (for Kafka, deferred implementation)
     - `quarkus-smallrye-stork` (for service discovery)
     - `io.smallrye.stork:stork-service-discovery-consul` (for Consul)
     - `io.smallrye.reactive:smallrye-mutiny-vertx-consul-client` (for Consul client)
   - [ ] Set application name to `connector-intake-service`
   - [ ] Set port to 38108

3. **Create application.properties**
   - [ ] Configure gRPC server (port 38108)
   - [ ] Configure Consul service discovery
   - [ ] Configure Traefik routing (`/connector-intake/`)
   - [ ] Add chunking threshold: `quarkus.connector-intake.chunking-threshold=5242880` (5MB)
   - [ ] Configure Kafka (dependencies only, no implementation yet)
   - [ ] Add service registration tags

4. **Update settings.gradle**
   - [ ] Add `connector-intake-service` to the project list

5. **Generate gRPC Stubs**
   - [ ] Run `./gradlew updateGrpcStubs` to generate Java stubs
   - [ ] Verify `ConnectorIntakeService` stubs are generated

**Dependencies:** Task 1 (repo-service fixes)  
**Estimated Time:** 1-2 hours

### Task 3: Implement ConnectorIntakeService Streaming Endpoint

**Objective:** Implement the core `StreamDocuments` bidirectional streaming endpoint.

**TODOs:**

1. **Create ConnectorIntakeServiceImpl**
   - [ ] Create `applications/connector-intake-service/src/main/java/io/pipeline/connector/intake/service/ConnectorIntakeServiceImpl.java`
   - [ ] Extend `MutinyConnectorIntakeServiceGrpc.ConnectorIntakeServiceImplBase`
   - [ ] Implement `StreamDocuments` method with bidirectional streaming
   - [ ] Handle `SessionStart` message:
     - Extract `connector_id` and `api_key`
     - Call `ConnectorAdminService.GetConnector` via gRPC
     - Validate API key
     - Return `SessionStartResponse` with `ConnectorConfig`
   - [ ] Handle `DocumentData` messages:
     - Validate document data
     - Call `repo-service` to store document
     - Return `DocumentResponse` with success/error status

2. **Create ConnectorValidationService**
   - [ ] Create `applications/connector-intake-service/src/main/java/io/pipeline/connector/intake/service/ConnectorValidationService.java`
   - [ ] Use `DynamicGrpcClientFactory` to call `connector-service`
   - [ ] Implement `validateConnectorAndApiKey(String connectorId, String apiKey)` method
   - [ ] Return `ConnectorConfig` on success
   - [ ] Handle gRPC errors appropriately

3. **Create DocumentStorageService**
   - [ ] Create `applications/connector-intake-service/src/main/java/io/pipeline/connector/intake/service/DocumentStorageService.java`
   - [ ] Use `DynamicGrpcClientFactory` to call `repo-service`
   - [ ] Implement `storeDocument(DocumentData, ConnectorConfig)` method
   - [ ] Handle document storage errors
   - [ ] Return document ID and S3 key

4. **Create ErrorMapper Utility**
   - [ ] Create `applications/connector-intake-service/src/main/java/io/pipeline/connector/intake/util/ErrorMapper.java`
   - [ ] Map internal exceptions to gRPC status codes:
     - `INVALID_AUTH` - Invalid API key
     - `INVALID_ARGUMENT` - Missing required fields
     - `PAYLOAD_TOO_LARGE` - Document exceeds max size
     - `INTERNAL` - Unexpected errors
   - [ ] Provide helper methods for common error scenarios

5. **Add Configuration**
   - [ ] Add `quarkus.connector-intake.chunking-threshold=5242880` to `application.properties`
   - [ ] Add any other configuration needed

**Dependencies:** Task 2 (service structure)  
**Estimated Time:** 4-6 hours

### Task 4: Create grpc-wiremock Tests

**Objective:** Create comprehensive tests for ConnectorIntakeService using grpc-wiremock.

**TODOs:**

1. **Create ConnectorIntakeServiceGrpcTest**
   - [ ] Create `applications/connector-intake-service/src/test/java/io/pipeline/connector/intake/ConnectorIntakeServiceGrpcTest.java`
   - [ ] Use `@QuarkusTestResource(WireMockGrpcTestResource.class)`
   - [ ] Use `@TestProfile(MockGrpcProfile.class)`
   - [ ] Mock `ConnectorAdminService.GetConnector` responses
   - [ ] Mock `repo-service` responses
   - [ ] Test `SessionStart` authentication flow
   - [ ] Test `DocumentData` storage flow
   - [ ] Test error scenarios (invalid API key, missing fields, etc.)

2. **Create Test Profiles**
   - [ ] Create `MockGrpcProfile.java` for test configuration
   - [ ] Configure test-specific properties

**Dependencies:** Task 3 (streaming implementation)  
**Estimated Time:** 2-3 hours

### Task 5: Create grpcurl Test Script

**Objective:** Create a bash script for manual testing of ConnectorIntakeService.

**TODOs:**

1. **Create test_connector_intake_grpcurl.sh**
   - [ ] Create `applications/connector-intake-service/src/main/bash/test_connector_intake_grpcurl.sh`
   - [ ] Test `StreamDocuments` endpoint
   - [ ] Test `SessionStart` with valid API key
   - [ ] Test `SessionStart` with invalid API key
   - [ ] Test `DocumentData` upload
   - [ ] Test error scenarios

**Dependencies:** Task 4 (grpc-wiremock tests)  
**Estimated Time:** 1-2 hours

### Task 6: Update Repo-Service for Deduplication

**Objective:** Ensure repo-service returns `was_update` and `previous_version` in responses.

**TODOs:**

1. **Review Repo-Service Proto**
   - [ ] Check if `was_update` and `previous_version` fields exist in response messages
   - [ ] If not, add them to appropriate response messages

2. **Update Repo-Service Implementation**
   - [ ] Implement deduplication logic using `(connector_id + client_document_id)` primary key
   - [ ] Implement fallback using `(connector_id + source_id)`
   - [ ] Return `was_update=true` if document already exists
   - [ ] Return `previous_version` if document was updated
   - [ ] Return `was_update=false` if document is new

3. **Update Tests**
   - [ ] Add tests for deduplication logic
   - [ ] Test primary key deduplication
   - [ ] Test fallback deduplication
   - [ ] Test `was_update` flag

**Dependencies:** Task 1 (repo-service fixes)  
**Estimated Time:** 2-3 hours

### Task 7: E2E Testing with Testcontainers

**Objective:** Create comprehensive E2E tests using Testcontainers.

**TODOs:**

1. **Create E2E Test**
   - [ ] Create `applications/connector-intake-service/src/test/java/io/pipeline/connector/intake/ConnectorIntakeServiceE2ETest.java`
   - [ ] Use Testcontainers for MySQL and MinIO
   - [ ] Use shared compose file for test services
   - [ ] Test full flow: connector validation → document storage → deduplication
   - [ ] Test error scenarios

2. **Configure Test Services**
   - [ ] Use `compose-test-services.yml` for shared test infrastructure
   - [ ] Ensure all services are properly configured

**Dependencies:** Task 5 (grpcurl tests)  
**Estimated Time:** 2-3 hours

### Task 8: Kafka Integration (Deferred)

**Objective:** Add Kafka integration for async document counting and metrics.

**TODOs:**

1. **Add Kafka Dependencies**
   - [ ] Already added in Task 2

2. **Implement Kafka Producers**
   - [ ] Create document count events
   - [ ] Create error events
   - [ ] Use protocol buffers for all messages

3. **Configure Kafka Topics**
   - [ ] Define topic names
   - [ ] Configure producers

**Dependencies:** Task 7 (E2E tests)  
**Estimated Time:** 2-3 hours  
**Status:** Deferred until after MVP

## Testing Strategy

### Unit Tests
- Use grpc-wiremock for mocking gRPC calls
- Test individual service methods
- Test error scenarios

### Integration Tests
- Use grpc-wiremock for mocking external services
- Test full request/response flow
- Test error handling

### E2E Tests
- Use Testcontainers with shared compose file
- Test with real MySQL and MinIO
- Test full document ingestion flow

### Manual Testing
- Use grpcurl scripts for quick smoke tests
- Test in dev mode as we go
- Verify live behavior

## Error Handling

### Error Scenarios (MVP)
1. **INVALID_AUTH** - Invalid API key
2. **INVALID_ARGUMENT** - Missing required fields
3. **PAYLOAD_TOO_LARGE** - Document exceeds max size
4. **INTERNAL** - Unexpected errors

### Error Scenarios (Deferred)
- **RATE_LIMIT** - Rate limiting (deferred until Kafka integration)

### ErrorMapper Utility
- Map internal exceptions to gRPC status codes
- Provide consistent error messages
- Handle gRPC-specific errors

## Chunking Strategy

### Configuration
- `quarkus.connector-intake.chunking-threshold=5242880` (5MB)
- Global service configuration in `application.properties`

### Implementation
- Repo-service already handles chunking
- Intake service just sends documents to repo-service
- Upload service in repo-service handles chunking logic

## Deduplication Strategy

### Primary Key
- `(connector_id + client_document_id)`

### Fallback Key
- `(connector_id + source_id)`

### Implementation
- Handled by repo-service
- Returns `was_update` flag
- Returns `previous_version` if updated

## Dependencies

### Connector Intake Service Dependencies
- `connector-service` (via gRPC)
- `repo-service` (via gRPC)
- Kafka (dependencies only, implementation deferred)

### Repo-Service Dependencies
- `account-service` (via gRPC)
- `connector-service` (via gRPC)

## Open Questions

1. **S3 Bucket Normalization** - Deferred until after MVP
2. **Rate Limiting** - Deferred until Kafka integration
3. **Observability** - Basic logging for MVP, detailed metrics deferred
4. **Encryption** - TBD default (SSE-S3 vs SSE-KMS)

## Success Criteria

### MVP Success Criteria
- [ ] Connector Intake Service can authenticate connectors via API key
- [ ] Connector Intake Service can stream documents to repo-service
- [ ] Repo-service can store documents with proper deduplication
- [ ] All tests pass (unit, integration, E2E)
- [ ] grpcurl scripts work for manual testing
- [ ] Service registers with Consul and Traefik
- [ ] Service can handle high-volume document ingestion

### Post-MVP Success Criteria
- [ ] Kafka integration for document counting
- [ ] Rate limiting implementation
- [ ] S3 bucket normalization
- [ ] Detailed observability and metrics

## Change Log

- **2025-10-22:** Initial plan created from comprehensive Q&A session
- **2025-10-22:** Flyway issue fixed in repo-service
- **2025-10-22:** Architecture decisions documented

## Next Steps

1. **Review this plan** - Ensure all decisions are documented
2. **Start Task 1** - Fix repo-service account management
3. **Create Task 2** - Set up connector-intake-service structure
4. **Implement Task 3** - Core streaming endpoint
5. **Test and iterate** - Use grpc-wiremock and grpcurl for testing
