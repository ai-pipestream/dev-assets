# Repository Service Architecture - Section 5: Repository Pattern

## Repository Use Cases

The Repository Service serves as the central DAM (Digital Asset Management) system for the entire pipeline:

1. **Pipeline Entry**: When a document enters the pipeline through a connector, it will be saved in the repository service for downstream processing
2. **Pipeline Playback**: When a document is in the middle of a pipestream, it can be offloaded to the repository service to allow for playback and rewinds
3. **Pipeline Completion**: When a document is completed through a pipeline and before going to a sink, it's a good practice to also offload this to the repository for fast re-processing
4. **LLM Model Storage**: The embedder service requires LLM Models, which will utilize this service for that storage directly into S3
5. **Graph Network Versioning**: The graph network of nodes will be recorded and versioned with this service
6. **Testing & Visualization**: Any use of assets for functional tests. The modules will have a front end that can use this service to test data live and visualize it

## Repository Design

**Core Repositories:**

```java
@ApplicationScoped
public class DriveRepository implements PanacheRepository<Drive> {
    
    // Basic CRUD operations
    public Drive findByBucketName(String bucketName) {
        return find("bucketName", bucketName).firstResult();
    }
    
    public List<Drive> findByCustomerId(String customerId) {
        return list("customerId", customerId);
    }
    
    public Drive findByName(String name) {
        return find("name", name).firstResult();
    }
    
    // Pipeline-specific queries
    public List<Drive> findActiveDrives() {
        return list("status.code", "ACTIVE");
    }
}
```

```java
@ApplicationScoped
public class NodeRepository implements PanacheRepository<Node> {
    
    // Basic CRUD operations
    public Node findByDocumentId(String documentId) {
        return find("documentId", documentId).firstResult();
    }
    
    public List<Node> findByDriveId(Long driveId) {
        return list("driveId", driveId);
    }
    
    public List<Node> findByPath(String path) {
        return list("path", path);
    }
    
    // Protobuf-specific queries
    public List<Node> findByNodeType(String nodeTypeCode) {
        return list("nodeType.code", nodeTypeCode);
    }
    
    public List<Node> findPipeDocs() {
        return list("nodeType.code", "PIPEDOC");
    }
    
    public List<Node> findPipeStreams() {
        return list("nodeType.code", "PIPESTREAM");
    }
    
    public List<Node> findGraphNodes() {
        return list("nodeType.code", "GRAPH_NODE");
    }
    
    // Generic metadata queries (for flexible use cases)
    public List<Node> findByMetadataTag(String tagKey, String tagValue) {
        return list("metadata", tagKey, tagValue);
    }
    
    public List<Node> findByMetadataTag(String tagKey) {
        return list("metadata", tagKey);
    }
    
    // Performance queries
    public List<Node> findBySizeRange(Long minSize, Long maxSize) {
        return list("sizeBytes >= ?1 and sizeBytes <= ?2", minSize, maxSize);
    }
    
    public List<Node> findByCreationDateRange(OffsetDateTime startDate, OffsetDateTime endDate) {
        return list("createdAt >= ?1 and createdAt <= ?2", startDate, endDate);
    }
    
    // Pagination support
    public List<Node> findWithPagination(Long driveId, int page, int size) {
        return find("driveId", driveId).page(page, size).list();
    }
    
    // Update operations
    @Transactional
    public Node updateNode(String documentId, String name, String metadata) {
        Node node = findByDocumentId(documentId);
        if (node != null) {
            node.name = name;
            node.metadata = metadata;
            node.updatedAt = OffsetDateTime.now();
            persist(node);
        }
        return node;
    }
    
    // Delete operations
    @Transactional
    public boolean deleteNode(String documentId) {
        Node node = findByDocumentId(documentId);
        if (node != null) {
            delete(node);
            return true;
        }
        return false;
    }
}
```

**Supporting Repositories:**

```java
@ApplicationScoped
public class NodeTypeRepository implements PanacheRepository<NodeType> {
    
    public NodeType findByCode(String code) {
        return find("code", code).firstResult();
    }
    
    public List<NodeType> findProtobufTypes() {
        return list("protobufType", true);
    }
    
    // Easy way to add new node types
    public NodeType createNodeType(String code, String description, Boolean protobufType) {
        NodeType nodeType = new NodeType();
        nodeType.code = code;
        nodeType.description = description;
        nodeType.protobufType = protobufType;
        persist(nodeType);
        return nodeType;
    }
}

@ApplicationScoped
public class UploadStatusRepository implements PanacheRepository<UploadStatus> {
    
    public UploadStatus findByCode(String code) {
        return find("code", code).firstResult();
    }
    
    public List<UploadStatus> findFinalStatuses() {
        return list("isFinal", true);
    }
}

@ApplicationScoped
public class UploadProgressRepository implements PanacheRepository<UploadProgress> {
    
    public UploadProgress findByUploadId(String uploadId) {
        return find("uploadId", uploadId).firstResult();
    }
    
    public List<UploadProgress> findByDocumentId(String documentId) {
        return list("documentId", documentId);
    }
    
    public List<UploadProgress> findActiveUploads() {
        return list("status.isFinal", false);
    }
}

@ApplicationScoped
public class CompletedUploadRepository implements PanacheRepository<CompletedUpload> {
    
    public List<CompletedUpload> findByDocumentId(String documentId) {
        return list("documentId", documentId);
    }
    
    public List<CompletedUpload> findRecentUploads(int days) {
        OffsetDateTime cutoff = OffsetDateTime.now().minusDays(days);
        return list("archivedAt >= ?1", cutoff);
    }
}
```

## Adding New Node Types

**Initial Node Types:**
```sql
INSERT INTO node_type (code, description, protobuf_type) VALUES 
('PIPEDOC', 'Pipeline Document (PipeDoc protobuf)', true),
('PIPESTREAM', 'Pipeline Stream (PipeStream protobuf)', true),
('GRAPH_NODE', 'Graph network node (GraphNode protobuf)', true),
('LLM_MODEL', 'LLM Model for embeddings', false),
('FILE', 'Generic file', false);
```

**Adding New Node Types:**
```java
// Example: Adding new protobuf type
NodeType newProtobufType = nodeTypeRepository.createNodeType(
    "NEW_PROTOBUF_TYPE", 
    "New protobuf type description", 
    true
);

// Example: Adding new file type
NodeType newFileType = nodeTypeRepository.createNodeType(
    "NEW_FILE_TYPE", 
    "New file type description", 
    false
);
```

## Protobuf Storage Strategy

**S3 Storage:**
- **File Extension**: `.pb` for protobuf files
- **Content**: Serialized protobuf bytes
- **Naming**: `{document-id}.pb`

**Database Tracking:**
- **Node Type**: Tracked in `node_type` table
- **S3 Key**: Simple key like `{document-id}.pb`
- **S3 ETag**: For integrity checking
- **S3 Size**: File size in bytes

**Example Storage:**
```
S3: s3://bucket/123e4567-e89b-12d3-a456-426614174000.pb
DB: node_type.code = "PIPEDOC"
     s3_key = "123e4567-e89b-12d3-a456-426614174000.pb"
```

## Metadata Tags for Generic Cases

**JSON Metadata Structure:**
```json
{
  "tags": {
    "pipeline_id": "pipeline-123",
    "module_name": "chunker",
    "test_asset": true,
    "version": "1.0.0"
  },
  "custom_fields": {
    "model_type": "embedding",
    "chunk_size": 512,
    "embedding_dimension": 1536
  }
}
```

**Query Examples:**
```java
// Find all test assets
List<Node> testAssets = nodeRepository.findByMetadataTag("test_asset", "true");

// Find documents for specific pipeline
List<Node> pipelineDocs = nodeRepository.findByMetadataTag("pipeline_id", "pipeline-123");

// Find LLM models by type
List<Node> embeddingModels = nodeRepository.findByMetadataTag("model_type", "embedding");
```

## Key Benefits

1. **Use Case Driven**: Repository methods align with actual pipeline use cases
2. **Performance Optimized**: Indexed queries for common operations
3. **Extensible**: Easy to add new query methods as use cases evolve
4. **Separation of Concerns**: Different repositories for different entity types
5. **Pipeline Integration**: Methods support all pipeline stages (entry, processing, completion)