# Repository Service Architecture - Section 4: Data Model - Node Entity (Document)

## Node Entity (Document)

**Database Entity Design:**
```java
@Entity
@Table(name = "documents")
public class Node extends PanacheEntity {
    @Column(name = "document_id", unique = true, nullable = false)
    public String documentId;              // UUID for external API
    
    @Column(name = "drive_id", nullable = false)
    public Long driveId;                   // Foreign key to Drive
    
    @Column(name = "name", nullable = false)
    public String name;                     // Document name
    
    @Column(name = "node_type_id", nullable = false)
    public Long nodeTypeId;                 // Foreign key to node_type lookup table
    
    @Column(name = "parent_id")
    public Long parentId;                   // Self-reference for hierarchy
    
    @Column(name = "path", nullable = false)
    public String path;                    // Computed path for efficient queries
    
    @Column(name = "content_type")
    public String contentType;             // MIME type
    
    @Column(name = "size_bytes")
    public Long size;                      // Size in bytes
    
    @Column(name = "s3_key")
    public String s3Key;                   // S3 object key within drive's bucket
    
    @Column(name = "created_at")
    public OffsetDateTime createdAt;
    
    @Column(name = "updated_at")
    public OffsetDateTime updatedAt;
    
    @Column(name = "metadata")
    public String metadata;                 // JSON metadata for unstructured data
    
    @Transient
    public Any payload;                    // Actual payload data (NOT persisted)
}
```

**Protobuf Definition:**
```protobuf
message Node {
  enum NodeType {
    NODE_TYPE_UNSPECIFIED = 0;
    FOLDER = 1;
    FILE = 2;
  }

  int64 id = 1;                    // Database primary key
  string document_id = 2;          // UUID for external API
  int64 drive_id = 3;             // Foreign key to Drive
  string name = 4;                 // Document name
  int64 node_type_id = 5;          // Foreign key to node_type lookup table
  int64 parent_id = 6;             // Self-reference for hierarchy
  string path = 7;                 // Computed path for efficient queries
  string content_type = 8;         // MIME type
  int64 size_bytes = 9;           // Size in bytes
  string s3_key = 10;              // S3 object key within drive's bucket
  google.protobuf.Timestamp created_at = 11;
  google.protobuf.Timestamp updated_at = 12;
  string metadata = 13;            // JSON metadata for unstructured data
  
  // Transient fields (not persisted to database)
  google.protobuf.Any payload = 14; // Actual payload data (NOT persisted)
  NodeType type = 15;              // S3-level classification (FOLDER or FILE)
  string icon_svg = 16;            // SVG icon for visual representation
  string service_type = 17;        // Service interface type (e.g., "PipeStepProcessor", "Parser")
  string payload_type = 18;        // Actual payload type (e.g., "ModuleProcessRequest", "ModuleProcessResponse")
}
```
```

## Supporting Tables

### Node Type Lookup Table
```java
@Entity
@Table(name = "node_type")
public class NodeType extends PanacheEntity {
    @Column(unique = true, nullable = false)
    public String code;                    // Type code (PIPEDOC, PIPESTREAM, etc.)
    
    @Column(nullable = false)
    public String description;             // Human-readable description
    
    @Column(name = "protobuf_type")
    public Boolean protobufType = false;   // Whether this is a protobuf type
}
```

### Upload Status Lookup Table
```java
@Entity
@Table(name = "upload_status")
public class UploadStatus extends PanacheEntity {
    @Column(unique = true, nullable = false)
    public String code;                    // Status code (PENDING, UPLOADING, COMPLETED, FAILED)
    
    @Column(nullable = false)
    public String description;             // Human-readable description
    
    @Column(name = "is_final")
    public Boolean isFinal = false;        // Whether this is a final status
}
```

### Upload Progress Table (Separate)
```java
@Entity
@Table(name = "upload_progress")
public class UploadProgress extends PanacheEntity {
    @Column(name = "document_id", nullable = false)
    public String documentId;              // Foreign key to documents
    
    @Column(name = "upload_id", unique = true, nullable = false)
    public String uploadId;                // Unique upload identifier
    
    @Column(name = "status_id", nullable = false)
    public Long statusId;                  // Foreign key to upload_status lookup table
    
    @Column(name = "total_chunks")
    public Integer totalChunks;            // For multi-part uploads
    
    @Column(name = "completed_chunks")
    public Integer completedChunks;        // Progress tracking
    
    @Column(name = "error_message")
    public String errorMessage;            // Error details if failed
    
    @Column(name = "started_at")
    public OffsetDateTime startedAt;
    
    @Column(name = "completed_at")
    public OffsetDateTime completedAt;
}
```

### Completed Uploads Table (Historical Record)
```java
@Entity
@Table(name = "completed_uploads")
public class CompletedUpload extends PanacheEntity {
    @Column(name = "document_id", nullable = false)
    public String documentId;              // Foreign key to documents
    
    @Column(name = "upload_id", nullable = false)
    public String uploadId;                // Original upload identifier
    
    @Column(name = "status_id", nullable = false)
    public Long statusId;                  // Final status (COMPLETED or FAILED)
    
    @Column(name = "total_chunks")
    public Integer totalChunks;            // Final chunk count
    
    @Column(name = "error_message")
    public String errorMessage;            // Error details if failed
    
    @Column(name = "started_at")
    public OffsetDateTime startedAt;
    
    @Column(name = "completed_at")
    public OffsetDateTime completedAt;
    
    @Column(name = "archived_at")
    public OffsetDateTime archivedAt;      // When moved to this table
}
```

## Database Schema

```sql
-- Node type lookup table
CREATE TABLE node_type (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,
    description VARCHAR(255) NOT NULL,
    protobuf_type BOOLEAN DEFAULT false,
    INDEX idx_node_type_code (code)
);

-- Upload status lookup table
CREATE TABLE upload_status (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,
    description VARCHAR(255) NOT NULL,
    is_final BOOLEAN DEFAULT false,
    INDEX idx_upload_status_code (code)
);

-- Main documents table (clean, completed uploads only)
CREATE TABLE documents (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    document_id VARCHAR(255) UNIQUE NOT NULL,
    drive_id BIGINT NOT NULL,
    name VARCHAR(500) NOT NULL,
    node_type_id BIGINT NOT NULL,
    parent_id BIGINT NULL,
    path VARCHAR(2000) NOT NULL,
    content_type VARCHAR(255),
    size_bytes BIGINT,
    s3_key VARCHAR(1000),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    metadata JSON,
    FOREIGN KEY (drive_id) REFERENCES drives(id) ON DELETE CASCADE,
    FOREIGN KEY (node_type_id) REFERENCES node_type(id),
    FOREIGN KEY (parent_id) REFERENCES documents(id) ON DELETE CASCADE,
    INDEX idx_documents_drive_name (drive_id, name),
    INDEX idx_documents_document_id (document_id),
    INDEX idx_documents_path (path(255))
);

-- Upload progress table (active uploads)
CREATE TABLE upload_progress (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    document_id VARCHAR(255) NOT NULL,
    upload_id VARCHAR(255) UNIQUE NOT NULL,
    status_id BIGINT NOT NULL,
    total_chunks INT,
    completed_chunks INT,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
    INDEX idx_upload_document (document_id),
    INDEX idx_upload_status (status_id)
);

-- Completed uploads table (historical record)
CREATE TABLE completed_uploads (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    document_id VARCHAR(255) NOT NULL,
    upload_id VARCHAR(255) NOT NULL,
    status_id BIGINT NOT NULL,
    total_chunks INT,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
    INDEX idx_completed_document (document_id),
    INDEX idx_completed_status (status_id)
);
```

## Initial Data

```sql
-- Initial node types
INSERT INTO node_type (code, description, protobuf_type) VALUES 
('PIPEDOC', 'Pipeline Document (PipeDoc protobuf)', true),
('PIPESTREAM', 'Pipeline Stream (PipeStream protobuf)', true),
('GRAPH_NODE', 'Graph network node (GraphNode protobuf)', true),
('LLM_MODEL', 'LLM Model for embeddings', false),
('FILE', 'Generic file', false);

-- Initial upload statuses
INSERT INTO upload_status (code, description, is_final) VALUES 
('PENDING', 'Upload pending', false),
('UPLOADING', 'Upload in progress', false),
('COMPLETED', 'Upload completed successfully', true),
('FAILED', 'Upload failed', true);
```

## Key Benefits

1. **All Nodes Have Payloads**: Since everything is in S3, all nodes have payloads
2. **Simple Start**: Focus on PIPEDOC and PIPESTREAM initially
3. **Historical Record**: Completed uploads preserved for audit trail
4. **Extensible**: Easy to add new node types and statuses
5. **Clean Separation**: Active uploads vs completed uploads