# Repository Service Architecture - Section 1: Overview & Design Philosophy

## Overview

The Repository Service is the central storage and metadata management system for the Pipeline Engine. It implements a **multi-service architecture** built around a core FilesystemService that separates metadata storage (MySQL) from payload storage (S3), enabling efficient processing of large documents while maintaining comprehensive audit trails and search capabilities.

The service architecture consists of:
- **FilesystemService**: Core storage backbone handling all CRUD operations
- **Specialized Services**: Domain-specific services built on top of FilesystemService
- **Search Integration**: OpenSearch integration for advanced search capabilities

## Design Philosophy

### Core Principles

1. **A DAM for assets in the application**: We will use this service to store and manage all assets in the application, including documents, folders, and metadata. Some usages: kafka payloads (typically a PipeDoc or PipeStream), file uploads, LLM Models for embeddings, and other assets.

2. **NO PAYLOAD IN DATABASE**: Document payloads are stored in S3, not in MySQL

3. **Metadata-Driven**: Database stores only metadata, references, and processing state

4. **Protobuf-First**: Pipeline data is stored as protobuf messages in S3 for consistency

5. **Blocking Hibernate**: Uses Hibernate ORM Panache for simplicity and reliability

6. **Document-Centric**: Focuses on document processing rather than filesystem operations

### DAM (Digital Asset Management) Architecture

The Repository Service functions as a comprehensive Digital Asset Management system for the entire application:

```mermaid
flowchart TD
    A[Repository Service<br/>DAM System] --> B[Document Assets]
    A --> C[Pipeline Assets]
    A --> D[Model Assets]
    A --> E[Binary Assets]
    
    B --> F[PipeDoc Messages]
    B --> G[PipeStream Messages]
    B --> H[File Uploads]
    
    C --> I[Processing Results]
    C --> J[Chunking Output]
    C --> K[Embedding Vectors]
    
    D --> L[LLM Models]
    D --> M[Embedding Models]
    D --> N[Model Artifacts]
    
    E --> O[Images]
    E --> P[Videos]
    E --> Q[Audio Files]
```

**Asset Types Managed:**
- **Kafka Payloads**: PipeDoc and PipeStream messages
- **File Uploads**: User-uploaded documents and media
- **LLM Models**: Embedding models and related artifacts
- **Processing Results**: Parser, chunker, and embedder outputs
- **Binary Assets**: Images, videos, audio, and other media files

### Protobuf Storage Strategy

The Repository Service stores various types of protobuf data:
- **Pipeline Documents**: Core PipeDoc messages for document processing
- **LLM Models**: Embedding models and related artifacts
- **Request/Response Data**: gRPC and Kafka message payloads
- **Processing Results**: Parser, chunker, and embedder outputs

**File Naming Convention:**
- **Encrypted**: Binary files with key reference stored in MySQL
- **Unencrypted**: `.pb` files when encryption is disabled
- **Frontend Integration**: SVG definitions for each protobuf type

### Pipeline Integration

The Repository Service is central to the pipeline architecture:

```mermaid
flowchart TD
    A[Pipeline Engine] --> B[Kafka Topics]
    B --> C[Repository Service]
    C --> D[S3 Storage]
    C --> E[MySQL Metadata]
    C --> F[OpenSearch Index]
    
    G[Processing Modules] --> H[gRPC Calls]
    H --> C
    C --> I[Payload Hydration]
    I --> G
```

**Kafka Integration:**
- Kafka messages contain lightweight references to payloads
- Repository Service handles storage and rehydration
- Modules receive fully hydrated data via gRPC

### Service Architecture

```mermaid
graph TB
    subgraph "Repository Service Architecture"
        A[FilesystemService<br/>Core Storage Backbone]
        B[PipeDocRepositoryService<br/>PipeDoc Operations]
        C[GraphRepositoryService<br/>Graph Operations]
        D[ModuleRepositoryService<br/>Module Operations]
        E[ProcessRequestRepositoryService<br/>Test Data Operations]
        F[NodeUploadService<br/>Chunked Uploads]
    end
    
    subgraph "Storage Layer"
        G[MySQL Database<br/>System of Record]
        H[S3 Storage<br/>Binary Data]
        I[OpenSearch<br/>Metadata Search]
    end
    
    A --> G
    A --> H
    A --> I
    
    B --> A
    C --> A
    D --> A
    E --> A
    F --> A
    
    J[Pipeline Engine] --> A
    K[Processing Modules] --> A
    L[Frontend Applications] --> A
    L --> F
```

### Architecture Separation

```mermaid
graph TB
    subgraph "Repository Service Architecture"
        A[MySQL Database<br/>System of Record]
        B[S3 Storage<br/>Binary Data]
        C[OpenSearch<br/>Metadata Search]
    end
    
    A --> D[Drive Metadata<br/>Node References<br/>Processing State]
    B --> E[Protobuf Payloads<br/>LLM Models<br/>Binary Assets]
    C --> F[Search Indices<br/>Vector Embeddings<br/>Metadata Queries]
    
    G[Pipeline Engine] --> A
    G --> B
    H[Processing Modules] --> A
    H --> B
    I[Frontend Applications] --> C
```

**Storage Ownership:**
- **MySQL**: System of record for all metadata and references
- **S3**: Repository Service owns multiple S3 buckets referenced in MySQL
- **OpenSearch**: Metadata search and indexing for the repository service

### Documentation Structure

This architecture documentation is organized into the following sections:

1. **Overview & Design Philosophy** - High-level architecture and design principles
2. **Technology Stack** - Technologies and frameworks used
3. **Data Model - Drive Entity** - Drive entity design and database schema
4. **Data Model - Node Entity** - Node entity design and database schema
5. **Repository Pattern** - Repository design patterns and use cases
6. **Service Layer Architecture** - Core FilesystemService implementation
7. **S3 Storage Strategy** - S3 integration and storage patterns
8. **Configuration** - Service configuration and environment setup
9. **Testing Strategy** - Testing approaches and strategies
10. **Migration & Performance** - Performance considerations and monitoring
11. **Specialized Services** - Domain-specific services built on FilesystemService

### Target Audience

This document serves:
- **Architects**: Understanding system design and integration patterns
- **Developers**: Implementation details and code examples
- **DevOps**: Configuration, deployment, and monitoring
- **Operations**: Troubleshooting and performance optimization