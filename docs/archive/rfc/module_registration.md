# RFC: Module Registration System

## Overview

This RFC defines the requirements for implementing a comprehensive module registration system for PipeDoc processing modules. The system extends the existing service registration to provide specialized handling for document processing modules with enhanced metadata, schema validation, and centralized schema management.

## Background & Justification

### Current State Analysis

**Service Registration (Working)**:
We currently have 3 services using service registration successfully:
- `applications/mapping-service` - Uses configuration-based registration
- `applications/repository-service` - Uses service registration pattern  
- `applications/platform-registration-service` - The registration service itself

**Service Registration Implementation**:
- **Configuration**: `applications/mapping-service/src/main/resources/application.properties`
  ```properties
  service.registration.enabled=true
  service.registration.service-name=mapping-service
  service.registration.service-type=APPLICATION
  ```
- **Client**: `libraries/dynamic-grpc/src/main/java/io/pipeline/dynamic/grpc/registration/PlatformRegistrationClient.java`
  - Auto-registers on `@Observes StartupEvent` 
  - Calls `registerService()` method
  - Streams registration events back to service

**Module Registration (Partially Implemented)**:
- **Proto Definition**: `grpc-stubs/src/main/proto/platform_registration.proto`
  - Defines `RegisterModule(ModuleRegistrationRequest) returns (stream RegistrationEvent)`
  - Defines `ModuleRegistrationRequest` with basic fields
- **Service Implementation**: `applications/platform-registration-service/src/main/java/io/pipeline/registration/grpc/PlatformRegistrationService.java:103`
  - `registerModule()` method exists and delegates to `RegistrationHandler`
- **Handler Logic**: `applications/platform-registration-service/src/main/java/io/pipeline/registration/grpc/RegistrationHandler.java:94`
  - `registerModule()` converts module to service and registers with Consul
  - **Missing**: No callback to get `ServiceRegistrationMetadata`
  - **Missing**: No schema validation or database persistence

### Why We Need Enhanced Module Registration

**1. Modules vs Services - Different Requirements**:
- **Services**: General gRPC services, basic metadata, Consul registration sufficient
- **Modules**: PipeDoc processors, rich metadata, JSON schemas, UI integration needs

**2. Current Module Implementation Gap**:
The chunker implements the module interface but the platform does not yet consume its metadata:
- **Module Interface**: `grpc-stubs/src/main/proto/module_service.proto:GetServiceRegistration`
- **Chunker Implementation**: `modules/chunker/src/main/java/io/pipeline/module/chunker/ChunkerGrpcImpl.java`
  - Must return `ServiceRegistrationMetadata` (proto-authoritative). Any `ServiceRegistrationResponse` usages must be updated to match the proto.

**3. Rich Metadata Requirements**:
The `ServiceRegistrationMetadata` proto (`grpc-stubs/src/main/proto/module_service.proto`) contains:
- JSON config schema (OpenAPI 3.1 specification)
- Capabilities, tags, dependencies
- Health check status and validation
- UI display information (display_name, description, owner)

**4. System of Record Problem**:
Current approach stores minimal data in Consul, but we need:
- **100% of ServiceRegistrationMetadata** stored in database
- **Schema registry integration** for centralized schema management
- **Transactional consistency** across multiple systems

### Why Separate Module Registration Client

**Option 1: Enhance PlatformRegistrationClient** (Rejected)
```java
// This would lead to complex branching
void onStart(@Observes StartupEvent ev) {
    if (serviceRegistrationEnabled) {
        registerService(); // Current logic
    } else if (moduleRegistrationEnabled) {
        registerModule(); // New logic - different config, different flow
    }
}
```
**Problems**: 
- Violates single responsibility principle
- Complex conditional logic as module registration gets more sophisticated
- Mixed concerns in one class

**Option 2: Separate ModuleRegistrationClient** (Recommended)
```java
// Clean separation of concerns
@ApplicationScoped
public class ModuleRegistrationClient {
    void onStart(@Observes StartupEvent ev) {
        // Only handles module registration
        // Can evolve independently
    }
}
```
**Benefits**:
- Single responsibility - only handles modules
- Independent evolution as module registration gets more sophisticated
- Clear separation between service and module concerns
- Easier testing and maintenance

## Architecture & Design Decisions

### Current Implementation Analysis

**Existing Service Registration Flow**:
1. **Configuration**: `applications/mapping-service/src/main/resources/application.properties`
   ```properties
   service.registration.enabled=true
   service.registration.service-name=mapping-service
   service.registration.description=Document mapping and transformation service
   service.registration.service-type=APPLICATION
   service.registration.host=localhost
   service.registration.port=38105
   ```

2. **Auto-Registration**: `libraries/dynamic-grpc/src/main/java/io/pipeline/dynamic/grpc/registration/PlatformRegistrationClient.java:67`
   ```java
   void onStart(@Observes StartupEvent ev) {
       if (!registrationEnabled) return;
       registerService().subscribe().with(/* handle events */);
   }
   ```

3. **Platform Service**: `applications/platform-registration-service/src/main/java/io/pipeline/registration/grpc/PlatformRegistrationService.java:85`
   ```java
   public Multi<RegistrationEvent> registerService(ServiceRegistrationRequest request) {
       return registrationHandler.registerService(request);
   }
   ```

**Existing Module Registration (Incomplete)**:
1. **Proto Interface**: `grpc-stubs/src/main/proto/platform_registration.proto:30`
   ```protobuf
   service PlatformRegistration {
       rpc RegisterModule(ModuleRegistrationRequest) returns (stream RegistrationEvent);
   }
   ```

2. **Service Implementation**: `applications/platform-registration-service/src/main/java/io/pipeline/registration/grpc/PlatformRegistrationService.java:103`
   ```java
   public Multi<RegistrationEvent> registerModule(ModuleRegistrationRequest request) {
       return registrationHandler.registerModule(request);
   }
   ```

3. **Handler Logic**: `applications/platform-registration-service/src/main/java/io/pipeline/registration/grpc/RegistrationHandler.java:94-96`
   ```java
   public Multi<RegistrationEvent> registerModule(ModuleRegistrationRequest request) {
       ServiceRegistrationRequest serviceRequest = convertModuleToService(request);
       // Only converts to service registration - no callback for metadata!
   }
   ```

### Why Current Module Registration is Insufficient

**Problem 1: No Callback for Rich Metadata**
- Chunker implements `GetServiceRegistration` and returns full `ServiceRegistrationMetadata` with JSON schema
- **But platform service never calls it!**

**Problem 2: Limited Data Persistence**
- Current flow: `RegistrationHandler.java:543-580` (`convertModuleToService`)
- Only saves basic fields to Consul metadata
- **Missing**: JSON schema, capabilities, health status, full metadata

**Problem 3: No Schema Management**
- Chunker generates OpenAPI 3.1 schema via `SchemaExtractorService`
- **Missing**: Schema validation, versioning, Apicurio integration
- **Missing**: Database persistence for schema content

### Design Decisions & Justifications

**Decision 1: Linear Flow vs Concurrent Operations**
```
Option A (Concurrent): Register → [Health Check || Get Schema] → Validate → Save
Option B (Linear): Register → Health Check → Get Schema → Validate → Save
```
**Chosen**: Linear (Option B)
**Justification**: 
- One-time operation, simplicity over performance
- Easier error handling and transaction management
- Reduces complexity for debugging and maintenance

**Decision 2: Health Check Streaming vs Polling**
```
Current: Polling every 2 seconds until healthy
Proposed: Consul blocking queries (reactive streaming)
```
**Justification**:
- **Reactive by design**: Fits Multi<RegistrationEvent> pattern
- **Lower resource usage**: No tight polling overhead
- **Immediate notifications**: Low-latency updates with Consul index changes
- **Consul native**: Uses existing Consul infrastructure via blocking query options

**Decision 3: Transaction Scope**
```
Option A: Include Consul in transaction (distributed transaction)
Option B: DB + Apicurio transaction, Consul cleanup on failure
Option C: DB transaction only, eventual consistency
```
**Chosen**: Option B
**Justification**:
- **Consul as cache**: Service discovery cache, DB is system of record
- **Simpler than distributed transactions**: Avoid 2PC complexity
- **Cleanup possible**: Can unregister from Consul on DB failure
- **Consistent with current architecture**: Consul used for discovery, not persistence

**Decision 4: Fail Fast vs Graceful Degradation**
```
Schema validation fails:
Option A: Continue registration without schema
Option B: Fail entire registration
```
**Chosen**: Fail Fast (Option B)
**Justification**:
- **Data integrity**: Prevents stale/incomplete registrations
- **Clear error feedback**: Module knows immediately if schema is invalid
- **System reliability**: Better to fail cleanly than have partial state

## Requirements

### 1. ModuleRegistrationClient

**Location**: `libraries/dynamic-grpc/src/main/java/io/pipeline/dynamic/grpc/registration/ModuleRegistrationClient.java`

**Pattern**: Follow existing `PlatformRegistrationClient` pattern
- **Reference**: `libraries/dynamic-grpc/src/main/java/io/pipeline/dynamic/grpc/registration/PlatformRegistrationClient.java:67-85`
- **Same startup pattern**: `@Observes StartupEvent`
- **Same streaming pattern**: Subscribe to `Multi<RegistrationEvent>`
- **Same configuration pattern**: `@ConfigProperty` injection

**Responsibilities**:
- Auto-register modules on startup when `module.registration.enabled=true`
- Use same configuration pattern as `PlatformRegistrationClient`
- Send a minimal `ModuleRegistrationRequest` (module-name, host, port, version only)
- Do not include rich metadata; the platform will fetch metadata from the module via `GetServiceRegistration` after health
- Stream registration events back to module logs

**Configuration Properties**:
```properties
# Required
module.registration.enabled=true
module.registration.module-name=chunker
module.registration.host=localhost
module.registration.port=39102

# Optional (used for basic discoverability and operator context)
module.registration.description=Text chunking and segmentation module
module.registration.capabilities=text-chunking,nlp-processing
module.registration.tags=chunker,nlp,module
```

**Why Minimal Configuration**:
- Rich metadata comes from `GetServiceRegistration` (module = source of truth)
- Avoids duplication between config and code
- Keeps module config simple and consistent across modules

**Implementation Pattern**:
```java
@ApplicationScoped
public class ModuleRegistrationClient {
    
    @Inject
    PlatformRegistrationClient platformClient;
    
    // Same config pattern as PlatformRegistrationClient
    @ConfigProperty(name = "module.registration.enabled", defaultValue = "false")
    boolean enabled;
    
    // Same startup pattern as PlatformRegistrationClient:67
    void onStart(@Observes StartupEvent ev) {
        if (!enabled) return;
        
        // Send minimal request (no rich metadata). Platform will fetch via callback after health.
        // Reference: PlatformRegistrationClient.registerModule(...) supports omitting metadata
        platformClient.registerModule(null)
            .subscribe().with(/* same event handling pattern */);
    }
}
```

### 2. Enhanced Platform Registration Service

**Location**: `applications/platform-registration-service/src/main/java/io/pipeline/registration/grpc/RegistrationHandler.java`

**Current Implementation Analysis**:
- **Line 94**: `registerModule()` method exists
- **Line 96**: Converts module to service request
- **Line 543**: `convertModuleToService()` only handles basic metadata
- **Missing**: Callback to module's `GetServiceRegistration` method

**Enhanced `registerModule()` Flow**:

#### Current Flow (Incomplete)
```java
// RegistrationHandler.java:94-150
public Multi<RegistrationEvent> registerModule(ModuleRegistrationRequest request) {
    ServiceRegistrationRequest serviceRequest = convertModuleToService(request);
    // 1. Register with Consul
    // 2. Wait for health (polling)
    // 3. Complete - NO CALLBACK FOR METADATA!
}
```

#### New Flow (Complete)
```java
public Multi<RegistrationEvent> registerModule(ModuleRegistrationRequest request) {
    return Multi.createFrom().emitter(emitter -> {
        // 1. Start processing
        emitter.emit(STARTED);
        
        // 2. Register with Consul (same as current)
        registerWithConsul(serviceRequest, serviceId)
            
        // 3. Stream health status using Consul blocking queries (reactive loop)
        .flatMap(success -> streamHealthStatus(serviceId))
        
        // 4. Get module metadata (module = source of truth)
        .flatMap(healthy -> callModuleGetServiceRegistration(request))
        .invoke(meta -> emitter.emit(METADATA_RETRIEVED))
        
        // 5. Validate JSON schema (NEW - fail fast)
        .flatMap(metadata -> validateJsonSchemaOrSynthesizeDefault(metadata))
        .invoke(v -> emitter.emit(SCHEMA_VALIDATED))
        
        // 6. Save to database (reuse existing ModuleRepository)
        .flatMap(validMetadata -> saveToDatabase(validMetadata))
        .invoke(v -> emitter.emit(DATABASE_SAVED))
        
        // 7. Save to Apicurio (ModuleRepository.syncSchemaToApicurio)
        .flatMap(dbResult -> saveToApicurio(validMetadata))
        .invoke(v -> emitter.emit(APICURIO_REGISTERED))
        
        // 8. Optional test processing (if present in RegistrationRequest); not required for success
        .flatMap(apicurioResult -> maybeRunOptionalTest(request))

        // 9. Complete
        .subscribe().with(
            success -> emitter.emit(COMPLETED),
            error -> {
                unregisterFromConsul(serviceId);
                emitter.emit(FAILED);
            }
        );
    });
}
```

**New Method: `callModuleGetServiceRegistration()`**
```java
private Uni<ServiceRegistrationMetadata> callModuleGetServiceRegistration(ModuleRegistrationRequest request) {
    // Use DynamicGrpcClientFactory to call module's GetServiceRegistration
    // Reference: libraries/dynamic-grpc/src/main/java/io/pipeline/dynamic/grpc/client/DynamicGrpcClientFactory.java
    // Same pattern as mapping service test: applications/mapping-service/src/test/java/io/pipeline/application/DynamicGrpcTestClient.java:39
}
```

#### Error Handling (Fail Fast)
- **Any step fails**: Rollback DB transaction, unregister from Consul, stream FAILED event
- **Schema validation fails**: Fail fast with detailed error message
- **Apicurio fails**: Rollback and cleanup (schema registry is required)

#### Streaming Events
```protobuf
// Reference: grpc-stubs/src/main/proto/platform_registration.proto:EventType
// Technical events for debugging
STARTED, TRANSACTION_STARTED, CONSUL_REGISTERED, CONSUL_HEALTHY
// Business events for monitoring  
METADATA_RETRIEVED, SCHEMA_VALIDATED, DATABASE_SAVED, APICURIO_REGISTERED
// Final states
COMPLETED, FAILED
```

### 3. Database Schema & Persistence

**Current State (to be leveraged)**:
- Existing tables and entities already model module registrations and config schemas:
  - `modules` (`ServiceModule` entity) — system of record for registered modules
  - `config_schemas` (`ConfigSchema` entity) — stores full JSON/OpenAPI schema with Apicurio sync columns
  - Migrations: `V1__create_module_registry_tables.sql`, `V2__add_apicurio_sync_columns.sql`

**Persistence Flow**:
- Save/Update `ServiceModule` with module name, host, port, module version, metadata
- If the module provides a schema, or we synthesize a default KV schema when absent, persist it in `config_schemas.json_schema`
- Sync to Apicurio and record Apicurio artifact/global IDs
- Schema version in DB should reflect Apicurio’s version (Apicurio wins for schema versioning). The module’s own version is kept on the module record.

### 4. Apicurio Schema Registry Integration

**Requirements**:
- Store OpenAPI 3.1 schemas from `ServiceRegistrationMetadata.json_config_schema`
- Use schema hash for deduplication
- Handle versioning when schemas change
- Provide schema retrieval for UI/validation

**Reference Implementation Pattern**:
- Follow existing gRPC client patterns in `libraries/dynamic-grpc/src/main/java/io/pipeline/dynamic/grpc/client/`
- Use same reactive patterns as `PlatformRegistrationClient`

**Implementation**:
```java
@ApplicationScoped
public class ApicurioSchemaService {
    
    public Uni<String> registerSchema(String moduleName, String schemaContent) {
        // 1. Generate hash for deduplication
        String schemaHash = generateSchemaHash(schemaContent);
        
        // 2. Check if schema already exists in module_schemas table
        return checkExistingSchema(moduleName, schemaHash)
            .flatMap(existing -> {
                if (existing.isPresent()) {
                    return Uni.createFrom().item(existing.get().getApicurioSchemaId());
                }
                
                // 3. Register new schema with Apicurio
                return registerWithApicurio(moduleName, schemaContent)
                    .flatMap(apicurioId -> 
                        // 4. Save to module_schemas table
                        saveSchemaRecord(moduleName, schemaHash, schemaContent, apicurioId)
                            .map(saved -> apicurioId)
                    );
            });
    }
    
    public Uni<String> getSchema(String apicurioSchemaId) {
        // Retrieve schema from Apicurio
        // Cache in database for performance
    }
}
```

**No-schema fallback**:
- If a module returns no schema, synthesize a minimal OpenAPI 3.1 document that models a generic key-value configuration object (e.g., `type: object`, `additionalProperties: { type: string }`) and persist/register it to ensure consistent downstream behavior.

### 5. Health Check Streaming

**Current Implementation**: Polling in `RegistrationHandler.java:520-538`
```java
private Uni<Boolean> waitForHealthy(String serviceId) {
    return pollForHealthyInstance(serviceName, serviceId, MAX_HEALTH_CHECK_ATTEMPTS);
}

private Uni<Boolean> pollForHealthyInstance(String serviceName, String serviceId, int attemptsRemaining) {
    // Polls every 2 seconds - NOT REACTIVE!
}
```

**New Implementation**: Consul Blocking Queries (Reactive Streaming)
```java
private Uni<Boolean> streamHealthStatus(String serviceId) {
    // Use the Vert.x Mutiny Consul client with blocking query options and the X-Consul-Index
    // Re-issue the health query with the last index to form a reactive loop until this serviceId is healthy
}
```

**Justification for Streaming**:
- **Reactive by design**: Fits `Multi<RegistrationEvent>` pattern
- **Lower resource usage**: No polling overhead
- **Immediate notifications**: No 2-second delay
- **Consul native**: Uses existing Consul infrastructure

### 6. Configuration for Chunker

**Configuration for Chunker (example)**

**Add to**: `modules/chunker/src/main/resources/application.properties`
```properties
# Module Registration
module.registration.enabled=true
module.registration.module-name=chunker
module.registration.host=localhost
module.registration.port=39102
module.registration.description=Text chunking and segmentation module
module.registration.capabilities=text-chunking,nlp-processing,document-segmentation
module.registration.tags=chunker,nlp,text-processing,module

# Keep existing chunker-specific properties; remove old service.registration.* for modules
```

**Why Configuration-Based**:
- **Consistent**: Single, generic client handles all modules
- **Simple**: No module-specific startup beans needed
- **Flexible**: Easy to enable/disable registration
- **Maintainable**: Configuration separate from business logic

## Implementation Plan

### Phase 1: Core Infrastructure (ModuleRegistrationClient)

**Goal**: Get basic module registration working with existing platform service

**Tasks**:
1. **Create ModuleRegistrationClient**
   - **File**: `libraries/dynamic-grpc/src/main/java/io/pipeline/dynamic/grpc/registration/ModuleRegistrationClient.java`
   - **Pattern**: Copy from `PlatformRegistrationClient.java:67-85` (startup pattern)
   - **Dependencies**: Inject existing `PlatformRegistrationClient`
   - **Method**: Call existing `PlatformRegistrationClient.registerModule()` method (line 108)

2. **Update Chunker Configuration**
   - **File**: `modules/chunker/src/main/resources/application.properties`
   - **Remove**: `ChunkerModuleRegistration.java` startup bean
   - **Add**: Module registration properties (following mapping service pattern)

3. **Test Basic Flow**
   - Verify chunker auto-registers on startup
   - Verify platform service receives `ModuleRegistrationRequest`
   - Verify current flow completes (even without callback)

**Success Criteria**:
- Chunker starts and attempts module registration
- Platform service logs show module registration request received
- Registration completes with current limited flow

### Phase 2: Enhanced Registration Flow (Platform Service)

**Goal**: Add callback, database persistence, and schema validation

**Tasks**:
1. **Database Persistence (reuse existing)**
   - Reuse `ServiceModule` and `ConfigSchema` entities and existing migrations

2. **Enhance RegistrationHandler**
   - **File**: `applications/platform-registration-service/src/main/java/io/pipeline/registration/grpc/RegistrationHandler.java`
   - **Method**: Enhance `registerModule()` method (line 94)
   - **Add**: `callModuleGetServiceRegistration()` method
   - **Pattern**: Use `DynamicGrpcClientFactory` like mapping service test (line 39)

3. **Add Schema Validation Service**
   - **File**: `applications/platform-registration-service/src/main/java/io/pipeline/registration/service/SchemaValidationService.java`
   - **Dependencies**: JSON Schema validator (already exists in project)
   - **Method**: Validate OpenAPI 3.1 schemas, or synthesize and validate default KV schema when absent

4. **Replace Health Check Polling**
   - **File**: `applications/platform-registration-service/src/main/java/io/pipeline/registration/grpc/RegistrationHandler.java`
   - **Method**: Replace `pollForHealthyInstance()` with Consul blocking queries in a reactive loop
   - **Pattern**: Use Mutiny Consul client with blocking query options and X-Consul-Index

**Success Criteria**:
- Platform service calls chunker's `GetServiceRegistration` method
- Full `ServiceRegistrationMetadata` retrieved and logged
- Schema validation works (pass/fail scenarios)
- Database contains complete module data
- Health check streaming works

### Phase 3: Apicurio Integration

**Goal**: Add schema registry integration for centralized schema management

**Tasks**:
1. **Apicurio Client Service**
   - **File**: `applications/platform-registration-service/src/main/java/io/pipeline/registration/service/ApicurioSchemaService.java`
   - **Dependencies**: Apicurio Registry client
   - **Pattern**: Follow existing gRPC client patterns in `dynamic-grpc/client/`

2. **Schema Versioning & Deduplication**
   - **Versioning**: Use Apicurio’s version in DB; keep module version on module record
   - **Deduplication (optional later)**: Add a `schema_hash` field to detect identical schema content

3. **Transaction Management**
   - **Scope**: Database + Apicurio operations
   - **Rollback**: Cleanup on failure
   - **Pattern**: Use existing transaction patterns in platform service

**Success Criteria**:
- Schemas stored in Apicurio Schema Registry
- Schema deduplication works (same schema = same ID)
- Schema retrieval works for UI/validation
- Transaction rollback works on failures

### Phase 4: Testing & Validation

**Goal**: Comprehensive testing and error handling

**Tasks**:
1. **Unit Tests**
   - **Files**: 
     - `libraries/dynamic-grpc/src/test/java/io/pipeline/dynamic/grpc/registration/ModuleRegistrationClientTest.java`
     - `applications/platform-registration-service/src/test/java/io/pipeline/registration/grpc/RegistrationHandlerTest.java`
   - **Pattern**: Follow existing test patterns in both projects

2. **Integration Tests**
   - **File**: `applications/platform-registration-service/src/test/java/io/pipeline/registration/ModuleRegistrationIntegrationTest.java`
   - **Scope**: End-to-end flow with real chunker module
   - **Pattern**: Follow existing integration test patterns

3. **Error Scenario Testing**
   - Invalid JSON schemas
   - Module unreachable during callback
   - Database failures
   - Apicurio failures
   - Network timeouts

4. **Performance Testing**
   - Concurrent module registrations
   - Large schema handling
   - Transaction timeout scenarios

**Success Criteria**:
- All unit tests pass
- Integration tests cover happy path and error scenarios
- Performance acceptable for expected load
- Error messages clear and actionable

## Proto & Eventing Updates

- Extend `EventType` in `grpc-stubs/src/main/proto/platform_registration.proto` with the following (appended values):
  - `METADATA_RETRIEVED`
  - `SCHEMA_VALIDATED`
  - `DATABASE_SAVED`
  - `APICURIO_REGISTERED`
- Continue to emit `STARTED`, `VALIDATED`, `CONSUL_REGISTERED`, `HEALTH_CHECK_CONFIGURED`, `CONSUL_HEALTHY`, `COMPLETED`, `FAILED`.
- Regenerate gRPC stubs and update modules to compile against `ServiceRegistrationMetadata` return type for `GetServiceRegistration`.

## Optional Test Request

- `RegistrationRequest.test_request` is optional and will be executed last, after schema persistence and Apicurio registration. A failure here does not invalidate registration unless configured to enforce it in the future.

## Code References Summary

### Existing Code to Leverage
- **Service Registration Pattern**: `applications/mapping-service/src/main/resources/application.properties:4-11`
- **Startup Event Pattern**: `libraries/dynamic-grpc/src/main/java/io/pipeline/dynamic/grpc/registration/PlatformRegistrationClient.java:67`
- **gRPC Client Pattern**: `applications/mapping-service/src/test/java/io/pipeline/application/DynamicGrpcTestClient.java:39`
- **Module Interface**: `modules/chunker/src/main/java/io/pipeline/module/chunker/ChunkerGrpcImpl.java:68`
- **Platform Service**: `applications/platform-registration-service/src/main/java/io/pipeline/registration/grpc/RegistrationHandler.java:94`

### Proto Definitions
- **Platform Registration**: `grpc-stubs/src/main/proto/platform_registration.proto:30`
- **Module Service**: `grpc-stubs/src/main/proto/module_service.proto:GetServiceRegistration`
- **Service Registration Metadata**: `grpc-stubs/src/main/proto/module_service.proto:ServiceRegistrationMetadata`

### Files to Create
- `libraries/dynamic-grpc/src/main/java/io/pipeline/dynamic/grpc/registration/ModuleRegistrationClient.java`
- `applications/platform-registration-service/src/main/java/io/pipeline/registration/service/ApicurioSchemaService.java` (optional wrapper; `ModuleRepository` already integrates with Apicurio)

### Files to Modify
- `grpc-stubs/src/main/proto/platform_registration.proto` (add event types)
- `applications/platform-registration-service/src/main/java/io/pipeline/registration/grpc/RegistrationHandler.java` (enhance registerModule)
- `modules/chunker/src/main/resources/application.properties` (switch to module registration config)

### Files to Remove
- Module-specific startup beans for registration (e.g., `ChunkerModuleRegistration`) once the generic `ModuleRegistrationClient` is in place

## Success Criteria

1. **Chunker registers automatically** on startup with full metadata
2. **Schema validation works** - invalid schemas fail fast
3. **Database contains complete module data** - 100% of ServiceRegistrationMetadata saved
4. **Apicurio integration works** - schemas stored and retrievable
5. **Streaming events provide visibility** - clear status throughout registration
6. **Transaction integrity** - no partial/stale registrations
7. **Backward compatibility** - existing service registration unchanged

## Technical Justifications

### Why This Approach vs Alternatives

**Alternative 1: Extend Existing Service Registration**
```java
// This would require complex branching in PlatformRegistrationClient
void onStart(@Observes StartupEvent ev) {
    if (serviceRegistrationEnabled) {
        registerService(); // Current working logic
    } else if (moduleRegistrationEnabled) {
        registerModule(); // New complex logic
        // Different config properties
        // Different metadata handling
        // Different database schema
        // Different error handling
    }
}
```
**Problems**:
- Violates Single Responsibility Principle
- Complex conditional logic as requirements diverge
- Risk of breaking existing service registration
- Mixed concerns in one class
- Difficult to test and maintain

**Our Approach: Separate ModuleRegistrationClient**
- **Clean separation**: Each client handles one concern
- **Independent evolution**: Module registration can get sophisticated without affecting services
- **Risk mitigation**: Zero impact on existing service registration
- **Easier testing**: Each client tested independently

**Alternative 2: No Database, Use Consul Only**
```java
// Store everything in Consul metadata
consulService.register(serviceId, metadata.putAll(allModuleData));
```
**Problems**:
- **Consul limitations**: Metadata size limits, no complex queries
- **No schema management**: Can't integrate with Apicurio
- **No transaction support**: Can't ensure consistency
- **Performance**: Consul optimized for service discovery, not data storage

**Our Approach: Database as System of Record**
- **Consul for discovery**: Fast service lookup (existing strength)
- **Database for persistence**: Complex queries, transactions, full metadata
- **Apicurio for schemas**: Centralized schema management and validation
- **Clear separation**: Each system used for its strengths

**Alternative 3: Synchronous Registration**
```java
// Block until everything completes
ServiceRegistrationMetadata metadata = getServiceRegistration(request);
validateSchema(metadata.getJsonConfigSchema());
saveToDatabase(metadata);
saveToApicurio(metadata);
return "SUCCESS";
```
**Problems**:
- **Poor user experience**: No visibility into progress
- **Timeout issues**: Long-running operations fail silently
- **No partial success feedback**: All-or-nothing approach
- **Not reactive**: Doesn't fit existing architecture

**Our Approach: Reactive Streaming**
- **Real-time feedback**: Module sees progress via streaming events
- **Fits architecture**: Consistent with existing `Multi<RegistrationEvent>` pattern
- **Better debugging**: Clear visibility into where failures occur
- **Timeout handling**: Can stream progress even for long operations

### Performance & Scalability Considerations

**Registration Frequency**: One-time per module startup
- **Impact**: Low frequency means optimization less critical than correctness
- **Decision**: Favor simplicity and reliability over performance

**Schema Size**: OpenAPI 3.1 documents can be large (10KB-100KB+)
- **Mitigation**: Schema deduplication via hashing
- **Storage**: Database JSONB for efficient storage and querying
- **Caching**: Apicurio provides schema caching

**Concurrent Registrations**: Multiple modules starting simultaneously
- **Database**: Use connection pooling and proper indexing
- **Consul**: Already handles concurrent registrations well
- **Apicurio**: Schema deduplication prevents duplicate work

**Transaction Scope**: Keep transactions short
- **Approach**: Start transaction late, commit early
- **Scope**: Only database + Apicurio operations
- **Consul cleanup**: Handle outside transaction for simplicity

### Error Handling Strategy

**Fail Fast Philosophy**:
```java
// Current incomplete flow
registerModule() -> convertToService() -> registerWithConsul() -> DONE
// Problem: Partial success, no validation, no persistence

// New complete flow with fail fast
registerModule() -> validateRequest() -> registerWithConsul() -> 
waitForHealthy() -> getMetadata() -> validateSchema() -> 
saveToDatabase() -> saveToApicurio() -> commit()
// Any step fails -> rollback everything
```

**Why Fail Fast**:
- **Data integrity**: Prevents partial/inconsistent state
- **Clear feedback**: Module knows immediately what went wrong
- **Easier debugging**: Failure point is obvious
- **System reliability**: Better to fail cleanly than have corrupt data

**Rollback Strategy**:
1. **Database**: Standard transaction rollback
2. **Apicurio**: Delete schema if created (idempotent)
3. **Consul**: Unregister service (cleanup)
4. **Events**: Stream FAILED event with details

### Integration Points & Dependencies

**Existing Systems We Leverage**:
- **Consul**: Service discovery and health checks (no changes needed)
  - Reference: `applications/platform-registration-service/src/main/java/io/pipeline/registration/consul/`
- **Dynamic gRPC**: Client factory for module callbacks
  - Reference: `libraries/dynamic-grpc/src/main/java/io/pipeline/dynamic/grpc/client/DynamicGrpcClientFactory.java`
- **Database**: Existing connection and transaction management
  - Reference: `applications/platform-registration-service/src/main/java/io/pipeline/registration/entity/`

**New Dependencies**:
- **Apicurio Registry Client**: For schema management
- **JSON Schema Validator**: For OpenAPI validation (may already exist)

**Backward Compatibility**:
- **Service registration**: Zero changes to existing flow
- **Module interface**: Chunker already implements `GetServiceRegistration`
- **Proto definitions**: No breaking changes to existing protos

## Risks & Mitigations

### Technical Risks

**Risk**: Complex transaction management across multiple systems
**Impact**: High - Could lead to inconsistent state
**Probability**: Medium - Distributed systems are inherently complex
**Mitigation**: 
- Keep Consul outside transaction (use as cache)
- Use database as single source of truth
- Implement comprehensive rollback logic
- **Reference**: Follow existing transaction patterns in `applications/platform-registration-service/src/main/java/io/pipeline/registration/`

**Risk**: Apicurio dependency adds failure point
**Impact**: Medium - Schema management becomes unavailable
**Probability**: Low - Apicurio is designed for high availability
**Mitigation**:
- Fail fast with clear error messages
- Consider retry logic for transient failures
- Monitor Apicurio health separately
- **Fallback**: Could temporarily disable schema validation if critical

**Risk**: Schema validation performance impact
**Impact**: Low - Only affects registration time
**Probability**: Low - JSON schema validation is typically fast
**Mitigation**:
- Validate schemas concurrently where possible
- Cache validation results by schema hash
- Set reasonable timeouts for validation

**Risk**: Breaking existing service registration
**Impact**: High - Would break 3 working services
**Probability**: Very Low - Completely separate code paths
**Mitigation**:
- **Zero shared code**: Separate `ModuleRegistrationClient` class
- **Comprehensive testing**: Test existing services still work
- **Gradual rollout**: Deploy module registration without enabling it first

### Operational Risks

**Risk**: Database schema migration issues
**Impact**: High - Could break platform registration service
**Probability**: Low - Standard database migration practices
**Mitigation**:
- **Backward compatible migrations**: Add tables, don't modify existing
- **Rollback plan**: Keep migration reversible
- **Testing**: Test migrations on copy of production data

**Risk**: Increased complexity for developers
**Impact**: Medium - More configuration and concepts to understand
**Probability**: Medium - New system has learning curve
**Mitigation**:
- **Clear documentation**: Comprehensive examples and troubleshooting
- **Consistent patterns**: Follow existing service registration patterns
- **Good error messages**: Clear feedback when configuration is wrong

**Risk**: Monitoring and observability gaps
**Impact**: Medium - Harder to debug issues in production
**Probability**: Medium - New system needs new monitoring
**Mitigation**:
- **Comprehensive logging**: Log all registration steps and decisions
- **Metrics**: Track registration success/failure rates
- **Health checks**: Monitor all components (DB, Apicurio, Consul)
- **Streaming events**: Provide real-time visibility into registration process

### Business Risks

**Risk**: Delayed delivery due to complexity
**Impact**: Medium - Feature delivery timeline affected
**Probability**: Medium - Complex distributed system changes
**Mitigation**:
- **Phased approach**: Deliver incrementally with testing at each phase
- **MVP first**: Get basic flow working before adding advanced features
- **Parallel development**: Multiple developers can work on different phases

**Risk**: Adoption resistance from module developers
**Impact**: Low - Only affects new module development
**Probability**: Low - Configuration-based approach is simple
**Mitigation**:
- **Simple configuration**: Follow existing patterns developers know
- **Clear benefits**: Better error messages, schema validation, UI integration
- **Gradual migration**: Existing modules continue working, new modules get benefits

## Future Enhancements

1. **Functional Testing**: Automated module validation during registration
2. **Schema Evolution**: Handle backward compatibility for schema changes
3. **Module Discovery UI**: Web interface for browsing registered modules
4. **Metrics & Monitoring**: Registration success rates, schema validation metrics
5. **Multi-tenancy**: Support for different environments/namespaces

---

**Author**: Claude (Amazon Q)  
**Date**: December 2024  
**Status**: Draft - Pending Review
