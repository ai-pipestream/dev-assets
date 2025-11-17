# Frontend Architecture - Connector Intake Service

## CORRECT ARCHITECTURE (DO NOT DEVIATE)

```
Frontend (port 33000) → Web-proxy (port 38106) → gRPC streaming → Connector-intake-service (port 38108) → Repo-service (S3)
```

## Key Principles

1. **Frontend NEVER uses gRPC directly** - only HTTP POST
2. **Web-proxy is the translation layer** - converts HTTP to gRPC internally
3. **Drive-uploader is CLI ONLY** - no Express server, no port 38109
4. **Shared components are OK** - `ConnectorClient`, `DocumentStreamer` can be shared
5. **✅ Non-blocking gRPC** - return receipts immediately, process in background (IMPLEMENTED)
6. **✅ Real-time progress** - streaming updates via Connect-ES (IMPLEMENTED)
7. **✅ Bidirectional streaming** - client streams chunks, server streams receipts (IMPLEMENTED)
8. **✅ gRPC flow control** - automatic backpressure management (IMPLEMENTED)

## DESIGN DECISIONS (FINAL - DO NOT DEVIATE)

### 1. Multi-File Streaming: Separate gRPC Streams Per File
- **Decision**: ✅ **Separate gRPC streams per file**
- **Rationale**: S3 requires ordered parts (1, 2, 3...) - mixed chunks would break this
- **Implementation**: 5 concurrent uploads = 5 separate gRPC streams
- **Flow**: Each file gets its own ordered stream (Header → Chunks → Footer)

### 2. Progress Granularity: Per Chunk Updates
- **Decision**: ✅ **Per chunk progress updates**
- **Rationale**: Real-time feedback, Kafka handles high message volume easily
- **Message Volume**: 10MB chunks = 100 events per 1GB file
- **Implementation**: Emit Kafka event on every chunk completion

### 3. Client Integration: Real-Time Streaming with Connect-ES
- **Decision**: ✅ **Real-time streaming with Connect-ES**
- **Architecture**: Browser → Connect-ES Proxy → Connector-Intake-Service → Repo-Service
- **Progress Updates**: Separate streaming gRPC call for real-time updates
- **Status Queries**: Blocking gRPC call for current state

### 4. Error Handling: Continue on Failure
- **Decision**: ✅ **Continue processing remaining files**
- **Behavior**: One file fails → Continue with other files, report failures
- **Client Retry**: Client can retry failed files independently
- **No Cascading Failures**: Partial success is acceptable

### 5. Timeout Strategy: Chunk-Based Only
- **Decision**: ✅ **Chunk timeout only (30 seconds per chunk)**
- **Rationale**: No bias toward small files, slow connections won't fail large files
- **Implementation**: Each chunk gets 30 seconds, no total upload timeout

## IMPLEMENTATION STATUS

### ✅ Phase 1: Non-Blocking gRPC (COMPLETED)
1. **✅ Bidirectional gRPC streaming** - `UploadChunks` now returns `stream UploadChunkResponse`
2. **✅ Immediate receipts** - each chunk returns receipt with file SHA, job ID, and completion flag
3. **✅ Parallel chunk processing** - using Mutiny `.merge(5)` for concurrent processing
4. **✅ Hash type specification** - added `HashType` enum for explicit algorithm specification
5. **✅ Background S3 processing** - chunks are queued and processed asynchronously

### 🔄 Phase 2: Multi-File Support (IN PROGRESS)
1. **✅ Multiple gRPC streams** - each file gets its own bidirectional stream
2. **🔄 File-level queuing** - single PUT uploads need proper chunk collection (placeholder implemented)
3. **✅ Cross-file progress tracking** - job IDs allow tracking multiple concurrent uploads
4. **✅ File completion detection** - `is_file_complete` flag indicates last chunk

### 🔄 Phase 3: Real-Time Progress (PENDING)
1. **🔄 Kafka progress events** - emit on every chunk completion (infrastructure ready)
2. **✅ Progress streaming gRPC** - existing `StreamUploadProgress` call available
3. **🔄 Database updates** - Kafka consumers update upload status in database
4. **✅ Client polling fallback** - `getUploadStatus()` for status queries

## gRPC BACKPRESSURE MECHANISM

### How gRPC Handles Backpressure Automatically

**gRPC Flow Control** provides built-in backpressure management without additional code:

1. **HTTP/2 Flow Control**: gRPC uses HTTP/2 which has built-in flow control
   - **Window Size**: Each stream has a receive window (default 64KB)
   - **Automatic Backpressure**: When window is full, sender automatically stops
   - **No Blocking**: Receiver doesn't block - just stops accepting new data

2. **Bidirectional Streaming Backpressure**:
   - **Client → Server**: Chunk uploads are automatically throttled when server buffer is full
   - **Server → Client**: Receipt responses are automatically throttled when client buffer is full
   - **Independent Control**: Each direction has its own flow control window

3. **Concurrent Stream Management**:
   - **Multiple Files**: Each file gets its own gRPC stream with independent flow control
   - **No Cross-Stream Blocking**: One slow file doesn't block other files
   - **Automatic Queuing**: gRPC queues chunks when receiver is busy

### Frontend Integration Benefits

- **Zero Configuration**: No manual buffer management needed in web-proxy
- **Automatic Scaling**: Flow control adapts to network conditions
- **Memory Efficient**: Prevents memory overflow from fast senders
- **Network Friendly**: Respects receiver capacity automatically
- **Real-time Responsiveness**: UI gets immediate feedback on chunk receipt

### Performance Characteristics

- **Throughput**: Limited only by network bandwidth and S3 upload speed
- **Latency**: Receipts returned immediately (no S3 waiting)
- **Memory**: Bounded by gRPC flow control windows
- **Concurrency**: Multiple files processed in parallel with independent backpressure

## CRITICAL IMPLEMENTATION RULES

- **NO DEVIATIONS** from this design
- **STOP CODING** if any issues arise - analyze together
- **NO CASCADING FAILURES** - prevent the mess that got us here
- **USE MUTINY REACTIVE** - `.merge()` instead of `.concatenate()`
- **THREAD-SAFE STATE** - synchronize shared state properly

## Current Implementation Status

### ✅ Completed Components

1. **Drive-uploader CLI** - Pure command-line tool with no Express server
   - Uses StreamPool for multiplexed gRPC streaming
   - Supports `--streams` flag for parallel uploads
   - Connector reuse with `--connector-id` and `--api-key` flags
   - Header/footer protocol for all file uploads

2. **Connector-shared library** - Reusable components for streaming
   - `StreamPool`: Manages N long-lived gRPC streams with round-robin distribution
   - `DocumentStreamer`: Streams files using header/data/footer protocol
   - `StreamingProtocol`: Helper functions for chunk creation
   - `ConnectorClient`: Manages connector registration and crawl sessions

3. **Streaming Protocol** - Always uses header/footer (raw_data deprecated)
   - Header chunk with Blob metadata
   - Data chunks with raw file content (10MB default)
   - Footer chunk with actual SHA256, size, and S3 ETag

### 🚧 Remaining Work

1. **Web-proxy implementation** - Needs gRPC streaming endpoints
   - Replace multer with busboy for streaming multipart parsing
   - Use StreamPool for multiplexed file uploads
   - Handle multiple files on single gRPC stream
   - No double buffering, stream directly to gRPC

2. **Frontend integration** - Already correct structure
   - Change `baseUrl` from `http://localhost:38109` to `http://localhost:38106`
   - Frontend HTTP API is already compatible

## IMMEDIATE NEXT STEPS (Phase 1: Non-Blocking gRPC)

### 1. Make gRPC Non-Blocking
- **File**: `applications/repo-service/src/main/java/io/pipeline/repository/services/NodeUploadServiceImpl.java`
- **Change**: Replace `.concatenate()` with `.merge()` in `uploadChunks()` method
- **Result**: Return receipt immediately, process chunks in background

### 2. Background Chunk Processing
- **Implementation**: Use Mutiny reactive streams with `.merge(5)` for 5 concurrent chunks
- **Thread Safety**: Synchronize shared state (UploadProgress, etags list)
- **Order Preservation**: Maintain S3 part order (1, 2, 3...)

### 3. Per-Chunk Kafka Events
- **Implementation**: Emit progress event on every chunk completion
- **Topics**: `upload.progress` for real-time updates
- **Message**: Include nodeId, chunkNumber, bytesUploaded, totalBytes

### 4. Chunk Timeout Handling
- **Implementation**: 30-second timeout per chunk
- **Cleanup**: Abort S3 multipart upload on timeout
- **Error Handling**: Emit failure event to Kafka

### 5. Testing
- **Single File**: Test 103MB file upload (should go from 30s to ~5s)
- **Progress Events**: Verify Kafka events are emitted per chunk
- **Timeout**: Test chunk timeout handling
- **Error Recovery**: Test S3 failure scenarios

## Data Flow

1. **Frontend**: User selects file/folder → HTTP POST to web-proxy
2. **Web-proxy**: Receives HTTP POST → Converts to gRPC streaming → Calls connector-intake-service
3. **Connector-intake-service**: Processes gRPC stream → Stores in S3 → Returns response
4. **Web-proxy**: Receives gRPC response → Converts to HTTP response → Returns to frontend
5. **Frontend**: Displays result to user

## CRITICAL RULES

- **NO gRPC in frontend** - frontend only knows HTTP
- **NO Express server in drive-uploader** - CLI only
- **Web-proxy handles all gRPC complexity** - frontend stays simple
- **Use shared components** - don't duplicate logic

## Files to Modify

- `node/applications/web-proxy/ui/src/pages/FilesystemConnectorPage.vue` - fix baseUrl
- `node/applications/web-proxy/src/index.ts` - implement gRPC streaming in upload endpoints
- `node/applications/drive-uploader/src/server.ts` - DELETE THIS FILE
- `node/applications/drive-uploader/package.json` - remove Express dependencies

## DO NOT FORGET

The frontend is already correct - it just points to the wrong port. The web-proxy needs to implement the gRPC streaming logic, not rewrite the frontend.

## End-to-End Streaming Architecture to S3

### gRPC Streaming Protocol

The connector-intake-service uses a 3-chunk streaming protocol:

1. **Header Chunk**: Contains `Blob` with metadata and S3 storage reference
2. **Raw Data Chunks**: Contains actual file content as `bytes`
3. **Footer Chunk**: Contains `BlobMetadata` with final SHA256, size, and S3 ETag

### Protobuf Messages

```protobuf
message StreamingChunk {
  string document_ref = 1;        // Reference to correlate chunks
  int32 chunk_number = 2;
  bool is_last = 4;
  
  oneof chunk_type {
    io.pipeline.data.v1.Blob header = 3;        // First chunk: Blob with storage_ref
    bytes raw_data = 5;                         // Middle chunks: Raw file content
    BlobMetadata footer = 6;                    // Last chunk: Final metadata
  }
}

message BlobMetadata {
  int64 final_size = 1;           // Actual final size
  string checksum = 2;            // SHA256 of complete file
  io.pipeline.data.v1.ChecksumType checksum_type = 3;
  string s3_key = 4;              // Final S3 object key
  string s3_etag = 5;             // S3 ETag for verification
  google.protobuf.Timestamp completed_at = 6;
  map<string, string> final_metadata = 7;
}
```

### Complete Data Flow

1. **Frontend**: User selects file → HTTP POST with FormData to web-proxy
2. **Web-proxy**: Receives HTTP POST → Creates gRPC client to connector-intake-service
3. **Web-proxy**: Streams file in chunks:
   - **Header**: Sends `Blob` with S3 storage reference and initial metadata
   - **Data**: Streams file content in chunks (no buffering, direct to S3)
   - **Footer**: Sends `BlobMetadata` with final SHA256 and S3 ETag
4. **Connector-intake-service**: Receives gRPC stream → Forwards to repo-service
5. **Repo-service**: Handles S3 multipart upload → Stores raw file data (no .pb extension)
6. **S3**: Stores encrypted file data with metadata
7. **Database**: Stores document reference and metadata in `crawl_documents` table
8. **Response**: Success/failure flows back through the chain

### Key Implementation Details

- **No file buffering**: Files are streamed directly to S3 without loading into memory
- **SHA256 integrity**: Calculated on both client and server for verification
- **S3 encryption**: Raw data is encrypted in S3, metadata stored in database
- **Concurrent uploads**: Multiple files can be uploaded in parallel using workers
- **Error handling**: Failed uploads are tracked and reported back to frontend

### Security Model

- **Frontend**: No S3 credentials, no direct S3 access
- **Web-proxy**: No S3 credentials, only gRPC to connector-intake-service
- **Connector-intake-service**: No S3 credentials, only gRPC to repo-service
- **Repo-service**: Has S3 credentials, handles all S3 operations

### Memory Optimization

- **Client-side**: Files are read in chunks, not loaded entirely into memory
- **Server-side**: gRPC streaming processes chunks immediately, no buffering
- **S3**: Multipart upload handles large files efficiently
- **Database**: Only metadata is stored, not file content

### Error Recovery

- **Network failures**: gRPC streaming can resume from last successful chunk
- **S3 failures**: Repo-service handles S3 retry logic
- **Database failures**: Document tracking is transactional
- **Partial uploads**: Failed files are tracked and can be retried

## Implementation Checklist

- [x] Remove Express server from drive-uploader
- [x] Implement StreamPool for multiplexed gRPC streaming
- [x] Implement header/footer protocol in DocumentStreamer
- [x] Add connector reuse functionality
- [x] Test CLI with single file upload
- [ ] Fix frontend baseUrl to point to web-proxy (38106)
- [ ] Implement gRPC streaming in web-proxy upload endpoints using busboy
- [ ] Add proper error handling and progress reporting
- [ ] Test with large files to verify memory usage
- [ ] Test concurrent uploads with multiple streams
- [ ] Verify S3 storage and database tracking
- [ ] Test error recovery scenarios

## Detailed Implementation Guide

### StreamPool Architecture

The `StreamPool` manages N long-lived gRPC bidirectional streams for multiplexed file uploads:

```typescript
// Create pool with 4 streams for parallel uploads
const streamPool = new StreamPool(connectorId, apiKey, crawlId, 4);
await streamPool.initialize();

// Queue documents on round-robin streams
await streamPool.queueDocument(request1);
await streamPool.queueDocument(request2); // Goes to different stream
```

**Key Features:**
- Round-robin distribution across streams
- Promise-based queuing with async generators
- Proper session authentication per stream
- Graceful shutdown with pending request flush

### DocumentStreamer Protocol

ALL files use header/data/footer protocol (10MB chunks default):

```typescript
// 1. Header chunk (chunkNumber: 0)
const headerChunk = createHeaderChunk(documentRef, {
  filename, path, mimeType, sizeBytes,
  sourceCreated, sourceModified, sourceMetadata
});

// 2. Data chunks (chunkNumber: 1, 2, 3, ...)
for await (const chunk of fileStream) {
  const dataChunk = createDataChunk(documentRef, chunkNumber++, buffer, false);
  await streamPool.queueDocument(dataChunk);
}

// 3. Footer chunk (chunkNumber: N, isLast: true)
const footerChunk = createFooterChunk(documentRef, chunkNumber, finalSize, sha256);
```

**Critical Details:**
- NO raw_data path (deprecated)
- Hash calculated incrementally (cached to prevent "digest already called" error)
- Size determined from actual streamed bytes
- No full file in memory at any point

### Connector Reuse Pattern

Connectors are registered ONCE and reused across uploads:

```bash
# First upload: Creates connector
node dist/index.js upload-file file.txt
# Output: Connector ID: abc-123, API Key: xyz-789

# Subsequent uploads: Reuse connector
node dist/index.js upload-file file2.txt --connector-id abc-123 --api-key xyz-789
```

**Implementation:**
```typescript
if (options.connectorId && options.apiKey) {
  connectorClient.setCredentials(connectorId, apiKey);
} else {
  const credentials = await connectorClient.registerConnector(...);
}
```

### Web-Proxy Streaming (TODO)

Use busboy for streaming multipart parsing (NO multer buffering):

```typescript
import busboy from 'busboy';

app.post('/api/upload/file', async (req, res) => {
  const bb = busboy({ headers: req.headers });
  const streamPool = new StreamPool(connectorId, apiKey, crawlId, 1);

  bb.on('file', async (fieldname, fileStream, filename) => {
    const streamer = new DocumentStreamer(streamPool, connectorId, crawlId);
    const result = await streamer.streamFromReadStream(fileStream, filename);
    res.json(result);
  });

  req.pipe(bb);
});
```

**Key Points:**
- Stream directly from HTTP to gRPC (no buffering)
- Multiple files share same StreamPool
- Progress reporting via WebSocket or SSE
- Error handling per file

### Chunk Size Configuration

Default 10MB chunks balance:
- S3 multipart minimum (5MB)
- Memory usage
- Network efficiency
- gRPC message size limits

```bash
# Override chunk size (in bytes)
export GRPC_CHUNK_SIZE=5242880  # 5MB
```

### Testing Examples

```bash
# Single file upload
node dist/index.js upload-file test.txt

# Large file with existing connector
node dist/index.js upload-file large.zip \
  --connector-id abc-123 \
  --api-key xyz-789 \
  --streams=4

# Directory upload (coming soon)
node dist/index.js upload-folder /path/to/dir \
  --streams=8
```

## Files to Reference

### Completed Implementation
- `node/libraries/connector-shared/src/stream-pool.ts` - StreamPool with async generators
- `node/libraries/connector-shared/src/document-streamer.ts` - Header/footer protocol implementation
- `node/libraries/connector-shared/src/streaming-protocol.ts` - Chunk creation helpers
- `node/libraries/connector-shared/src/connector-client.ts` - Connector registration and sessions
- `node/applications/drive-uploader/src/index.ts` - CLI with --streams flag

### Proto Definitions
- `grpc/grpc-stubs/src/main/proto/module/connectors/connector_intake_service.proto` - gRPC service definition
- `grpc/grpc-stubs/src/main/proto/core/pipeline_core_types.proto` - Blob, BlobMetadata, StreamingChunk

### Backend Processing
- `applications/connector-intake-service/src/main/java/io/pipeline/connector/intake/service/StreamingChunkProcessor.java` - Server-side chunk handling
- `applications/repo-service/` - S3 multipart upload handling