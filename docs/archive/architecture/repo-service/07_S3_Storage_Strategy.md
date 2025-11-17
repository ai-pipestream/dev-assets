# Repository Service Architecture - Section 7: S3 Storage Strategy

## Simple S3 Storage

**Storage Structure:**
```
s3://{bucket-name}/
├── {document-id}.pb              # Protobuf file (PipeDoc, PipeStream, etc.)
├── {document-id}.bin             # Encrypted file
├── {document-id}.{extension}    # Generic file (PDF, image, etc.)
└── {document-id}/                # Folder for multi-file documents (rare)
    └── payload.pb
```

**That's it. Simple.**

## S3 Integration

**File Naming:**
- **Protobuf files**: `{document-id}.pb`
- **Encrypted files**: `{document-id}.bin` 
- **Generic files**: `{document-id}.{extension}` (PDF, image, etc.)

**S3 Metadata:**
- **Content-Type**: MIME type
- **Content-Length**: File size
- **ETag**: S3 ETag for integrity
- **Last-Modified**: S3 timestamp
- **Custom Metadata**: Any additional metadata as S3 object metadata

**Database Tracking:**
- **S3 Key**: Simple key like `{document-id}.pb`
- **S3 ETag**: For integrity checking
- **S3 Size**: File size in bytes
- **S3 Last Modified**: S3 timestamp

## Protobuf Integration Strategy

**Protobuf Storage Flow:**
1. **gRPC Request** arrives with `Node` containing `Any payload`
2. **Extract payload** from `Node.payload` field
3. **Store payload** in S3 using `payload.toByteArray()`
4. **Store Node metadata** in database (without payload field)
5. **Emit Kafka events** for indexing and analytics

**Protobuf Serialization:**
```java
// Store protobuf payload in S3
public S3ObjectMetadata storePayload(String bucketName, String documentId, Any payload) {
    byte[] protobufBytes = payload.toByteArray();
    return storeProtobuf(bucketName, documentId, protobufBytes, "application/x-protobuf");
}

// Retrieve protobuf payload from S3
public Any retrievePayload(String bucketName, String documentId) {
    byte[] protobufBytes = retrieveProtobuf(bucketName, documentId);
    return Any.parseFrom(protobufBytes);
}
```

**Type Resolution:**
- **Primary**: Use `Node.payload_type` field for in-memory type lookup
- **Fallback**: Use reflection if type not found in lookup
- **No Apicurio**: Avoid Apicurio dependency for basic operations

**S3 Key Structure:**
- **Protobuf files**: `{document-id}.pb`
- **Content-Type**: `application/x-protobuf`
- **S3 Metadata**: Include `payload_type` for type resolution

## Key Benefits

1. **Simple**: One file per document, that's it
2. **Fast**: Direct S3 key lookup
3. **Clean**: No complex folder structures
4. **Flexible**: Works for any file type
5. **Efficient**: No unnecessary nesting
6. **Type-Safe**: Proper protobuf type resolution
7. **Separation**: Metadata in DB, payload in S3