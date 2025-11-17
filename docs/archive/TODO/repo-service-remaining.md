# Repository Service - Remaining Work

## ✅ COMPLETED (January 14, 2025)

### Critical Fixes - DONE
- ✅ **Event Schema Fixed**: Events are now ~75 bytes (metadata only), payloads in S3
- ✅ **S3 Persistence**: Real multipart upload working with 5MB threshold
- ✅ **Content Hashing**: SHA-256 implemented for deduplication
- ✅ **S3 Versioning**: Version IDs captured from S3 responses
- ✅ **Structured S3 Keys**: `connectors/{connector_id}/{document_id}.pb` implemented
- ✅ **Client-Provided IDs**: Support for deduplication and updates
- ✅ **Path Support**: Added to proto for filesystem organization
- ✅ **Metadata Tags**: Human-readable S3 metadata (filename, proto-type, etc.)

### Architecture - DONE
- ✅ **Connector Pattern Designed**: Clean separation of concerns
- ✅ **Connector-Intake Service**: Proto and architecture defined
- ✅ **Streaming Support**: Already batch-capable via existing RPCs

## 📋 REMAINING WORK

### Repository Service Enhancements

#### 1. CRUD Operations (Priority: HIGH) ✅ COMPLETED
```
[✅] GetNode - Retrieve document by ID (with include_payload option)
[✅] UpdateNode - Update metadata AND content (creates S3 versions)
[✅] DeleteNode - Hard delete with S3 cleanup (recursive for folders)
[✅] GetChildren - List child nodes with pagination
[✅] SearchNodes - Metadata-based search with filters
```

#### 2. Download/Streaming API (Priority: HIGH)
```
[ ] DownloadDocument - Direct download from S3
[ ] StreamDocument - Streaming for large files
[ ] GetDocumentUrl - Pre-signed S3 URLs
[ ] Byte-range support - Partial downloads
```

#### 3. Database Integration (Priority: MEDIUM)
```
[ ] Replace in-memory maps with database entities
[ ] Implement proper transaction boundaries
[ ] Add indexes for search performance
[ ] Migration scripts for production
```

#### 4. Search & Query (Priority: MEDIUM)
```
[ ] Metadata search API
[ ] Full-text search integration
[ ] Query by path/hierarchy
[ ] Orphan detection queries
```

### Connector-Intake Service (NEW SERVICE)

#### 1. Core Implementation
```
[ ] Create Quarkus project
[ ] Implement gRPC service from proto
[ ] Authentication/session management
[ ] Account lookup and enrichment
```

#### 2. Integration
```
[ ] Connect to repo-service
[ ] Rate limiting implementation
[ ] Crawl session tracking
[ ] Orphan detection logic
```

### Testing & Quality

#### 1. Unit Tests
```
[ ] Convert test scripts to unit tests
[ ] Add CRUD operation tests
[ ] Streaming/download tests
[ ] Search functionality tests
```

#### 2. Integration Tests
```
[ ] End-to-end connector flow
[ ] Multi-file batch uploads
[ ] Failure recovery scenarios
[ ] Performance tests with 260+ files
```

### Monitoring & Operations

#### 1. Metrics (Priority: LOW)
```
[ ] Quarkus Micrometer integration
[ ] Upload/download metrics
[ ] S3 operation metrics
[ ] Error rate tracking
```

#### 2. Health Checks
```
[ ] S3 connectivity check
[ ] Database health check
[ ] Memory/thread monitoring
```

## Implementation Order

### Week 1 (This Week)
1. **CRUD Operations** - Essential for any real usage
2. **Download API** - Critical for retrieving documents
3. **Database Integration** - Move from in-memory to persistent

### Week 2
1. **Connector-Intake Service** - Standalone implementation
2. **FileSystem Connector** - First connector implementation
3. **Integration Testing** - End-to-end validation

### Week 3
1. **Search APIs** - Metadata and full-text search
2. **Monitoring** - Metrics and health checks
3. **Production Preparation** - Performance tuning

## Notes

### What NOT to Do (Already Solved)
- ❌ Event schema changes - DONE
- ❌ S3 multipart upload - DONE
- ❌ Content hashing - DONE
- ❌ Client IDs - DONE
- ❌ Connector architecture - DESIGNED

### Key Decisions Made
1. **Batch via Streaming**: Use existing `UploadChunks` RPC
2. **Connectors are Clients**: Simple streaming clients, no complex logic
3. **Central Auth**: All in connector-intake service
4. **S3 is Truth**: Database points to S3, not vice versa

### Success Metrics
- Documents upload in <100ms (small files)
- Streaming works for 100MB+ files
- 260 file batch completes successfully
- Search returns results in <500ms
- Zero data loss on failures