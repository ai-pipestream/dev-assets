# Pipeline Engine: System Network Overview

## Introduction

This document provides a comprehensive network-level view of the Pipeline Engine system, showing how all services communicate through dynamic gRPC discovery, event-driven Kafka messaging, and S3 payload hydration patterns. This architecture supports the core principle that **modules never talk to each other directly - they only communicate through the Engine**.

## Complete System Network Architecture

```mermaid
graph TB
    %% External Layer
    subgraph "External Sources"
        Web[Web Scrapers]
        Files[File Systems] 
        APIs[External APIs]
    end
    
    %% Infrastructure Layer
    subgraph "Infrastructure Services"
        Consul[Consul<br/>Service Discovery<br/>& Configuration]
        Kafka[Kafka<br/>Message Bus]
        S3[S3 Compatible Storage<br/>Payload Storage]
        OpenSearchCluster[OpenSearch<br/>Search Engine]
        MySQL[(MySQL<br/>Metadata DB)]
        LB[Load Balancer<br/>Traffic Distribution]
    end
    
    %% Core Services Layer
    subgraph "Core Platform Services"
        Engine[Pipeline Engine<br/>:38100<br/>Orchestrator]
        RegistrationSvc[Platform Registration<br/>:38101<br/>Service Registry]
        RepoSvc[Repository Service<br/>:38102<br/>Document Management]
        SearchMgr[OpenSearch Manager<br/>:38103<br/>Search Management]
    end
    
    %% Processing Modules Layer  
    subgraph "Processing Modules"
        Parser[Parser Module<br/>Document Processing]
        Chunker[Chunker Module<br/>Text Segmentation]
        Embedder[Embedder Module<br/>Vector Generation]
        Sink[OpenSearch Sink<br/>Index Writer]
    end
    
    %% Communication Patterns
    
    %% Dynamic gRPC Discovery
    Engine -.->|"1. Service Discovery"| Consul
    RepoSvc -.->|"Dynamic gRPC"| Consul
    SearchMgr -.->|"Self Registration"| Consul
    RegistrationSvc -.->|"Health Checks"| Consul
    
    %% gRPC Connections (Solid lines for direct calls)
    Engine <-->|"gRPC Calls"| Parser
    Engine <-->|"gRPC Calls"| Chunker
    Engine <-->|"gRPC Calls"| Embedder
    Engine <-->|"gRPC Calls"| Sink
    RepoSvc <-->|"Dynamic gRPC<br/>via Stork"| SearchMgr
    
    %% Kafka Event Streams (Dashed lines for async messaging)
    Engine --->|"Process Events"| Kafka
    RepoSvc -.->|"Node Updates<br/>Drive Events"| Kafka
    Kafka -.->|"Index Updates"| SearchMgr
    Kafka -.->|"Module Events"| RegistrationSvc
    
    %% S3 Payload Pattern (Dotted lines for payload refs)
    Engine -.->|"Store Payloads"| S3
    Parser -.->|"Hydrate from<br/>S3 References"| S3
    Chunker -.->|"Hydrate from<br/>S3 References"| S3
    Embedder -.->|"Hydrate from<br/>S3 References"| S3
    Sink -.->|"Hydrate from<br/>S3 References"| S3
    RepoSvc <.->|"Document Storage"| S3
    
    %% Data Storage
    RepoSvc <-->|"Metadata"| MySQL
    SearchMgr <-->|"Indexing"| OpenSearchCluster
    Sink -->|"Final Index"| OpenSearchCluster
    
    %% External Inputs (via Load Balancer in production)
    Web -->|"Documents"| LB
    Files -->|"File Upload"| LB
    APIs -->|"API Data"| LB
    LB -->|"Route to Services"| Engine
    LB -->|"Route to Services"| RepoSvc
    
    %% Styling
    classDef infrastructure fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef platform fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef modules fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef external fill:#fff3e0,stroke:#e65100,stroke-width:2px
    
    class Consul,Kafka,S3,OpenSearchCluster,MySQL,LB infrastructure
    class Engine,RegistrationSvc,RepoSvc,SearchMgr platform
    class Parser,Chunker,Embedder,Sink modules
    class Web,Files,APIs external
```

## Key Communication Patterns

### 1. Dynamic gRPC Service Discovery

The system uses **SmallRye Stork** with **Consul** for dynamic service discovery, eliminating hardcoded service endpoints:

```mermaid
sequenceDiagram
    participant Repo as Repository Service
    participant Consul as Consul Registry
    participant Search as OpenSearch Manager
    
    Note over Repo,Search: Dynamic gRPC Client Discovery
    
    Repo->>+Consul: 1. Query service instances<br/>service=opensearch-manager
    Consul-->>-Repo: 2. Return healthy instances<br/>[host:port, health status]
    
    Repo->>+Search: 3. gRPC Call via StorkGrpcChannel<br/>SearchFilesystemMeta(query)
    Search-->>-Repo: 4. Search Results<br/>(up to 2GB response)
    
    Note over Repo: 5. Channel cached for 5min<br/>for subsequent calls
```

**Benefits:**
- **No hardcoded URLs** - Services discover each other at runtime
- **Health-aware routing** - Only calls healthy service instances  
- **Automatic failover** - Falls back to other instances if one fails
- **Load balancing** - Distributes calls across available instances

### 2. Event-Driven Kafka Architecture

**Kafka Topics** decouple services for async processing and real-time data flow:

```mermaid
flowchart TD
    subgraph "Event Producers"
        RepoSvc[Repository Service]
        Engine[Pipeline Engine]
    end
    
    subgraph "Kafka Topics"
        NodeUpdates[node-updates]
        DriveUpdates[drive-updates] 
        ProcessEvents[process-events]
        ModuleEvents[module-events]
    end
    
    subgraph "Event Consumers"
        SearchMgr[OpenSearch Manager]
        RegistrationSvc[Platform Registration]
    end
    
    RepoSvc -->|"Node Created/Updated"| NodeUpdates
    RepoSvc -->|"Drive Created"| DriveUpdates
    Engine -->|"Processing Status"| ProcessEvents
    Engine -->|"Module Registration"| ModuleEvents
    
    NodeUpdates -->|"Index Documents"| SearchMgr
    DriveUpdates -->|"Index Drive Metadata"| SearchMgr  
    ProcessEvents -->|"Track Pipeline Status"| SearchMgr
    ModuleEvents -->|"Service Discovery"| RegistrationSvc
```

### 3. S3 Payload Hydration Pattern

Kafka and file payloads are stored in **S3** with **references** passed through Kafka for efficiency:

```mermaid
sequenceDiagram
    participant Engine as Pipeline Engine
    participant S3 as S3 Storage
    participant Kafka as Kafka Topic
    participant Module as Processing Module
    
    Note over Engine,Module: S3 Payload Hydration Pattern
    
    Engine->>+S3: 1. Store payload<br/>PUT /bucket/payload-id
    S3-->>-Engine: 2. Storage confirmation<br/>s3://bucket/payload-id
    
    Engine->>Kafka: 3. Publish event with S3 reference<br/>{"payloadRef": "s3://bucket/payload-id", ...}
    
    Kafka->>Module: 4. Consume event<br/>(lightweight message)
    
    Module->>+S3: 5. Hydrate payload<br/>GET /bucket/payload-id  
    S3-->>-Module: 6. Full payload data<br/>(could be GBs)
    
    Note over Module: 7. Process full payload<br/>with all data available
```

**Benefits:**
- **Kafka stays lightweight** - Only metadata and references in messages
- **Scalable payload sizes** - No Kafka message size limits
- **Efficient storage** - Deduplicated payloads in S3
- **On-demand hydration** - Modules only fetch what they need

## Service Port Allocation

The canonical port allocation strategy for all services and infrastructure is defined in the **[Port Allocation Strategy](./endpoints/Port_allocations.md)** document. This is the single source of truth for all port assignments.

## Infrastructure Dependencies

| Component | Purpose | Production | Development |
|-----------|---------|------------|-------------|
| **Consul** | Service discovery, health checks, config KV store | Multi-datacenter cluster | Single-node local |
| **Kafka** | Async messaging, event streaming | Managed Kafka service | Local Kafka cluster |
| **S3 Compatible Storage** | Document and payload storage | AWS S3, Google Cloud Storage, Azure Blob | MinIO (local S3-compatible) |
| **MySQL** | Metadata and relationship storage | Managed MySQL service | Local MySQL container |
| **OpenSearch** | Full-text search and vector similarity | Managed OpenSearch cluster | Local OpenSearch |
| **Load Balancer** | Traffic distribution and SSL termination | Cloud Load Balancer (ALB, GLB, etc.) | Traefik (dev proxy only) |

## Development vs Production Deployment

### Development Environment
- **Traefik** - Local reverse proxy and SSL termination for development
- **MinIO** - S3-compatible object storage for local testing
- **Local containers** - All infrastructure runs in Docker containers
- **Frontend Development Server** - Node.js development server with hot reload

### Production Environment  
- **Cloud Load Balancer** - AWS ALB, Google Cloud Load Balancer, Azure Load Balancer
- **Managed Object Storage** - AWS S3, Google Cloud Storage, Azure Blob Storage
- **Managed Services** - Cloud-provided Kafka, OpenSearch, MySQL services
- **Static Frontend Hosting** - CDN-hosted static assets with API gateway routing

### Key Architectural Differences
| Aspect | Development | Production |
|--------|-------------|------------|
| **Load Balancing** | Traefik (local proxy) | Cloud Load Balancer |
| **Object Storage** | MinIO (S3-compatible) | Native cloud storage (S3, GCS, Azure) |
| **Service Discovery** | Local Consul | Multi-datacenter Consul cluster |
| **Frontend** | Development server | Static hosting + CDN |
| **TLS/SSL** | Self-signed certificates | Cloud-managed certificates |
| **Scaling** | Single instance | Auto-scaling groups |

## Next Steps

This network overview provides the foundation for understanding:

1. **[Dynamic Service Discovery](dynamic-service-discovery.md)** - How services find each other
2. **[Event-Driven Flows](event-driven-flows.md)** - Kafka message patterns  
3. **[gRPC Communication Patterns](grpc-communication-patterns.md)** - Synchronous service calls
4. **[S3 Payload Hydration](s3-payload-hydration.md)** - Large data handling patterns

Each of these patterns work together to create a resilient, scalable, and maintainable distributed system.