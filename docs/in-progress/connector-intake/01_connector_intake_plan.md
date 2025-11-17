# Connector-Intake Service Implementation Plan

## Overview
The `connector-intake-service` is responsible for receiving document streams from external connectors, authenticating them, enriching metadata, and persisting documents to the repository service. It is the central ingestion gateway for all connector-sourced content.

## Service Boundaries

### What This Service Does
- **Document Streaming**: Accept bidirectional streaming of documents from connectors via gRPC
- **Authentication**: Validate connector API keys against `connector-service`
- **Session Management**: Track crawl sessions for monitoring and orphan detection
- **Metadata Enrichment**: Add account context and connector metadata to documents
- **Repository Integration**: Store documents via `repository-service` gRPC API
- **Rate Limiting**: Enforce per-connector and per-account rate limits
- **Heartbeat Monitoring**: Track connector health and allow server control commands

### What This Service Does NOT Do
- **Connector Administration**: The existing `connector-service` handles connector CRUD, API key rotation, etc.
- **Account Management**: The `account-manager` handles account lifecycle
- **Document Processing**: Pipeline processors handle extraction, enrichment, etc.
- **Direct S3 Access**: All storage goes through `repository-service`

## Architecture Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                  External Connectors                            │
│  (Filesystem, Confluence, Database, Web APIs, etc.)             │
└────────────────────────┬────────────────────────────────────────┘
                         │ gRPC Streaming
                         ↓
         ┌───────────────────────────────────────┐
         │   connector-intake-service            │
         │   - StreamDocuments                   │
         │   - StartCrawlSession                 │
         │   - EndCrawlSession                   │
         │   - Heartbeat                         │
         └─────┬──────────────┬──────────────────┘
               │              │
               │              └────────────────────────┐
               │                                       │
               │ gRPC (validate API key)               │ gRPC (store docs)
               ↓                                       ↓
    ┌──────────────────────┐            ┌─────────────────────────┐
    │  connector-service   │            │  repository-service     │
    │  - Validate API Key  │            │  - CreateNode           │
    │  - Get Connector     │            │  - Store to S3          │
    │  - Get Config        │            │  - Deduplication        │
    └──────────────────────┘            └─────────────────────────┘
               │                                       │
               │ gRPC (validate account)               │ Kafka Events
               ↓                                       ↓
    ┌──────────────────────┐            ┌─────────────────────────┐
    │   account-manager    │            │   Pipeline Processors   │
    │   - GetAccount       │            └─────────────────────────┘
    └──────────────────────┘
```

## Proto Definition Review

### ✅ Current Proto is Good
The existing proto at `grpc/grpc-stubs/src/main/proto/module/connectors/connector_intake_service.proto` is well-designed and covers all requirements.

### Minor Clarifications Needed

1. **`ConnectorConfig.account_id` Source**
   - Where does this come from? Options:
     - A) Fetch from `connector-service` via `GetConnector` RPC (connector has account link)
     - B) Fetch from `account-manager` directly
   - **Recommendation**: Option A - connector-service already links connectors to accounts via the `connector_accounts` junction table

2. **Session Authentication Flow**
   - When `SessionStart` is received with `connector_id` + `api_key`:
     1. Call `connector-service.ValidateApiKey(connector_id, api_key)` - **DOES THIS RPC EXIST?**
     2. If not, call `connector-service.GetConnector(connector_id)` and validate API key hash locally
   - **Recommendation**: Add a `ValidateApiKey` RPC to `connector-service` for cleaner separation

3. **Repository Service Integration**
   - Use `FilesystemService.CreateNode` for document storage
   - Map connector intake fields to CreateNodeRequest:
     - `drive` → from connector config (default or connector-specific)
     - `document_id` → generate UUID or use `client_document_id` if provided
     - `connector_id` → from session
     - `name` → from `DocumentData.filename`
     - `path` → from `DocumentData.path`
     - `content_type` → from `DocumentData.mime_type`
     - `payload` → from `DocumentData.raw_data` or assembled chunks
     - `metadata` → JSON with connector metadata, source metadata, account_id, etc.

4. **Orphan Detection Strategy**
   - Architecture doc mentions tracking documents per crawl session
   - **Question**: Should we implement this in v1 or defer to v2?
   - **Recommendation**: Implement basic tracking (store `source_id` per session in DB) but defer deletion logic to v2

## Database Schema

### New Database: `pipeline_connector_intake_dev`

```sql
-- Crawl Sessions
CREATE TABLE crawl_sessions (
  id VARCHAR(100) PRIMARY KEY,                 -- Generated session ID
  connector_id VARCHAR(100) NOT NULL,          -- FK to connector-service (not enforced cross-DB)
  crawl_id VARCHAR(100) NOT NULL,              -- Client-provided crawl ID
  account_id VARCHAR(100) NOT NULL,            -- Copied from connector for queries
  state VARCHAR(50) NOT NULL,                  -- RUNNING, COMPLETED, FAILED, TERMINATED
  started_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP,

  -- Statistics
  documents_found INT DEFAULT 0,
  documents_processed INT DEFAULT 0,
  documents_failed INT DEFAULT 0,
  documents_skipped INT DEFAULT 0,
  bytes_processed BIGINT DEFAULT 0,

  -- Configuration
  track_documents BOOLEAN DEFAULT FALSE,       -- Enable orphan detection tracking
  delete_orphans BOOLEAN DEFAULT FALSE,        -- Delete orphans at end

  -- Metadata
  connector_type VARCHAR(50),
  source_system VARCHAR(500),
  metadata JSONB,                              -- CrawlMetadata as JSON

  UNIQUE(connector_id, crawl_id),
  INDEX idx_account_id (account_id),
  INDEX idx_state (state),
  INDEX idx_started_at (started_at)
);

-- Document Tracking (for orphan detection)
CREATE TABLE crawl_documents (
  crawl_session_id VARCHAR(100) NOT NULL,
  source_id VARCHAR(500) NOT NULL,             -- Connector's source system ID
  document_id VARCHAR(100) NOT NULL,            -- Repository document ID (UUID)
  processed_at TIMESTAMP NOT NULL,

  PRIMARY KEY (crawl_session_id, source_id),
  FOREIGN KEY (crawl_session_id) REFERENCES crawl_sessions(id) ON DELETE CASCADE,
  INDEX idx_document_id (document_id)
);

-- Session Authentication Cache (optional optimization)
-- Caches validated sessions to reduce calls to connector-service
CREATE TABLE session_cache (
  session_id VARCHAR(100) PRIMARY KEY,
  connector_id VARCHAR(100) NOT NULL,
  account_id VARCHAR(100) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  config_json JSON NOT NULL,                   -- ConnectorConfig as JSON

  INDEX idx_connector_id (connector_id),
  INDEX idx_expires_at (expires_at)
);
```

### Flyway Migration Structure
```
src/main/resources/db/migration/
  V1__create_crawl_sessions.sql
  V2__create_crawl_documents.sql
  V3__create_session_cache.sql
```

## Implementation Steps

### Phase 1: Project Setup & Skeleton ✅ (Junie is doing this)
1. Create Quarkus project with Gradle
2. Add dependencies (same as connector-service)
3. Generate gRPC stubs from proto
4. Create empty service implementations
5. Set up database (MySQL via Docker Compose)
6. Configure Flyway migrations
7. Configure dynamic-grpc for service discovery

### Phase 2: Authentication & Session Management
**Files to Create:**
- `src/main/java/io/pipeline/connector/intake/service/ConnectorValidationService.java`
- `src/main/java/io/pipeline/connector/intake/service/SessionManager.java`
- `src/main/java/io/pipeline/connector/intake/entity/CrawlSession.java`
- `src/main/java/io/pipeline/connector/intake/repository/CrawlSessionRepository.java`

**Responsibilities:**
1. **ConnectorValidationService**
   - Inject `DynamicGrpcClientFactory`
   - Call `connector-service` to validate API key
   - Call `connector-service.GetConnector(connector_id)` to fetch config
   - Extract account_id from connector
   - Call `account-manager.GetAccount(account_id)` to validate account is active
   - Return `ConnectorConfig` with all metadata

2. **SessionManager**
   - Generate session IDs (UUID)
   - Store sessions in database
   - Manage session lifecycle (RUNNING → COMPLETED/FAILED)
   - Track session statistics
   - Handle session timeouts (background cleanup job)

3. **Session State Machine**
   ```
   RUNNING → COMPLETED (normal end)
   RUNNING → FAILED (error during crawl)
   RUNNING → TERMINATED (server command or timeout)
   ```

### Phase 3: Document Streaming Implementation
**Files to Create:**
- `src/main/java/io/pipeline/connector/intake/service/ConnectorIntakeServiceImpl.java`
- `src/main/java/io/pipeline/connector/intake/service/DocumentProcessor.java`
- `src/main/java/io/pipeline/connector/intake/service/RepositoryClient.java`
- `src/main/java/io/pipeline/connector/intake/service/ChunkAssembler.java`

**Responsibilities:**
1. **ConnectorIntakeServiceImpl.StreamDocuments**
   - Handle bidirectional streaming
   - Expect first message to be `SessionStart`
   - Validate session using `ConnectorValidationService`
   - Return `SessionStartResponse` with `ConnectorConfig`
   - Stream subsequent `DocumentData` messages to `DocumentProcessor`
   - Return `DocumentResponse` for each processed document
   - Handle errors and backpressure

2. **DocumentProcessor**
   - Validate document metadata (required fields, size limits)
   - Enforce rate limits (using Guava RateLimiter or similar)
   - Check if content is `raw_data` or chunked
   - If chunked, delegate to `ChunkAssembler`
   - Enrich metadata (add account_id, connector_id, ingestion_time)
   - Call `RepositoryClient` to store document
   - Update session statistics
   - Track document in `crawl_documents` table if orphan detection enabled

3. **ChunkAssembler**
   - Maintain in-memory map of `document_ref` → assembled chunks
   - Validate chunk sequence numbers
   - Detect `is_last` and assemble complete document
   - Validate checksum if provided
   - Clean up partial chunks on timeout

4. **RepositoryClient**
   - Inject `DynamicGrpcClientFactory`
   - Call `repository-service.CreateNode` via dynamic-grpc
   - Map connector document to `CreateNodeRequest`:
     ```java
     CreateNodeRequest.newBuilder()
       .setDrive(connectorConfig.getS3Bucket()) // or default drive
       .setDocumentId(generateOrUseDocumentId())
       .setConnectorId(session.getConnectorId())
       .setName(doc.getFilename())
       .setPath(doc.getPath())
       .setContentType(doc.getMimeType())
       .setPayload(Any.pack(BytesValue.of(doc.getRawData())))
       .setMetadata(buildMetadataJson(doc, session))
       .setType(Node.NodeType.FILE)
       .build()
     ```
   - Handle errors (retries, circuit breaker)
   - Track success/failure metrics

### Phase 4: Crawl Session Management
**Files to Create:**
- `src/main/java/io/pipeline/connector/intake/entity/CrawlDocument.java`
- `src/main/java/io/pipeline/connector/intake/repository/CrawlDocumentRepository.java`

**Implement RPCs:**
1. **StartCrawlSession**
   - Validate connector credentials (same as StreamDocuments)
   - Create session in database with RUNNING state
   - Return session_id and crawl_id

2. **EndCrawlSession**
   - Find session by session_id and crawl_id
   - Update statistics from `CrawlSummary`
   - Set state to COMPLETED
   - If `delete_orphans` was enabled:
     - Query previous crawl session for same connector
     - Find documents in previous crawl NOT in current crawl
     - Mark as orphans (don't delete in v1, just log)
   - Return orphan count

3. **Heartbeat**
   - Validate session exists and is RUNNING
   - Update last_heartbeat timestamp (add column to crawl_sessions)
   - Update queued/processing metrics
   - Return session status and control commands:
     - CONTINUE (default)
     - THROTTLE (if rate limit hit)
     - PAUSE (future feature)
     - STOP (if connector disabled or account inactive)

### Phase 5: Rate Limiting & Backpressure
**Files to Create:**
- `src/main/java/io/pipeline/connector/intake/service/RateLimiter.java`

**Implementation:**
1. Use Guava `RateLimiter` per connector_id
2. Initialize from `ConnectorConfig.rate_limit_per_minute`
3. On rate limit hit:
   - Send `ControlCommand.THROTTLE` in next DocumentResponse
   - Apply backpressure on gRPC stream
   - Log rate limit events

### Phase 6: Configuration & Deployment
**Configuration:**
```properties
# Service Configuration
quarkus.application.name=connector-intake-service
quarkus.http.port=38108

# gRPC Configuration
quarkus.grpc.server.use-separate-server=false
quarkus.grpc.server.enable-health-service=true
quarkus.grpc.server.enable-reflection-service=true
quarkus.grpc.server.max-inbound-message-size=104857600  # 100MB

# Database Configuration
quarkus.datasource.db-kind=mysql
quarkus.datasource.username=pipeline
quarkus.datasource.password=password
%dev.quarkus.datasource.jdbc.url=jdbc:mysql://localhost:3306/pipeline_connector_intake_dev

# Flyway
%dev.quarkus.hibernate-orm.schema-management.strategy=none
%dev.quarkus.flyway.migrate-at-start=true

# Dynamic gRPC - Service Discovery
service.registration.enabled=true
service.registration.service-name=connector-intake-service
service.registration.description=Document ingestion service for connectors
service.registration.service-type=APPLICATION
service.registration.capabilities=document-intake,crawl-session-management

# Connector Service Client (via dynamic-grpc)
# No explicit config needed - dynamic-grpc uses Consul for discovery

# Repository Service Client (via dynamic-grpc)
# No explicit config needed - dynamic-grpc uses Consul for discovery

# Rate Limiting Defaults
connector-intake.default-rate-limit-per-minute=1000
connector-intake.max-concurrent-streams=100

# Session Management
connector-intake.session-timeout-minutes=60
connector-intake.session-cleanup-interval-minutes=10

# Chunk Assembly
connector-intake.chunk-assembly-timeout-minutes=30
connector-intake.max-chunk-size-mb=10

# Document Limits
connector-intake.max-document-size-mb=100
connector-intake.max-filename-length=255
```

**Build.gradle:**
```gradle
plugins {
    alias(libs.plugins.java)
    alias(libs.plugins.quarkus)
}

dependencies {
    // Use published BOM from Maven Local
    implementation platform('io.pipeline:pipeline-bom:1.0.0-SNAPSHOT')

    // Core Quarkus
    implementation 'io.quarkus:quarkus-arc'
    implementation 'io.quarkus:quarkus-grpc'
    implementation 'io.grpc:grpc-services'
    implementation 'io.quarkus:quarkus-hibernate-orm-panache'
    implementation 'io.quarkus:quarkus-jdbc-mysql'
    implementation 'io.quarkus:quarkus-flyway'
    implementation 'org.flywaydb:flyway-mysql'
    implementation 'io.quarkus:quarkus-smallrye-health'

    // Service discovery
    implementation 'io.quarkus:quarkus-smallrye-stork'
    implementation 'io.smallrye.stork:stork-service-discovery-consul'
    implementation 'io.smallrye.reactive:smallrye-mutiny-vertx-consul-client'

    // Pipeline libraries
    implementation 'io.pipeline:grpc-stubs:1.0.0-SNAPSHOT'
    implementation 'io.pipeline:dynamic-grpc-registration-clients:1.0.0-SNAPSHOT'
    implementation 'io.pipeline:dynamic-grpc:1.0.0-SNAPSHOT'

    // Utilities
    implementation 'com.google.guava:guava:33.0.0-jre'  // For RateLimiter

    // Testing
    testImplementation 'io.quarkus:quarkus-junit5'
    testImplementation 'io.pipeline:grpc-wiremock:1.0.0-SNAPSHOT'
    testImplementation 'io.rest-assured:rest-assured'
}

java {
    sourceCompatibility = JavaVersion.VERSION_21
    targetCompatibility = JavaVersion.VERSION_21
}
```

### Phase 7: Testing Strategy

**Unit Tests:**
- `ConnectorValidationServiceTest` - Mock gRPC calls to connector-service and account-manager
- `DocumentProcessorTest` - Test metadata enrichment and validation
- `ChunkAssemblerTest` - Test chunk assembly logic, checksums
- `SessionManagerTest` - Test session lifecycle
- `RateLimiterTest` - Test rate limiting logic

**Integration Tests:**
- `ConnectorIntakeServiceIntegrationTest` - Full streaming flow with WireMock for dependencies
- `RepositoryIntegrationTest` - Test actual gRPC calls to repository-service (Docker Compose)
- `DatabaseIntegrationTest` - Test Panache repositories with test database

**E2E Tests:**
- Create a simple test connector client
- Stream test documents through connector-intake-service
- Verify documents appear in repository-service
- Verify crawl sessions are tracked correctly

## Error Handling Strategy

### gRPC Status Codes
- `UNAUTHENTICATED` - Invalid API key
- `PERMISSION_DENIED` - Connector disabled or account inactive
- `INVALID_ARGUMENT` - Missing required fields, invalid data
- `RESOURCE_EXHAUSTED` - Rate limit exceeded
- `FAILED_PRECONDITION` - Session not started, invalid state
- `NOT_FOUND` - Connector or account not found
- `INTERNAL` - Unexpected errors

### Retry Strategy
- Transient repository errors → Retry with exponential backoff (3 attempts)
- Permanent errors (INVALID_ARGUMENT) → Fail document, continue stream
- Session errors (UNAUTHENTICATED) → Terminate session, force re-auth

### Circuit Breaker
- Monitor repository-service availability
- Trip circuit after 5 consecutive failures
- Half-open after 30 seconds
- Alert on circuit open

## Monitoring & Metrics

### Key Metrics (Micrometer)
- `connector_intake.documents.received` - Counter by connector_id
- `connector_intake.documents.processed` - Counter by connector_id, status
- `connector_intake.documents.failed` - Counter by connector_id, error_code
- `connector_intake.bytes.received` - Counter by connector_id
- `connector_intake.session.active` - Gauge
- `connector_intake.session.duration` - Timer by connector_id
- `connector_intake.rate_limit.hits` - Counter by connector_id
- `connector_intake.repository.latency` - Timer

### Health Checks
- Database connectivity
- Connector-service reachability (via gRPC health check)
- Repository-service reachability
- Session cleanup job status

### Logging
- Session start/end with connector_id, account_id
- Document processing errors with source_id
- Rate limit events
- API validation failures

## Open Questions & Decisions Needed

### 1. **API Key Validation RPC**
Does `connector-service` have a `ValidateApiKey(connector_id, api_key)` RPC?
- If YES: Use it directly
- If NO: Should we add it, or use `GetConnector` + local hash validation?

**Recommendation**: Add `ValidateApiKey` RPC to connector-service for better separation of concerns.

### 2. **Orphan Detection v1 Scope**
Should we implement orphan detection in v1 or defer to v2?
- Track documents: YES (simple, just insert to crawl_documents table)
- Delete orphans: DEFER to v2 (complex, needs careful design)

**Recommendation**: Track in v1, delete in v2.

### 3. **Session Timeout Handling**
How should we handle sessions that never call `EndCrawlSession`?
- Background job to mark sessions as FAILED after timeout (default: 60 minutes of inactivity)
- Require heartbeats to keep session alive?

**Recommendation**: Both - heartbeat optional but recommended, timeout as safety net.

### 4. **Document ID Generation**
Who generates the document ID?
- Client provides `client_document_id` (for deduplication)
- Server generates UUID as primary `document_id`

**Recommendation**: Server generates UUID, use `client_document_id` for deduplication logic in repository-service.

### 5. **Drive Selection Strategy**
How do we determine which "drive" (S3 bucket) to use?
- Default drive from connector config?
- Per-account drive?
- Connector-specific drive?

**Recommendation**: Fetch from connector metadata (connector-service already stores `s3_bucket` and `s3_base_path` in metadata JSON).

### 6. **Proto Changes Needed?**
Based on this plan, are there any changes needed to the proto definition?

**Potential Additions:**
1. Add `ValidateApiKey` RPC to `ConnectorAdminService` (in connector_intake_service.proto):
   ```protobuf
   rpc ValidateApiKey(ValidateApiKeyRequest) returns (ValidateApiKeyResponse);

   message ValidateApiKeyRequest {
     string connector_id = 1;
     string api_key = 2;
   }

   message ValidateApiKeyResponse {
     bool valid = 1;
     string message = 2;
     ConnectorRegistration connector = 3;  // If valid, return full config
   }
   ```

2. Add `last_heartbeat` to `HeartbeatRequest` timestamp?
   - Current proto has metrics but no timestamp
   - **Recommendation**: Server tracks it, no proto change needed

## Success Criteria

### Phase 1 Complete (Skeleton)
- ✅ Project compiles and builds
- ✅ gRPC service starts and registers with Consul
- ✅ Database migrations run successfully
- ✅ Health checks pass
- ✅ All service methods return NOT_IMPLEMENTED

### Phase 2 Complete (Authentication)
- ✅ Can validate connector API key via connector-service
- ✅ Can fetch connector config and account info
- ✅ Session created and stored in database
- ✅ Unit tests pass

### Phase 3 Complete (Document Streaming)
- ✅ Can stream documents from test connector
- ✅ Documents stored in repository-service
- ✅ Chunk assembly works for large files
- ✅ Metadata enrichment includes account_id, connector_id
- ✅ Integration tests pass

### Phase 4 Complete (Session Management)
- ✅ StartCrawlSession, EndCrawlSession, Heartbeat all working
- ✅ Session statistics updated correctly
- ✅ Orphan tracking writes to database (deletion deferred to v2)

### Phase 5 Complete (Rate Limiting)
- ✅ Rate limits enforced per connector
- ✅ Backpressure applied on rate limit
- ✅ Control commands sent to connector

### Phase 6 Complete (Deployment)
- ✅ Docker container builds
- ✅ Service runs in Docker Compose with other services
- ✅ Can be discovered via Consul
- ✅ Metrics exposed and scraping

### Phase 7 Complete (Testing)
- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ E2E test with real connector client works
- ✅ Load test shows target throughput (1000 docs/min)

## Timeline Estimate

- **Phase 1** (Skeleton): ✅ Junie completing now
- **Phase 2** (Authentication): 1 day
- **Phase 3** (Document Streaming): 2 days
- **Phase 4** (Session Management): 1 day
- **Phase 5** (Rate Limiting): 0.5 day
- **Phase 6** (Configuration): 0.5 day
- **Phase 7** (Testing): 1 day

**Total**: ~6 days of development time

## Next Steps

1. **Review this plan** - Confirm architecture and decisions
2. **Answer open questions** - Especially API key validation and proto changes
3. **Wait for Junie** - Let skeleton generation complete
4. **Begin Phase 2** - Start with authentication and session management
5. **Iterate** - Test each phase before moving to next

---

**Document Version**: 1.0
**Last Updated**: 2025-01-26
**Author**: Claude (with input from human architect)
