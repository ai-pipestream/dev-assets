# Port Allocation Strategy

This document is the single source of truth for the port allocation strategy for the Pipeline Engine system.

## Guiding Principles

1.  **Clarity and Consistency**: A single, clear port number for each service in a given environment.
2.  **Environment Separation**: Development and Test environments can run simultaneously without port conflicts.
3.  **Test Isolation**: Automated tests run on random ports to prevent conflicts and allow parallel execution.

---

## Port Allocation Environments

Our strategy is divided into three distinct environments:

| Environment / Profile | Service Type | Port Strategy | Justification |
| :--- | :--- | :--- | :--- |
| **Development (`%dev`)** | **Your Applications** | **Fixed Ports** (e.g., `38102`) | Provides predictable endpoints for local development and manual testing. |
| | **Infrastructure** | **Fixed Ports** (e.g., `3306`) | Defined in `compose-devservices.yml` for stable dependency access. |
| **Test (`%test`)** | **Service Under Test** | **Random Port** (`port: 0`) | Guarantees test isolation and prevents conflicts between test runs. |
| | **Infrastructure** | **Fixed Ports** (e.g., `3307`) | Defined in `compose-test-services.yml` for reliable connections to dependencies. |
| | **Mocked Services (Wiremock)** | **Random Port** (dynamic) | The test framework finds and assigns an available port at runtime, preventing all conflicts. |

---

## Canonical Port Assignments

### Core Application Services (38xxx Range)

These are the standard ports for local development (`%dev` profile).

| Service | Port | Protocol | Description |
| :--- | :--- | :--- | :--- |
| **PipeStream Engine** | `38100` | HTTP/gRPC | Core orchestration service |
| **Platform Registration** | `38101` | HTTP/gRPC | Service registry and health checks |
| **Repository Service** | `38102` | HTTP/gRPC | Document and metadata management |
| **OpenSearch Manager** | `38103` | HTTP/gRPC | OpenSearch operations and management |
| **Mapping Service** | `38104` | HTTP/gRPC | Data mapping and transformation |

### Processing Modules (39xxx Range)

Standard ports for local development (`%dev` profile).

| Module | Port | Protocol | Description |
| :--- | :--- | :--- | :--- |
| **echo** | `39000` | HTTP/gRPC | Simple test and echo module |
| **parser** | `39001` | HTTP/gRPC | Document parsing (Tika) |
| **chunker** | `39002` | HTTP/gRPC | Text segmentation |
| **embedder** | `39003` | HTTP/gRPC | Vector embedding generation |
| **opensearch-sink** | `39004` | HTTP/gRPC | Writes final output to OpenSearch |
| **test-harness** | `39040` | HTTP/gRPC | Module for testing and validation |

---

## Infrastructure Ports

These ports are managed via Docker Compose.

### Development Infrastructure (`compose-devservices.yml`)

| Service | Port | Description |
| :--- | :--- | :--- |
| **Traefik Dashboard** | `8080` | Traefik dashboard UI |
| **Traefik Entrypoint**| `38080`| Main entrypoint for all services |
| **Consul** | `8500` | Service Discovery UI & API |
| **MySQL** | `3306` | Primary database |
| **Kafka** | `9094` | Message streaming (localhost) |
| **Apicurio Registry** | `8081` | Schema Registry API |
| **Apicurio Registry UI**| `8888` | Schema Registry Web UI |
| **OpenSearch** | `9200` | Search & analytics engine API |
| **OpenSearch Dashboards**| `5601` | OpenSearch Web UI |
| **MinIO API** | `9000` | S3-compatible object storage |
| **MinIO Console** | `9001` | MinIO Web UI |
| **Kafka UI** | `8889` | Kafka Management UI |
| **Grafana (LGTM)** | `3001` | Metrics and observability dashboard |

### Test Infrastructure (`compose-test-services.yml`)

These ports are intentionally offset from development to prevent conflicts.

| Service | Port | Description |
| :--- | :--- | :--- |
| **Consul** | `8510` | Test Service Discovery |
| **MySQL** | `3307` | Test database |
| **Kafka** | `9095` | Test message streaming |
| **Apicurio Registry** | `8082` | Test Schema Registry API |
| **MinIO API** | `9010` | Test S3-compatible storage |
| **MinIO Console** | `9011` | Test MinIO Web UI |

---

## Code Configuration

To ensure consistency, all `application.properties` files should be updated to reflect this canonical port strategy. The `%dev` profile should use the fixed ports defined above, and the `%test` profile should use `quarkus.http.port=0`.
