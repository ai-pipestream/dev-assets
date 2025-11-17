# Repository Service Architecture - Section 2: Technology Stack

## Database Layer
- **Hibernate ORM Panache**: Blocking (non-reactive) for simplicity and reliability
- **MySQL**: Primary metadata storage
- **Flyway**: Database migrations and version control
- **Quarkus Compose Dev Services**: Test environment with `compose-test-services.yml`

## Storage Layer
- **S3-Compatible Storage**: 
  - **Development/Test**: MinIO for local development
  - **Production**: Compatible with AWS S3, Google Cloud Storage, Azure Blob Storage utilizing the S3 API by Amazon through the Quarkus extension
- **Protobuf Serialization**: 
  - **Quarkus Integration**: Uses Quarkus protobuf support with Apicurio Registry
  - **Version Compatibility**: Apicurio uses newer protobuf version, compatible with gRPC
- **Multi-part Uploads**: Support for large file uploads
- **Encryption**: Default key storage with AWS KMS support

## Integration Layer
- **gRPC**: Service communication and API endpoints
- **Kafka**: Event publishing with Apicurio Registry for schema management
- **OpenSearch**: Search and indexing
- **WireMock**: Default mocking for external systems and dependent gRPC services in testing

## Development & Build Tools
- **Quarkus-Driven**: Built on Quarkus framework for cloud-native development
- **Gradle**: Build tool with version management in `libs.versions.toml`
- **Container Output**: All components output base containers

## Monitoring & Observability
- **Prometheus**: Metrics collection and monitoring
- **Grafana**: Metrics visualization and dashboards
- **Logback**: Logging framework (Quarkus default)
- **Quarkus Observability**: Built-in health checks, metrics, and tracing

## Quarkus Features
- **Dev Services**: Automatic service provisioning for development and testing
- **Health Checks**: Built-in health monitoring endpoints
- **Metrics**: Prometheus metrics collection
- **Configuration**: Externalized configuration with profiles
- **Hot Reload**: Development-time hot reloading
- **Native Compilation**: GraalVM native image support
- **Extension Ecosystem**: Rich ecosystem of extensions for integration

## Version Management
- **Centralized**: All dependency versions managed in `libs.versions.toml`
- **Quarkus BOM**: Leverages Quarkus Bill of Materials for consistent versions
- **Apicurio Integration**: Schema registry for protobuf version management