# Repository Service Remediation Master Plan (Final)

## 1. Overview and Goal

This document outlines a detailed, step-by-step plan to remediate the critical architectural issues in the `repository-service`. **This plan is a synthesis of the best insights from multiple LLM assessments and our final architectural decisions.** It prioritizes a clean, modern, and efficient design, as we do not need to maintain backward compatibility.

### **Architectural Mandates (The Final Design)**

1.  **Service Architecture**: The repository will have a two-tier service architecture:
    *   **`FilesystemService` (Core Engine)**: A generic service responsible for the fundamental operations of storing and retrieving `google.protobuf.Any` payloads. Its API will remain pure and type-agnostic.
    *   **`TypedRepositoryService` (Convenience Facade)**: A separate, new service to be built later. It will provide strongly-typed helper methods (e.g., `GetPipeDoc`) for common use cases, calling the generic `FilesystemService` internally.
2.  **Client-Provided IDs**: The service will **not** generate `document_id`s. The calling client is responsible for providing a stable, unique identifier for each document.
3.  **S3 Versioning for Updates**: When a document is uploaded with a pre-existing `document_id`, it is treated as an update. S3 versioning will be used to manage document history, and the database will point to the specific S3 object `versionId`.
4.  **Lean Events**: Events are lightweight notifications of a state change (e.g., `Created`, `Updated`). They contain IDs and data about the change itself (`s3_key`, `checksum`, `s3_version_id`), but **not** the full entity metadata.
5.  **Database as Single Source of Truth (SSOT)**: The `Node` entity in the database is the authoritative source for all document metadata (`name`, `path`, `parent_id`, `content_type`, etc.).
6.  **Logical Deduplication via Content Hash**: The service will calculate a SHA-256 `content_hash` for every document version. This allows for metadata-level discovery of identical content.
7.  **Structured S3 Keys**: The `s3Key` will follow the clear, namespaced format: `connectors/{connector_id}/{document_id}.pb`.

This plan is structured to support a **PR slicing strategy** for incremental, reviewable changes.

---

## 2. Phased Implementation Plan

### **PR #1: Aggressive Event Schema Overhaul**

*   **Objective**: Rip and replace the old event schema with the new, lean `RepositoryEvent` design. This is the most impactful change and sets the foundation for the new architecture.
*   **Files**: `grpc/grpc-stubs/src/main/proto/repository/filesystem/repository_events.proto`, `ReactiveEventPublisherImpl.java`.
*   **Changes**:
    1.  **Delete Old Events**: Remove `DocumentEvent`, `DocumentCreated`, `DocumentUpdated`, etc.
    2.  **Create `RepositoryEvent`**: Implement the new, clean schema as defined below.
    3.  **Refactor Publisher**: Completely refactor `ReactiveEventPublisherImpl.java` to build and publish this new `RepositoryEvent`.
*   **New `RepositoryEvent` Schema**:
    ```protobuf
    // The new, lean event for state change notifications
    message RepositoryEvent {
      // Deterministic ID: hash(document_id + operation + timestamp_millis)
      string event_id = 1;
      google.protobuf.Timestamp timestamp = 2;
      string document_id = 3;        // The client-provided ID of the entity that changed
      string customer_id = 4;         // The customer context for this event
      SourceContext source = 5;       // Detailed audit context

      oneof operation {
        Created created = 10;
        Updated updated = 11;
        Deleted deleted = 12;
      }
    }

    // Contains only data about the NEW version created in storage
    message Created {
      string s3_key = 1;
      int64 size = 2;
      string checksum = 3;          // SHA-256 hash of the content
      string s3_version_id = 4;     // The version ID of the new S3 object
    }

    // Contains data about the new version and a pointer to the old one
    message Updated {
      string s3_key = 1;
      int64 size = 2;
      string checksum = 3;          // SHA-256 hash of the new content
      string s3_version_id = 4;     // The version ID of the new S3 object
      string previous_s3_version_id = 5; // The version this update replaces
    }

    message Deleted {
      string reason = 1;
    }

    // Detailed and required context for all events
    message SourceContext {
      string component = 1;          // e.g., "repository-service", "connector-gutenberg"
      string operation = 2;          // e.g., "createDocument", "uploadChunks"
      string request_id = 3;         // For tracing
    }
    ```
*   **Verification**: All event-related tests must be rewritten to validate this new lean structure. Assert that events are small and contain no PII or entity metadata beyond what's specified.

### **PR #2: S3 Persistence & Hydration Correctness**

*   **Objective**: Solidify the core data read/write lifecycle according to the new architecture.
*   **Changes**:
    1.  **Standardize S3 API**: Ensure `S3Service` methods accept a full, explicit `s3Key` and remove any internal key-derivation logic.
    2.  **Correct Write Path**: Implement the `Any.pack()` -> `any.toByteArray()` -> S3 storage flow in `DocumentService.java`.
    3.  **Correct Read Path**: Implement the S3 `byte[]` -> `Any.parseFrom(bytes)` -> gRPC response flow.
*   **Verification**: Tests must confirm that the `s3Key` bug is gone and that `Any` payloads can be round-tripped to/from S3 without data corruption.

### **PR #3: Multipart Upload End-to-End Fix**

*   **Objective**: Ensure large file uploads are handled correctly via streaming and that the final metadata is accurate.
*   **Changes**:
    1.  Refactor `NodeUploadServiceImpl.java` to use the S3 async client's multipart upload capabilities, streaming chunks directly.
    2.  After the upload completes, perform a `HEAD` request on the S3 object to get its exact final size.
    3.  Use this accurate size when creating the final `Node` record in the database.
*   **Verification**: An integration test must upload a file > 5MB, confirm low memory usage, and assert the final `Node` entity's `size` property matches the actual S3 object size.

### **PR #4: Implement New Core Business Logic**

*   **Objective**: Rework the service to use client-provided IDs, content hashing, structured keys, and S3 versioning.
*   **Changes**:
    1.  **gRPC Proto Update**: Add `string document_id` and `string connector_id` to `CreateNodeRequest`.
    2.  **DB Schema Update**: Add `content_hash` (VARCHAR(64)) and `s3_version_id` (VARCHAR) columns to the `documents` table. Update the `Node.java` entity.
    3.  **S3 Service Update**: Ensure the `upload` methods return the `versionId` from the S3 API response.
    4.  **Content Hashing**: In `DocumentService.java`, implement the SHA-256 hashing of the raw payload.
    5.  **Key Construction**: Implement the `connectors/{connector_id}/{document_id}.pb` key structure.
    6.  **Create-vs-Update Logic**: Implement the core logic to check if a `document_id` exists. If not, create a new `Node`. If yes, update the existing `Node` with the new `s3_version_id` and other version-specific metadata.
*   **Verification**: Tests must prove the create-vs-update logic works correctly and that all new fields (`content_hash`, `s3_version_id`, `s3Key`) are populated as expected.

---

## 3. Architectural Notes & Testing

### **Service Layer Design (`FilesystemService` vs. `TypedRepositoryService`)**

As per our discussion, the old specialized services (`PipeDocRepositoryService`, etc.) are deprecated, and their proto files have been removed. The new architecture is as follows:

*   **`FilesystemService`**: This is the core, generic engine we are currently fixing. Its public API, defined in `filesystem_service.proto`, will remain pure and deal only with `google.protobuf.Any` payloads. It has no knowledge of specific business objects like `PipeDoc`.

*   **`TypedRepositoryService` (Future)**: To provide developer convenience, a *new* service will be created later (e.g., in `typed_repository_service.proto`). This service will act as a facade. It will contain strongly-typed RPCs like `GetPipeDoc(GetPipeDocRequest) returns (PipeDoc)`. Internally, it will call the generic `FilesystemService` to fetch the `Any` payload and then perform the `unpack()` operation before returning the result to its client.

### **Testing and Validation**

*   **Test-Driven Development**: Each change should begin with a failing test that proves the bug or missing feature.
*   **Test Constraints**: All tests must adhere to the project's established infrastructure and not attempt to start containers outside the `compose-test-services.yml` framework.
*   **Grep Guards**: As a final check, add build steps or manual checks to `grep` for forbidden patterns to prevent regressions.