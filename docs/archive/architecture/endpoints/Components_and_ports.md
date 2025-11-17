# Pipeline Components and Ports

This document provides a high-level overview of the services and components that make up the Pipeline Engine system.

## Port Allocation Strategy

The canonical port allocation strategy for all services and infrastructure is defined in the **[Port Allocation Strategy](./Port_allocations.md)** document. This is the single source of truth for all port assignments.

Refer to that document for all details regarding development, test, and infrastructure port mappings.

## Service Status

| Service | Status | Notes |
| :--- | :--- | :--- |
| **opensearch-manager** | ✅ Active | Manages OpenSearch operations |
| **mapping-service** | ✅ Active | Handles data mapping and transformation |
| **repository-service** | ✅ Active | Manages document and metadata storage |
| **platform-registration-service** | ✅ Active | Handles service registration and health checks |
| **pipestream-engine** | ⚠️ Deprecated | The original engine; slated for rewrite |

| Module | Status | Notes |
| :--- | :--- | :--- |
| **echo** | ✅ Active | Simple test and echo module |
| **parser** | ✅ Active | Document parsing (Tika) |
| **chunker** | ✅ Active | Text segmentation |
| **embedder** | ✅ Active | Vector embedding generation |
| **opensearch-sink** | ✅ Active | Writes final output to OpenSearch |
| **test-harness** | ✅ Active | Module for testing and validation |
| **draft** | 📋 Template | Template for creating new modules |

**Status Key:**
- ✅ **Active**: In active development and use.
- ⚠️ **Deprecated**: Functionality is being replaced or rewritten.
- 📋 **Template**: A template for creating new components; not a functional service.
