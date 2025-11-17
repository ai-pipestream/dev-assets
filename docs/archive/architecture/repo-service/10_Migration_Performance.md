# Repository Service Architecture - Section 10: Migration & Performance

## Migration Status

**No Migration Required:**
- This is a new implementation, not a migration
- No existing data to migrate
- Fresh start with the new architecture

## Kafka Event Integration (Current Implementation)

**CRUD Event Publishing with Mutiny Emitters:**
```java
@ApplicationScoped
public class KafkaEventPublisher {
    
    @Inject
    @Channel("document-events")
    MutinyEmitter<DocumentEvent> documentEventEmitter;
    
    @Inject
    @Channel("drive-events")
    MutinyEmitter<DriveEvent> driveEventEmitter;
    
    public Uni<Void> publishDocumentCreated(Node node) {
        DocumentEvent event = DocumentEvent.newBuilder()
            .setEventType(EventType.CREATED)
            .setDocumentId(node.documentId)
            .setDriveId(node.driveId)
            .setNodeType(node.nodeType.code)
            .setS3Key(node.s3Key)
            .setSize(node.size)
            .setCreatedAt(Timestamp.newBuilder()
                .setSeconds(node.createdAt.toEpochSecond())
                .setNanos(node.createdAt.getNano())
                .build())
            .build();
            
        return documentEventEmitter.sendAndAwait(event);
    }
    
    public Uni<Void> publishDocumentUpdated(Node node) {
        DocumentEvent event = DocumentEvent.newBuilder()
            .setEventType(EventType.UPDATED)
            .setDocumentId(node.documentId)
            .setDriveId(node.driveId)
            .setNodeType(node.nodeType.code)
            .setS3Key(node.s3Key)
            .setSize(node.size)
            .setUpdatedAt(Timestamp.newBuilder()
                .setSeconds(node.updatedAt.toEpochSecond())
                .setNanos(node.updatedAt.getNano())
                .build())
            .build();
            
        return documentEventEmitter.sendAndAwait(event);
    }
    
    public Uni<Void> publishDocumentDeleted(String documentId, String s3Key) {
        DocumentEvent event = DocumentEvent.newBuilder()
            .setEventType(EventType.DELETED)
            .setDocumentId(documentId)
            .setS3Key(s3Key)
            .setDeletedAt(Timestamp.newBuilder()
                .setSeconds(System.currentTimeMillis() / 1000)
                .build())
            .build();
            
        return documentEventEmitter.sendAndAwait(event);
    }
}
```

**Service Integration with Mutiny:**
```java
@ApplicationScoped
public class DocumentService {
    
    @Inject
    NodeRepository nodeRepository;
    
    @Inject
    S3Service s3Service;
    
    @Inject
    KafkaEventPublisher eventPublisher;
    
    @Transactional
    public Uni<CreateDocumentResult> createDocument(CreateDocumentRequest request) {
        return Uni.createFrom().item(() -> {
            // ... existing create logic ...
            return result;
        }).chain(result -> {
            // Publish event
            return eventPublisher.publishDocumentCreated(node)
                .map(v -> result);
        });
    }
    
    @Transactional
    public Uni<UpdateDocumentResult> updateDocument(UpdateDocumentRequest request) {
        return Uni.createFrom().item(() -> {
            // ... existing update logic ...
            return result;
        }).chain(result -> {
            // Publish event
            return eventPublisher.publishDocumentUpdated(node)
                .map(v -> result);
        });
    }
    
    @Transactional
    public Uni<Boolean> deleteDocument(DeleteDocumentRequest request) {
        return Uni.createFrom().item(() -> {
            // ... existing delete logic ...
            return success;
        }).chain(success -> {
            if (success) {
                // Publish event
                return eventPublisher.publishDocumentDeleted(documentId, s3Key)
                    .map(v -> true);
            } else {
                return Uni.createFrom().item(false);
            }
        });
    }
}
```

**Event Metadata for Search:**
- **Document Events**: Enable search indexing and metadata updates
- **Drive Events**: Enable drive-level search and analytics
- **Upload Events**: Enable upload progress tracking and error monitoring
- **Event Correlation**: Link events to specific operations for audit trails

## Performance Considerations

**Database Optimization:**
- **Indexes**: Optimized for common query patterns (drive_id + name, document_id, upload_status)
- **Connection Pooling**: Configured for expected load
- **Query Optimization**: Uses Panache's efficient query methods

**S3 Optimization:**
- **Multi-part Uploads**: For large files (>5MB)
- **Concurrent Requests**: Parallel uploads for better throughput
- **Caching**: Local caching for frequently accessed payloads

**Memory Management:**
- **No Payload in Database**: Prevents memory bloat
- **Lazy Loading**: Payloads loaded on-demand from S3
- **Streaming**: Large payloads processed in chunks

## Monitoring and Observability

**Key Metrics:**
- **Database**: Connection pool usage, query performance, transaction metrics
- **S3**: Upload/download latency, error rates, storage usage
- **gRPC**: Request latency, error rates, throughput
- **Kafka**: Message publishing success/failure rates

**Health Checks:**
- **Database**: Connection and query health
- **S3**: Connectivity and permissions
- **Kafka**: Producer health and topic availability

## Key Benefits

1. **Event-Driven Architecture**: Enables search indexing and other downstream services
2. **Audit Trail**: Complete history of all CRUD operations
3. **Search Integration**: Events can trigger OpenSearch indexing
4. **Monitoring**: Upload progress and error tracking
5. **Extensibility**: Easy to add new event consumers
6. **Mutiny Integration**: Consistent with the rest of the reactive gRPC interface
7. **Async Event Publishing**: Non-blocking event publishing
8. **Error Handling**: Proper error propagation with Mutiny
9. **Transaction Safety**: Events published after successful database operations