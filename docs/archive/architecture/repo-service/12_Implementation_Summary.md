# Repository Service Implementation Summary

## 🎉 MAJOR REFACTOR COMPLETE (90% Done) - January 14, 2025

### Critical Architecture Fix Achieved
**The 12MB Kafka payload problem has been completely resolved.** Kafka events now contain only metadata (~75 bytes) while actual document payloads are stored in S3/MinIO. This was the core architectural violation that cost months of debugging.

## Overview

This document summarizes the complete implementation of the Repository Service, including the lessons learned from the 2-month Hibernate Reactive struggle and the final hybrid architecture solution.

## Architecture Decisions

### Hybrid Reactive Architecture (Final Solution)

**The Winning Pattern:**
```
gRPC Layer: Reactive Mutiny stubs
  ↓
Service Layer: Mixed (Smart!)
  ├── Database: Blocking Hibernate ORM ✅ (reliable, debuggable)
  ├── S3: Reactive S3AsyncClient ✅ (better performance)
  └── Events: MutinyEmitters ✅ (non-blocking)
  ↓
External Systems: All reactive
```

### Why This Works

1. **Hibernate ORM (Blocking)**:
   - Reliable, well-tested, easy to debug
   - No reactive Hibernate complexity
   - Fast for typical database operations
   - Proper transaction boundaries

2. **S3 (Reactive)**:
   - Better for I/O-bound operations
   - Higher throughput for large files
   - Natural async composition

3. **Events (Reactive)**:
   - Fire-and-forget with MutinyEmitters
   - Don't block main operations
   - Perfect for eventual consistency

### Lessons Learned: Hibernate Reactive

**❌ The Problem**: Hibernate Reactive + gRPC streaming = 2-month debugging nightmare
- Complex transaction boundaries across reactive streams
- Incomprehensible stack traces
- Thread pool conflicts between Vert.x and gRPC
- Context propagation issues

**✅ The Solution**: Use blocking Hibernate where it makes sense
- Simple, reliable, debuggable
- Proper `@Transactional` boundaries
- Easy to reason about

## Implementation Details

### Entity Layer

**Pattern**: PanacheEntityBase + GenerationType.IDENTITY
```java
@Entity
@Table(name = "drives")
public class Drive extends PanacheEntityBase {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    public Long id;
    
    // ... fields
}
```

**Key Fix**: SQL NULL handling for hierarchy queries
```java
public static List<Node> findByDriveIdAndParentId(Long driveId, Long parentId) {
    if (parentId == null) {
        return find("driveId = ?1 and parentId IS NULL", driveId).list();
    } else {
        return find("driveId = ?1 and parentId = ?2", driveId, parentId).list();
    }
}
```

### Service Layer

**Pattern**: Structured exceptions with error codes
```java
@ApplicationScoped
public class DocumentService {
    
    @Transactional
    public DocumentResult createDocument(...) {
        try {
            // Database operations (blocking, critical path)
            // S3 operations (reactive, better performance)
            // Event emission (reactive, fire-and-forget)
        } catch (RepoServiceException e) {
            // Re-throw structured exceptions
            throw e;
        } catch (Exception e) {
            // Wrap unexpected exceptions
            throw new DatabaseOperationException("createDocument", "Node", e);
        }
    }
}
```

**Exception Hierarchy:**
```
RepoServiceException (base)
├── DriveNotFoundException
├── DocumentNotFoundException  
├── S3StorageException
├── DatabaseOperationException
├── InvalidRequestException
├── UploadException
└── EventEmissionException
```

### Event System

**Pattern**: MutinyEmitters with Cancellable control
```java
@ApplicationScoped
public class ReactiveEventPublisherImpl implements EventPublisher {
    
    @Inject
    @Channel("repository-events")
    MutinyEmitter<DocumentEvent> documentEventEmitter;
    
    public Cancellable publishDocumentCreated(...) {
        // Build event
        Message<DocumentEvent> message = Message.of(event)
            .addMetadata(OutgoingKafkaRecordMetadata.<UUID>builder()
                .withKey(messageKey)
                .withTopic(topicName) // Dynamic topic support
                .build());
        
        return documentEventEmitter.sendMessageAndForget(message);
    }
}
```

**Critical Apicurio Registry Consumer Config:**
```properties
apicurio.registry.url=http://localhost:8082/apis/registry/v3
apicurio.registry.serde.find-latest=true
apicurio.registry.deserializer.value.return-class=io.pipeline.repository.filesystem.EventType
```

### Multi-Tenant Architecture

**Pattern**: Drive-based bucket resolution (no defaults)
```java
private String getBucketName(String driveName) {
    Drive drive = Drive.findByName(driveName);
    if (drive == null) {
        throw new DriveNotFoundException(driveName);
    }
    return drive.bucketName;
}
```

**Benefits:**
- ✅ Multi-tenant by design
- ✅ No default bucket hacks
- ✅ Customer isolation
- ✅ Scalable architecture

## Test Infrastructure

### Parallel-Safe Testing

**Pattern**: TestInfo-based resource isolation
```java
@BeforeEach
void setUp(TestInfo testInfo) {
    // Unique bucket per test
    testBucket = bucketManager.setupBucket(testInfo);
    
    // Unique topic prefix per test  
    testTopicPrefix = testInfo.getTestClass().map(Class::getSimpleName).orElse("UnknownTest") + 
                     "-" + testInfo.getTestMethod().map(m -> m.getName()).orElse("unknownMethod") + 
                     "-" + System.currentTimeMillis();
}

@AfterEach
void tearDown(TestInfo testInfo) {
    bucketManager.cleanupBucket(testBucket); // Clean specific bucket
    eventListener.clearTopicsWithPrefix(testTopicPrefix); // Clean specific topics
}
```

### Test Helpers

**Pattern**: Injectable helpers eliminate scaffolding
```java
@ApplicationScoped
public class EntityTestHelper {
    public Drive createTestDrive(String namePrefix, String bucketName) {
        // Creates drive with proper setup
    }
    
    public Node createTestNode(Drive drive, String namePrefix, String nodeTypeCode) {
        // Creates node with proper relationships
    }
}
```

**Benefits:**
- ✅ 15+ lines of setup → 1-2 lines
- ✅ Consistent patterns across tests
- ✅ Easy to maintain and update

### Event Testing

**Pattern**: EventTestListener with Awaitility
```java
@ApplicationScoped
public class EventTestListener {
    // Separate collections for each event type
    private final Map<String, List<DocumentEvent>> documentEvents = new ConcurrentHashMap<>();
    private final Map<String, List<SearchIndexEvent>> searchIndexEvents = new ConcurrentHashMap<>();
    private final Map<String, List<RequestCountEvent>> requestCountEvents = new ConcurrentHashMap<>();
    
    public List<DocumentEvent> waitForDocumentEvents(String topicName, int expectedCount, Duration timeout) {
        // Awaitility-based waiting with proper error handling
    }
}
```

## Current Status (January 14, 2025)

### ✅ What's COMPLETELY FIXED
- **12MB Kafka Problem** - Events now ~75 bytes (metadata only)
- **Real S3 Storage** - Multipart upload working with 5MB threshold
- **Connector Organization** - `connectors/{connector_id}/{document_id}.pb`
- **Client IDs** - Deduplication and update support
- **S3 Metadata** - Human-readable tags (filename, proto-type, etc.)
- **Path Support** - Proto updated for filesystem paths
- **Content Hashing** - SHA-256 for deduplication
- **Version Tracking** - S3 version IDs captured

### 📋 Architecture Next Steps

#### Immediate (This Week)
1. **Standalone Connector Pattern**
   - Filesystem connector as separate microservice
   - gRPC/Consul for service discovery
   - Reusable for Confluence, WordPress, etc.

2. **Batch via Existing Streaming**
   - Use current `UploadChunks` RPC
   - Multiple files in single stream
   - Clear file boundaries with `isLast=true`

3. **Download/Streaming API**
   - Efficient S3 retrieval
   - Byte-range support
   - Stream large files

#### Future
- Resume interrupted uploads (complex, lower priority)
- Comprehensive unit tests (scripts → tests)
- Metrics and monitoring
- Performance optimization  
🔧 **Database Progress** - Use entities instead of in-memory maps  

## Key Takeaways

1. **Hybrid > Full Reactive** - Use reactive where it adds value, blocking where it's simpler
2. **Test Infrastructure is Critical** - Parallel-safe isolation prevents test interference  
3. **Structured Exceptions** - Error codes and context make debugging possible
4. **Multi-tenancy from Day 1** - No default bucket hacks, proper drive isolation
5. **Event System Complexity** - Apicurio Registry configuration is critical for proper deserialization

## Repository Service Status

**Functional and ready for integration** - All core subsystems working, just need to connect them together for complete end-to-end flows.



