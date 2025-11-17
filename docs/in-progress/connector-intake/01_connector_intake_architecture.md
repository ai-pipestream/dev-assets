# Connector-Intake Service Architecture

## Purpose
The Connector-Intake Service is the central ingestion point for all document connectors. It handles authentication, account management, metadata enrichment, and rate limiting, allowing connectors to be simple streaming clients.

Proto Reference
- Connector intake and admin services proto: `grpc/grpc-stubs/src/main/proto/module/connectors/connector_intake_service.proto`

## Architecture Position

```
┌─────────────────────────────────────────────────────────┐
│            Document Sources                              │
├─────────────┬──────────────┬──────────────┬────────────┤
│ FileSystem  │  Confluence  │   Database   │  Web APIs  │
│  Connector  │   Connector  │   Connector  │ Connector  │
└──────┬──────┴──────┬───────┴──────┬───────┴─────┬──────┘
       │             │               │              │
       └─────────────┴───────────────┴──────────────┘
                            │
                     gRPC Streaming
                            │
                            ↓
           ┌────────────────────────────────┐
           │  Connector-Intake Service      │
           │  - Authentication              │
           │  - Account Management          │
           │  - Metadata Enrichment         │
           │  - Rate Limiting               │
           │  - Crawl Session Tracking      │
           └────────────────┬───────────────┘
                            │
                            ↓
           ┌────────────────────────────────┐
           │      Repository Service        │
           │  - S3 Storage                  │
           │  - Deduplication               │
           │  - Version Management           │
           └────────────────┬───────────────┘
                            │
                         Events
                            │
                            ↓
           ┌────────────────────────────────┐
           │    Pipeline Processor          │
           └────────────────────────────────┘
```

## Core Responsibilities

### 1. Authentication & Authorization
- Validate connector credentials (API key)
- Map connector ID to account
- Enforce access policies

### 2. Account Management
- Look up account configuration
- Apply account-specific limits
- Track usage per account

### 3. Metadata Enrichment
- Add account metadata to documents
- Apply default tags/labels
- Set S3 paths based on account config

### 4. Rate Limiting
- Per-connector rate limits
- Per-account aggregate limits
- Backpressure to connectors

### 5. Crawl Session Management
- Track crawl sessions for orphan detection
- Monitor crawl progress
- Handle incremental updates

## Data Flow

### 1. Session Initiation
```proto
Connector → IntakeService: SessionStart {
  connector_id: "filesystem-prod-01",
  api_key: "xxx",
  crawl_id: "crawl-2025-01-14",
  metadata: {
    connector_type: "filesystem",
    source_system: "/data/documents"
  }
}

IntakeService → Connector: SessionResponse {
  authenticated: true,
  session_id: "session-123",
  config: {
    account_id: "acct-456",
    s3_bucket: "customer-data",
    s3_base_path: "connectors/filesystem/",
    max_file_size: 104857600
  }
}
```

### 2. Document Streaming
```proto
Connector → IntakeService: DocumentData {
  source_id: "/data/documents/report.pdf",
  filename: "report.pdf",
  path: "2024/Q4/",
  mime_type: "application/pdf",
  source_created: "2024-12-01T10:00:00Z",
  source_modified: "2024-12-15T14:30:00Z",
  raw_data: <bytes>
}

IntakeService → RepoService: EnrichedDocument {
  // Original fields plus:
  account_id: "acct-456",
  connector_id: "filesystem-prod-01",
  s3_path: "connectors/filesystem/2024/Q4/report.pdf",
  ingestion_time: "2025-01-14T10:00:00Z"
}
```

## Database Schema

### Connector Registration
```sql
CREATE TABLE connectors (
  id VARCHAR(100) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  type VARCHAR(50) NOT NULL,
  account_id VARCHAR(100) NOT NULL,
  api_key VARCHAR(255) NOT NULL,
  s3_bucket VARCHAR(255),
  s3_base_path VARCHAR(500),
  max_file_size BIGINT,
  rate_limit_per_minute INT,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP,
  FOREIGN KEY (account_id) REFERENCES accounts(id)
);
```

### Crawl Sessions
```sql
CREATE TABLE crawl_sessions (
  id VARCHAR(100) PRIMARY KEY,
  connector_id VARCHAR(100) NOT NULL,
  crawl_id VARCHAR(100) NOT NULL,
  state VARCHAR(50) NOT NULL,
  started_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP,
  documents_found INT DEFAULT 0,
  documents_processed INT DEFAULT 0,
  documents_failed INT DEFAULT 0,
  bytes_processed BIGINT DEFAULT 0,
  metadata JSONB,
  FOREIGN KEY (connector_id) REFERENCES connectors(id),
  UNIQUE(connector_id, crawl_id)
);
```

### Document Tracking (for orphan detection)
```sql
CREATE TABLE crawl_documents (
  crawl_session_id VARCHAR(100),
  document_id VARCHAR(100),
  source_id VARCHAR(500),
  processed_at TIMESTAMP,
  PRIMARY KEY (crawl_session_id, document_id),
  FOREIGN KEY (crawl_session_id) REFERENCES crawl_sessions(id)
);
```

## Configuration

### Application Properties
```properties
# Service Configuration
connector-intake.port=50051
connector-intake.max-message-size=104857600  # 100MB

# Repository Service Connection
connector-intake.repo-service.url=localhost:38102

# Rate Limiting
connector-intake.default-rate-limit=1000  # docs/minute
connector-intake.max-concurrent-streams=100

# Session Management
connector-intake.session-timeout-minutes=60
connector-intake.orphan-detection.enabled=true
```

## Security

### Authentication Flow
1. Connector provides ID and API key
2. Service validates against database
3. Session token generated
4. All subsequent calls use session token

### API Key Management
- Keys are hashed before storage (bcrypt)
- Keys can be rotated without downtime
- Keys can be revoked immediately

## Monitoring & Metrics

### Key Metrics
- Documents per second by connector
- Failed documents by type
- Average document size
- Session duration
- Queue depths

### Health Checks
- Database connectivity
- Repository service availability
- Memory usage
- Thread pool status

## Error Handling

### Retry Strategy
- Transient errors: Exponential backoff
- Permanent errors: Mark document failed, continue
- Session errors: Force re-authentication

### Circuit Breaker
- Trip on repeated repo-service failures
- Gradual recovery
- Alert on circuit open

## Next Steps

1. **Implementation**
   - Set up Quarkus project
   - Implement gRPC service
   - Add database layer
   - Connect to repo-service

2. **Testing**
   - Integration tests with repo-service and a sample connector
   - Load tests focused on streaming throughput

---

## Accounts (MVP)

Goal
- Provide a minimal account entity used to associate connectors and enrich ingested documents. No users/roles in v1; those will be added later in a dedicated account service.

Model (initial)
- `account_id` (string, primary key)
- `name` (string)
- `status` (enum: ACTIVE/INACTIVE)
- `created_at`, `updated_at`
- `default_bucket` (optional)
- `base_path` (optional)

Lifecycle
- Admin creates an account record and issues an API key at the end of creation.
- Connector registration requires a valid `account_id` and API key.

Enrichment
- Intake enriches each document with `{ account_id, connector_id }` and storage hints derived from the account (e.g., bucket/base path) before persisting via repo-service.

Ports
- All service ports are configurable; documentation lists defaults only. For example, web-proxy defaults to `38106` and repo-service to `38102`.

---

## Proposed gRPC API (Documentation Only)

Service: `ConnectorIntakeService`
- `RegisterConnector(RegisterConnectorRequest) → RegisterConnectorResponse`
  - Registers a connector under an account; returns metadata and a connector key or acknowledges existing registration.
- `WatchConnectors(WatchConnectorsRequest) → stream WatchConnectorsResponse`
  - Streams connector registrations/updates for observability.
- `StartSession(StartSessionRequest) → StartSessionResponse`
  - Authenticates with `connector_id` + API key; returns `session_id` and effective limits/config.
- `StreamDocuments(stream DocumentIntakeRequest) → StreamDocumentsResponse`
  - Client-streaming of document payloads; intake enriches and persists via repo-service.
- `EndSession(EndSessionRequest) → EndSessionResponse`
  - Completes a session; updates crawl/session stats.

Notes
- API definitions here are for planning; wire format will be finalized in `.proto` under `grpc/grpc-stubs` in a later step.
   - Unit tests for auth/enrichment
   - Integration tests with repo-service
   - Load testing for streaming

3. **Deployment**
   - Docker containerization
   - Kubernetes manifests
   - Service mesh integration
