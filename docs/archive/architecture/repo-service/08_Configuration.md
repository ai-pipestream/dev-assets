# Repository Service Architecture - Section 8: Configuration

## S3 Configuration

```properties
# S3-Compatible Storage Configuration
aws.s3.region=us-east-1
aws.s3.multipart-threshold=5MB
aws.s3.concurrent-requests=10
aws.s3.max-connections=50

# Development (MinIO)
%dev.aws.s3.endpoint-override=http://localhost:9000
%dev.aws.s3.path-style-access-enabled=true

# Upload Configuration
repository.upload.chunk-size=5242880
repository.upload.max-chunk-size=10485760
repository.upload.timeout-seconds=300
```

## Database Configuration

```properties
# Database Configuration
quarkus.datasource.db-kind=mysql
quarkus.datasource.jdbc.max-size=20
quarkus.datasource.jdbc.min-size=5
quarkus.datasource.jdbc.validation-query-sql=SELECT 1

# Panache configuration
quarkus.hibernate-orm.packages=io.pipeline.repository.model
quarkus.hibernate-orm.physical-naming-strategy=org.hibernate.boot.model.naming.CamelCaseToUnderscoresNamingStrategy

# Test profile uses compose services
%test.quarkus.compose.devservices.files=src/test/resources/compose-test-services.yml
%test.quarkus.datasource.username=pipeline
%test.quarkus.datasource.password=password
%test.quarkus.hibernate-orm.database.generation=none
```

## Kafka Configuration

```properties
# Kafka Configuration
quarkus.kafka.bootstrap-servers=localhost:9092
quarkus.kafka.sasl.mechanism=PLAIN
quarkus.kafka.security.protocol=PLAINTEXT

# Event Channels
mp.messaging.outgoing.document-events.connector=smallrye-kafka
mp.messaging.outgoing.document-events.topic=document-events
mp.messaging.outgoing.document-events.key.serializer=org.apache.kafka.common.serialization.StringSerializer
mp.messaging.outgoing.document-events.value.serializer=io.pipeline.repository.events.DocumentEventSerializer

mp.messaging.outgoing.drive-events.connector=smallrye-kafka
mp.messaging.outgoing.drive-events.topic=drive-events
mp.messaging.outgoing.drive-events.key.serializer=org.apache.kafka.common.serialization.StringSerializer
mp.messaging.outgoing.drive-events.value.serializer=io.pipeline.repository.events.DriveEventSerializer
```

## Key Changes Made

1. **Removed Bucket Configuration**: Buckets are database-driven, not configuration-driven
2. **Added Upload Configuration**: Chunk size, timeouts, etc. are now configurable
3. **Simplified S3 Config**: Just the minimum needed for MinIO/S3 compatibility
4. **Database Pool Settings**: Added min/max pool sizes and validation query
5. **Extensible**: Easy to add more configuration as needed

## Configuration Usage

```java
@ConfigProperty(name = "repository.upload.chunk-size", defaultValue = "5242880")
int chunkSize;

@ConfigProperty(name = "repository.upload.max-chunk-size", defaultValue = "10485760")
int maxChunkSize;

@ConfigProperty(name = "repository.upload.timeout-seconds", defaultValue = "300")
int timeoutSeconds;
```