Title: Connector, Account, and Intake MVP – Implementation Plan
Date: 2025-10-16
Owner: Junie (AI Product Planner)

Purpose
- Turn the answered questions (2025-10-16_product_questions_connector_repo.md) into a concrete, incremental plan and minimal contract decisions so multiple contributors can work in parallel.

Executive Summary
- We will implement three services in small, testable slices: Account (standalone MVP), Connector Registry/Admin (with cross-account support), and Connector Intake (streaming). Intake writes through to Repo-Service for S3 + DB. We standardize S3 key prefixes with connector context, use drive-based routing (pre-created buckets), and keep quotas and advanced observability for later. We’ll rely on grpc-wiremock for golden-path tests and MinIO + MySQL for integration.

Key Decisions (from your answers)
- Ownership/S3/Drives: Connectors specify drive; drives are pre-created and not shared between accounts. Repo decides bucket via drive. No bucket creation in code for MVP.
- S3 Keys: Standardize on connectors/{connector_id}/{document_id}.pb (aligned with Repo-Service summary). Node.path reflects source hierarchy and listing by DB queries.
- Dedup Key: Canonical dedup on (connector_id + client_document_id). Fallback to (connector_id + source_id). If checksum unchanged, return was_update=false; if updated, return previous_version (from S3 when available). 
- Chunking: Use 5MB default threshold (config property) for raw vs chunked; enforce in-order chunks per document. Per-account limits deferred.
- Authentication: Intake uses API key auth; keys scoped to connectors (managed by Connector Admin). Account service does not issue/validate keys in MVP.
- Cross-Account Connectors: In scope for MVP (many-to-many connector↔account mapping).
- Observability: Ad-hoc to start. Correlation via PipeStream/session_id/crawl_id/document_id in logs; basic PII redaction.
- Limits/Quotas: None for MVP.
- Deployment: Static config in dev; enable quarkus-consul-config, but keep static values.
- Orphans/Deletion: Defer delete-orphans and other side-effects beyond soft-deletes.
- Encryption: TBD default (SSE-S3 vs SSE-KMS). Keep secure defaults; no KMS integration in MVP.

Architecture Touchpoints
- Intake → Repo-Service: Intake constructs minimal Node metadata and forwards payload to Repo-Service (which stores to S3 and metadata to DB, emits events). Repo enforces drive/bucket mapping. Intake sets RequestContext correlation for events.
- Search/Indexing: Repo emits events; OpenSearch indexer can be added later (optional stub in MVP).

Phased Plan and Work Slices
1. Document decisions and contracts (this file) + Contract Deltas
   - Capture decisions (done here). Maintain a short Contract Deltas section for any small proto changes, kept minimal.

2. Account Service – Standalone MVP
   - Extract CreateAccount/GetAccount/InactivateAccount from repo-service into its own Quarkus app (same proto at grpc/grpc-stubs/.../account_service.proto).
   - Keep blocking Hibernate ORM; no API keys here. Provide grpc-wiremock stubs for clients.
   - Tests: golden-path grpc-wiremock; dev services for MySQL.

3. Connector Registry/Admin Service (with cross-account)
   - API: Prefer ConnectorAdminService in connector_intake_service.proto as the canonical admin API. Keep connector_service.proto minimal or deprecate after alignment.
   - Model: connectors table; status (ACTIVE/INACTIVE), name (platform-unique), description, api_key (hashed), created/updated timestamps, metadata json. Add connector_accounts m2m table for cross-account.
   - Endpoints: RegisterConnector, GetConnector, ListConnectors, SetConnectorStatus, DeleteConnector (soft), RotateApiKey (immediate old-key invalidation; record last_rotated_at).
   - Tests: unit for key rotation/status transitions; grpc-wiremock golden-path.

4. Connector Intake Service – Streaming MVP
   - Auth: SessionStart(connector_id, api_key). Validate using Connector Admin; get account_id and drive. Return ConnectorConfig { account_id, s3_bucket, s3_base_path=connectors/{connector_id}/ }.
   - Stream: Support raw_data (<5MB) and chunked (>5MB). Enforce in-order chunks per document. Config property for threshold.
   - Dedup + Updates: Primary key (connector_id + client_document_id), fallback (connector_id + source_id). If checksum unchanged, return was_update=false; else was_update=true with previous_version.
   - Repo Write-Through: Use Repo-Service to store payload and metadata; repo chooses bucket via drive; persist minimal metadata: account_id, connector_id, path, mime_type, size_bytes, checksum, timestamps, client IDs.
   - Errors: Standard taxonomy (INVALID_AUTH, INVALID_ARGUMENT, RATE_LIMIT, PAYLOAD_TOO_LARGE, INTERNAL). Per-document responses allow continuing the stream. Include retry guidance in docs.
   - Tests: E2E with MinIO + MySQL; grpc-wiremock for account/connector when needed.

5. Repo-Service validation/adjustments
   - Verify connector-aware key prefixes are supported; adjust if necessary.
   - Ensure RequestContext carries session_id/crawl_id/document_id for event correlation.
   - Ensure previous_version can be returned to Intake when updates occur.

6. Observability & Ops (light)
   - Logging fields: session_id, crawl_id, document_id. Add redaction for PII-like fields.
   - Metrics: Simple counters for docs ingested/failed and bytes; leave detailed plans for later.
   - Tracing: Use Quarkus defaults; no extra infra required for MVP.

7. Deployment & Config
   - Enable quarkus-consul-config (off by default in dev) to be ready; keep static configs.
   - Secrets: store only hashed API keys. Encryption default (SSE-S3 vs KMS) TBD.

Contract Deltas (Minimal, Proposed)
- Prefer using ConnectorAdminService messages for registry/admin operations instead of connector_service.proto to avoid duplicating similar concepts. If we keep both, add a minimal status field and optional account linkage to the smaller proto for parity, or mark it deprecated in docs.
- Intake: No wire changes required for MVP; we will compute s3_base_path, document_id, was_update, previous_version as defined.
- Account: No changes required for MVP.

Test Strategy
- Golden-path API tests with grpc-wiremock per service (no multi-service dev prerequisite).
- Integration tests (dev services): MinIO + MySQL for intake→repo E2E, validating S3 keys, metadata persistence, and events.
- Reuse sample docs from modules/parser resources.

Open Items (Explicitly Deferred)
- Encryption default (SSE-S3 vs SSE-KMS).
- Metrics taxonomy and placement strategy.
- InactivateAccount side-effects on drives/connectors.
- Orphan detection and auto-delete workflows.

Immediate Next Steps
- Align on Contract Deltas (if any) in a small PR.
- Start Phase 2 (Account extraction) and Phase 3 (Connector Admin) in parallel by separate contributors; Intake scaffolding can begin once basic admin endpoints are mocked via grpc-wiremock.

Change Log
- 2025-10-16: Initial plan created from answered questions and current repository design.
