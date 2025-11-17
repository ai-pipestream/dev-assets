# Connector Architecture Pattern

## Overview
The connector pattern separates document ingestion into three clean layers:

```
┌─────────────────────────┐
│  Connector Clients      │  (FileSystem, Confluence, Database, etc.)
│  - Simple streaming     │
│  - No auth logic        │
│  - Just sends docs      │
└───────────┬─────────────┘
            │ gRPC Stream
            ↓
┌─────────────────────────┐
│ Connector-Intake-Service│  (Authentication & Enrichment)
│  - Auth/Session mgmt    │
│  - Account lookup       │
│  - Metadata enrichment  │
│  - Rate limiting        │
└───────────┬─────────────┘
            │ Enriched
            ↓
┌─────────────────────────┐
│    Repo-Service         │  (Storage)
│  - S3 storage           │
│  - Deduplication        │
│  - Version tracking     │
└───────────┬─────────────┘
            │ Events
            ↓
┌─────────────────────────┐
│  Pipeline Processor     │  (Processing)
│  - Content extraction   │
│  - NLP/ML processing    │
│  - Indexing             │
└─────────────────────────┘
```

## Benefits

1. **Simple Connectors**: Connectors are just streaming clients - no complex logic
2. **Centralized Auth**: All authentication/authorization in one place
3. **Account Management**: Connector-intake enriches with account metadata
4. **Reusable Pattern**: Same pattern for filesystem, databases, APIs, etc.
5. **Scalable**: Each layer can scale independently

## Example: FileSystem Connector

```java
// Pseudo-code for filesystem connector
public class FileSystemConnector {
    private final ConnectorIntakeServiceStub intakeService;
    private final String connectorId;
    private final String apiKey;

    public void crawl(Path rootPath) {
        String crawlId = UUID.randomUUID().toString();

        // Start stream
        StreamObserver<DocumentIntakeRequest> stream =
            intakeService.streamDocuments(responseObserver);

        // Send session start
        stream.onNext(DocumentIntakeRequest.newBuilder()
            .setSessionStart(SessionStart.newBuilder()
                .setConnectorId(connectorId)
                .setApiKey(apiKey)
                .setCrawlId(crawlId)
                .setCrawlMetadata(CrawlMetadata.newBuilder()
                    .setConnectorType("filesystem")
                    .setSourceSystem(rootPath.toString())
                    .build())
                .build())
            .build());

        // Walk filesystem and stream documents
        Files.walk(rootPath)
            .filter(Files::isRegularFile)
            .forEach(file -> {
                // Read file
                byte[] content = Files.readAllBytes(file);

                // Send document
                stream.onNext(DocumentIntakeRequest.newBuilder()
                    .setDocument(DocumentData.newBuilder()
                        .setSourceId(file.toString())
                        .setFilename(file.getFileName().toString())
                        .setPath(rootPath.relativize(file.getParent()).toString())
                        .setMimeType(detectMimeType(file))
                        .setSizeBytes(content.length)
                        .setSourceCreated(toTimestamp(Files.getCreationTime(file)))
                        .setSourceModified(toTimestamp(Files.getLastModifiedTime(file)))
                        .setRawData(ByteString.copyFrom(content))
                        .build())
                    .build());
            });

        stream.onCompleted();
    }
}
```

## Connector-Intake Responsibilities

The connector-intake-service handles:

1. **Authentication**: Validates connector ID and API key
2. **Account Lookup**: Finds account metadata for the connector
3. **Enrichment**: Adds account ID, default metadata, S3 paths
4. **Rate Limiting**: Enforces per-connector rate limits
5. **Session Management**: Tracks crawl sessions
6. **Orphan Detection**: Tracks documents per crawl for cleanup

## Implementation Plan

### Phase 1: Connector-Intake-Service
- [ ] Create new Quarkus service
- [ ] Implement authentication/session management
- [ ] Connect to repo-service for storage
- [ ] Add connector registration API

### Phase 2: FileSystem Connector
- [ ] Create standalone Java/Quarkus app
- [ ] Implement filesystem walking
- [ ] Stream documents to intake service
- [ ] Add configuration for paths, filters, etc.

### Phase 3: Additional Connectors
- [ ] Confluence connector
- [ ] Database connector
- [ ] S3/Cloud storage connector
- [ ] Web crawler connector

## Key Design Decisions

1. **Streaming over Batch**: Use gRPC streaming for memory efficiency
2. **Source Metadata Preservation**: Keep all source system metadata
3. **Crawl Tracking**: Track crawl sessions for orphan detection
4. **Simple Clients**: Connectors are thin clients, no business logic
5. **Central Configuration**: All config in connector-intake, not clients