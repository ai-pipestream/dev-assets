# Streaming File Upload Architecture

## Overview

A streaming file upload system that processes files in chunks without buffering, stores raw data in S3 (optionally encrypted), and maintains metadata in the database. Designed to handle both known-size files and unknown-size live streams.

## Core Design Principles

1. **No Buffering** - Process chunks as they arrive, never accumulate in memory
2. **Raw Data Storage** - Store actual file content in S3, not protobufs
3. **Metadata Separation** - Store searchable metadata in database
4. **Encryption Ready** - S3 data can be encrypted, DB metadata remains clear
5. **Unknown Size Support** - Handle live streams where final size is unknown

## Streaming Protocol

### Chunk Structure

```proto
message StreamingChunk {
  oneof chunk_type {
    Blob header = 1;        // First chunk: Blob with storage_ref
    bytes raw_data = 2;     // Middle chunks: Raw file content
    BlobMetadata footer = 3; // Last chunk: Final metadata
  }
}
```

### Header Chunk (First)

```proto
message Blob {
  string blob_id = 1;                    // Hash-based filename
  string drive_id = 2;                   // S3 bucket name
  FileStorageReference storage_ref = 4;  // Points to S3 location
  
  // Optional metadata (size unknown upfront)
  optional string mime_type = 5;
  optional string filename = 6;
  optional int64 size_bytes = 8;         // Optional for unknown-size streams
  optional string checksum = 9;
  ChecksumType checksum_type = 10;
  optional google.protobuf.Struct metadata = 11;
}
```

### Raw Data Chunks (Middle)

- Pure file content as `bytes`
- Streamed directly to S3 via multipart upload
- Can be encrypted in S3
- No protobuf overhead

### Footer Chunk (Last)

```proto
message BlobMetadata {
  int64 final_size = 1;           // Actual final size
  string checksum = 2;            // SHA256 of complete file
  ChecksumType checksum_type = 3;
  string s3_key = 4;              // Final S3 object key
  string s3_etag = 5;             // S3 ETag for verification
  google.protobuf.Timestamp completed_at = 6;
  map<string, string> final_metadata = 7;
}
```

## Data Flow

### 1. Client Side
```
File Stream → Chunk Generator → gRPC Stream
```

- Client reads file in chunks
- First chunk: Header with metadata
- Middle chunks: Raw file data
- Last chunk: Footer with final metadata

### 2. Connector Intake Service
```
gRPC Stream → Chunk Processor → Single Stream to Repo Service
```

- Receives chunks sequentially
- Validates chunk order
- Calculates incremental SHA256
- Forwards to repo-service via single stream

### 3. Repo Service
```
Stream → S3 Multipart Upload → Database Reference
```

- Initiates S3 multipart upload
- Streams raw data directly to S3
- Creates database reference with S3 metadata
- Returns S3 key and metadata

## S3 Storage Strategy

### File Naming
- **Hash-based filenames**: `{blob_id}` (no extensions)
- **Path structure**: `connectors/{connector_id}/{blob_id}`
- **No .pb extension** - these are raw files, not protobufs

### Encryption
- Raw data in S3 can be encrypted
- Database metadata remains clear for search
- Only decrypted in memory when needed
- Admin sees encrypted gibberish in S3

### Multipart Upload
- Large files (>5MB) use S3 multipart upload
- Small files use single PUT
- Chunks streamed directly to S3 parts
- No intermediate buffering

## Database Schema

### Blob Reference
```sql
CREATE TABLE blobs (
  blob_id VARCHAR(255) PRIMARY KEY,
  drive_id VARCHAR(255) NOT NULL,
  s3_key VARCHAR(255) NOT NULL,
  s3_etag VARCHAR(255),
  mime_type VARCHAR(255),
  filename VARCHAR(255),
  size_bytes BIGINT,
  checksum VARCHAR(255),
  checksum_type VARCHAR(50),
  metadata JSON,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

### Integration with BlobBag
```proto
message BlobBag {
  oneof blobData {
    Blob blob = 1;        // Single file
    Blobs blobs = 2;      // Multiple files
  }
}
```

Each uploaded file becomes a `Blob` with `storage_ref` pointing to S3.

## Use Cases

### 1. Known Size Files
- Upload large files (videos, documents)
- Header contains expected size
- Footer confirms actual size
- Standard file upload workflow

### 2. Unknown Size Streams
- Live camera feeds
- Sensor data streams
- Real-time APIs
- Network streams that pause/resume
- Header has no size, footer provides final size

### 3. Batch Processing
- Multiple files in `BlobBag`
- Each file streamed independently
- All references stored together
- Pipeline engine processes entire bag

## Security Model

### Data at Rest
- **S3**: Encrypted raw file data
- **Database**: Clear metadata for search
- **Memory**: Decrypted only when needed

### Data in Transit
- gRPC with TLS
- Chunks encrypted in flight
- No plaintext file data in logs

### Admin Access
- Admins see encrypted data in S3
- Metadata searchable in database
- System decrypts on demand

## Benefits

1. **True Streaming** - No memory buffering
2. **Encryption Ready** - S3 data encrypted, DB clear
3. **Live Data Friendly** - Unknown size streams
4. **Resumable** - Track progress without final size
5. **Admin Safe** - S3 contains encrypted gibberish
6. **Engine Compatible** - Works with existing `BlobBag` structure
7. **Scalable** - Handles any file size
8. **Efficient** - Raw data in S3, metadata in DB

## Implementation Status

- ✅ Basic streaming working
- ✅ S3 multipart upload working
- ✅ No buffering in connector-intake-service
- ✅ Single stream to repo-service
- 🔄 Need to implement header/raw/footer protocol
- 🔄 Need to remove .pb extension
- 🔄 Need to add encryption support
- 🔄 Need to handle unknown size streams

## Next Steps

1. Implement header/raw/footer chunk protocol
2. Remove .pb extension from S3 keys
3. Add encryption support for S3 data
4. Test with unknown size streams
5. Integrate with pipeline engine via BlobBag