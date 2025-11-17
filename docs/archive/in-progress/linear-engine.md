# Linear Pipeline Processor Service - Development Approach

## Overview

The Linear Pipeline Processor is a **pure Quarkus gRPC service** with an integrated **Vue.js frontend** designed to simplify pipeline development and testing. This service serves as a **strategic sandbox** for testing new features before promoting them to the network topology engine.

### Strategic Context

This linear engine is part of a **dual-track development strategy**:

1. **Linear Engine (This Service)**: Simplified sequential processing for rapid feature development and testing
2. **Network Topology Engine**: Complex graph-based processing for production workloads

The linear engine will typically be **ahead of the network version** since it's simpler and provides an end-to-end testing sandbox. Eventually, both engines will converge to use the same models, with the linear engine introducing **streaming versions** of network topology features.

### Evolutionary Path

- **Phase 1**: Independent linear processing with its own models
- **Phase 2**: Feature testing and validation in linear context  
- **Phase 3**: Promotion of proven features to network topology engine
- **Phase 4**: Convergence to shared models with streaming network capabilities

## Service Architecture

### Core Concepts

- **Linear Processing**: Sequential execution of pipeline stages (no complex branching)
- **Development-Focused**: Optimized for pipeline creation, testing, and debugging
- **Real-time Streaming**: Live execution progress and results
- **Interactive Designer**: Visual pipeline creation with immediate validation
- **Module Testing Sandbox**: Quick testing of individual modules and configurations

### Frontend Architecture Integration

This service follows the **standardized frontend architecture** defined in `docs/in-progress/frontend-standardization.md`:

- **gRPC-first communication** through central web-proxy gateway
- **Type-safe end-to-end** communication using generated TypeScript from protobuf
- **Standardized Vue.js 3 + Vuetify** technology stack
- **Shared component library** for consistent UI patterns
- **Quinoa integration** for seamless Quarkus deployment

The frontend will serve as a **reference implementation** for the standardized architecture, demonstrating:
- Complex form generation with JSONForms
- Real-time streaming UI updates
- Shared component usage patterns
- gRPC-Web integration best practices

## Project Structure

```
applications/linear-pipeline-processor/
├── src/main/java/
│   ├── io/pipeline/linear/processor/
│   │   ├── service/           # gRPC service implementations
│   │   │   ├── LinearPipelineProcessorService.java
│   │   │   ├── ValidationService.java
│   │   │   └── TestingService.java
│   │   ├── engine/            # Pipeline execution engine
│   │   │   ├── LinearExecutionEngine.java
│   │   │   ├── StageExecutor.java
│   │   │   ├── ResultStreamer.java
│   │   │   └── ExecutionContext.java
│   │   ├── validation/        # Pipeline validation logic
│   │   │   ├── PipelineValidator.java
│   │   │   ├── ModuleConnectivityChecker.java
│   │   │   ├── ConfigurationValidator.java
│   │   │   └── ValidationResult.java
│   │   ├── storage/           # Pipeline persistence
│   │   │   ├── PipelineRepository.java
│   │   │   ├── ExecutionHistoryService.java
│   │   │   └── MetricsCollector.java
│   │   ├── client/            # Module communication
│   │   │   ├── ModuleClientFactory.java
│   │   │   ├── ServiceDiscoveryClient.java
│   │   │   └── HealthChecker.java
│   │   └── config/            # Quarkus configuration
│   │       ├── GrpcConfig.java
│   │       ├── StorageConfig.java
│   │       └── ModuleConfig.java
├── src/main/ui-vue/           # Vue.js frontend (Quinoa integration)
│   ├── src/
│   │   ├── components/        # Shared UI components
│   │   │   ├── designer/      # Pipeline designer components
│   │   │   │   ├── PipelineCanvas.vue
│   │   │   │   ├── StageEditor.vue
│   │   │   │   ├── ModuleLibrary.vue
│   │   │   │   └── ValidationPanel.vue
│   │   │   ├── dev-tools/     # Development tools components
│   │   │   │   ├── TestRunner.vue
│   │   │   │   ├── ExecutionMonitor.vue
│   │   │   │   ├── LogViewer.vue
│   │   │   │   └── MetricsDashboard.vue
│   │   │   └── shared/        # Reusable components
│   │   │       ├── PipelineStageCard.vue
│   │   │       ├── ModuleSelector.vue
│   │   │       ├── ConfigEditor.vue
│   │   │       ├── ValidationDisplay.vue
│   │   │       ├── ExecutionProgress.vue
│   │   │       └── DocumentViewer.vue
│   │   ├── views/             # Main application views
│   │   │   ├── PipelineDesigner.vue
│   │   │   ├── TestingWorkbench.vue
│   │   │   ├── ExecutionHistory.vue
│   │   │   └── ModuleExplorer.vue
│   │   ├── stores/            # Pinia state management
│   │   │   ├── pipelineStore.js
│   │   │   ├── executionStore.js
│   │   │   ├── moduleStore.js
│   │   │   └── validationStore.js
│   │   ├── services/          # gRPC client services
│   │   │   ├── linearPipelineService.js
│   │   │   ├── validationService.js
│   │   │   └── moduleService.js
│   │   ├── utils/             # Utility functions
│   │   │   ├── grpcClient.js
│   │   │   ├── validation.js
│   │   │   └── formatting.js
│   │   ├── App.vue
│   │   └── main.js
│   ├── package.json
│   ├── vite.config.js
│   └── tsconfig.json
├── src/main/resources/
│   ├── application.properties
│   └── META-INF/
│       └── resources/         # Static resources served by Quarkus
├── src/test/java/             # Backend tests
└── build.gradle
```

## Backend Implementation Strategy

### 1. gRPC Service Layer

#### LinearPipelineProcessorService
- **ExecuteLinearPipeline**: Stream-based pipeline execution with real-time progress
- **BatchProcessLinearDocuments**: Efficient batch processing with bidirectional streaming
- **ProcessLinearDocument**: Single document/module testing for quick feedback
- **ValidateLinearPipeline**: Comprehensive pipeline validation

**Key Implementation Points:**
- **Reactive Streams**: Use Mutiny for non-blocking operations
- **Error Handling**: Comprehensive error recovery and reporting
- **Resource Management**: Proper cleanup of long-running operations
- **Metrics Collection**: Performance and usage metrics

### 2. Pipeline Execution Engine

#### LinearExecutionEngine
```java
@ApplicationScoped
public class LinearExecutionEngine {
    // Core execution logic for linear pipelines
    // Handles stage sequencing, error recovery, and result streaming
    
    public Multi<ExecuteLinearPipelineResponse> executeLinearPipeline(
        ExecuteLinearPipelineRequest request) {
        // Implementation details
    }
}
```

#### StageExecutor
- **Module Communication**: Dynamic gRPC client creation for module addresses
- **Configuration Management**: JSON-based module configuration handling
- **Timeout Management**: Configurable timeouts for module operations
- **Result Processing**: Transform and validate stage outputs

#### ResultStreamer
- **Real-time Updates**: Stream execution progress to frontend
- **Backpressure Handling**: Manage high-volume result streams
- **Error Propagation**: Proper error handling in streaming context

### 3. Validation Framework

#### PipelineValidator
- **Configuration Validation**: JSON schema validation for module configs
- **Dependency Checking**: Verify stage dependencies and execution order
- **Module Compatibility**: Check input/output compatibility between stages

#### ModuleConnectivityChecker
- **Service Discovery**: Integration with Consul for module discovery
- **Health Checking**: Verify module availability and responsiveness
- **Version Compatibility**: Check module API version compatibility

### 4. Storage Layer

#### PipelineRepository
- **CRUD Operations**: Create, read, update, delete pipeline definitions
- **Version Management**: Track pipeline versions and changes
- **Search and Filtering**: Find pipelines by various criteria

#### ExecutionHistoryService
- **Execution Tracking**: Store execution results and metrics
- **Performance Analytics**: Analyze execution patterns and performance
- **Audit Trail**: Maintain execution history for debugging

## Frontend Implementation Strategy

### 1. Standardized Architecture Compliance

Following the **frontend standardization guide**, this service implements:

#### **A. Technology Stack**
- **Vue.js 3** with Composition API and TypeScript
- **Vuetify 3.9.3** for Material Design components  
- **Vite 7.0.6** for fast development and building
- **JSONForms 3.7.0-alpha.0** for schema-driven forms
- **Connect-ES** for gRPC-Web communication

#### **B. Communication Pattern**
```typescript
// All communication through web-proxy gateway
const transport = createConnectTransport({
  baseUrl: 'http://localhost:38106', // Web-proxy
  useBinaryFormat: true // Binary protobuf for performance
});

const linearClient = createClient(LinearPipelineProcessor, transport);
```

#### **C. Proto Integration**
```typescript
// Import from centralized proto package
import { 
  ExecuteLinearPipelineRequest,
  LinearPipeline,
  LinearPipelineStage 
} from '@pipeline/proto-stubs/types';

import { LinearPipelineProcessor } from '@pipeline/proto-stubs/connect';
```

### 2. Project Structure (Updated)

```
applications/linear-pipeline-processor/
├── src/main/java/                    # Backend (unchanged)
├── src/main/webui/                   # Standardized frontend structure
│   ├── src/
│   │   ├── components/
│   │   │   ├── designer/
│   │   │   │   ├── LinearPipelineCanvas.vue
│   │   │   │   ├── StageSequencer.vue
│   │   │   │   ├── ModuleLibrary.vue
│   │   │   │   └── ValidationPanel.vue
│   │   │   ├── dev-tools/
│   │   │   │   ├── TestRunner.vue
│   │   │   │   ├── ExecutionMonitor.vue
│   │   │   │   ├── StreamingViewer.vue
│   │   │   │   └── MetricsDashboard.vue
│   │   │   └── shared/              # Uses @pipeline/shared-ui
│   │   │       ├── UniversalConfigCard.vue
│   │   │       ├── ExecutionProgress.vue
│   │   │       └── DocumentViewer.vue
│   │   ├── services/
│   │   │   ├── linearPipelineClient.ts
│   │   │   ├── streamingService.ts
│   │   │   └── validationService.ts
│   │   ├── stores/                  # Pinia state management
│   │   │   ├── pipelineStore.ts
│   │   │   ├── executionStore.ts
│   │   │   └── streamingStore.ts
│   │   ├── views/
│   │   │   ├── LinearDesigner.vue
│   │   │   ├── TestingWorkbench.vue
│   │   │   └── ExecutionHistory.vue
│   │   ├── App.vue
│   │   └── main.ts
│   ├── package.json                 # Standardized dependencies
│   ├── vite.config.ts              # Standardized Vite config
│   └── tsconfig.json
├── src/main/resources/
│   └── application.properties       # Quinoa configuration
└── build.gradle
```

### 3. Shared Component Integration

#### **A. UniversalConfigCard Usage**
```vue
<template>
  <UniversalConfigCard
    :schema="moduleSchema"
    :initial-data="stageConfig"
    @update="handleConfigUpdate"
  />
</template>

<script setup lang="ts">
import { UniversalConfigCard } from '@pipeline/shared-ui'
import type { JsonSchema7 } from '@jsonforms/core'

const props = defineProps<{
  moduleSchema?: JsonSchema7
  stageConfig: any
}>()
</script>
```

#### **B. Real-time Streaming Components**
```vue
<template>
  <StreamingExecutionViewer
    :execution-stream="executionStream"
    :pipeline="currentPipeline"
    @stage-complete="handleStageComplete"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useLinearPipelineStore } from '@/stores/pipelineStore'

const pipelineStore = useLinearPipelineStore()
const executionStream = ref()

onMounted(async () => {
  // Connect to streaming execution
  executionStream.value = await pipelineStore.executeWithStreaming(pipelineId)
})
</script>
```

### 4. Development Workflow Integration

#### **A. Quinoa Configuration**
```properties
# application.properties
quarkus.quinoa.ui-dir=src/main/webui
quarkus.quinoa.build-dir=src/main/resources/META-INF/resources
quarkus.quinoa.package-manager=pnpm
%dev.quarkus.quinoa.dev-server.port=33100  # Linear engine frontend port
```

#### **B. Development Startup Sequence**
```bash
# 1. Start web-proxy (required for all frontends)
cd applications/node/web-proxy && pnpm dev

# 2. Start linear engine with integrated frontend
./gradlew :applications:linear-pipeline-processor:quarkusDev

# 3. Frontend available at http://localhost:8080 (served by Quarkus)
# 4. Frontend dev server at http://localhost:33100 (hot reload)
```

### 5. Advanced Frontend Features

#### **A. Real-time Streaming UI**
```typescript
// streamingService.ts
export class StreamingExecutionService {
  async executeWithStreaming(request: ExecuteLinearPipelineRequest) {
    const stream = linearClient.executeLinearPipeline(request);
    
    return {
      async *[Symbol.asyncIterator]() {
        for await (const response of stream) {
          yield {
            documentId: response.documentId,
            currentStage: response.currentStage,
            totalStages: response.totalStages,
            stageName: response.stageName,
            result: response.stageResult,
            isFinal: response.isFinal
          };
        }
      }
    };
  }
}
```

#### **B. Pipeline Designer with Drag-and-Drop**
```vue
<template>
  <div class="linear-pipeline-canvas">
    <draggable
      v-model="pipelineStages"
      group="stages"
      @change="handleStageReorder"
    >
      <template #item="{ element: stage, index }">
        <LinearStageCard
          :stage="stage"
          :index="index"
          :total-stages="pipelineStages.length"
          @configure="openStageConfig"
          @remove="removeStage"
        />
      </template>
    </draggable>
  </div>
</template>
```

#### **C. Schema-driven Configuration Forms**
```vue
<template>
  <v-card>
    <v-card-title>Configure {{ stageName }}</v-card-title>
    <v-card-text>
      <JsonForms
        :data="stageConfig"
        :schema="moduleSchema"
        :uischema="moduleUISchema"
        :renderers="vuetifyRenderers"
        @change="handleConfigChange"
      />
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { JsonForms } from '@jsonforms/vue'
import { vuetifyRenderers } from '@jsonforms/vue-vuetify'
</script>
```

## Integration Points

### 1. Module Communication

#### Dynamic gRPC Client Creation
```java
@ApplicationScoped
public class ModuleClientFactory {
    public PipeStepProcessorGrpc.PipeStepProcessorStub createClient(String moduleAddress) {
        // Create gRPC client for module address
        // Handle connection pooling and lifecycle management
    }
}
```

#### Service Discovery Integration
- **Consul Integration**: Use existing Consul setup for module discovery
- **Health Checking**: Regular health checks for module availability
- **Load Balancing**: Distribute requests across module instances
- **Circuit Breaker**: Handle module failures gracefully

### 2. Document Management

#### Repository Service Integration
- **Document Storage**: Use existing repository-service for document persistence
- **Metadata Management**: Store document metadata and annotations
- **Version Control**: Track document versions and changes
- **Search Integration**: Leverage existing search capabilities

#### Document Processing
- **Support Multiple Sources**: Both storage_id and inline documents
- **Format Handling**: Support various document formats and encodings
- **Result Persistence**: Configurable result storage and retention
- **Streaming Support**: Handle large documents efficiently

### 3. Monitoring and Observability

#### Metrics Collection
```java
@ApplicationScoped
public class MetricsCollector {
    @Counted(name = "pipeline_executions_total")
    @Timed(name = "pipeline_execution_duration")
    public void recordExecution(String pipelineId, Duration duration, boolean success) {
        // Record execution metrics
    }
}
```

#### Observability Features
- **Execution Metrics**: Track execution counts, durations, success rates
- **Performance Monitoring**: Monitor resource usage and bottlenecks
- **Distributed Tracing**: Trace requests across module boundaries
- **Health Checks**: Service health monitoring and alerting

## Development Phases (Updated)

### Phase 0: Frontend Standardization (Week 0-1) - **PRIORITY**

#### Objectives
- Complete frontend standardization across existing services
- Establish @pipeline/proto-stubs package
- Ensure web-proxy is production-ready
- Validate standardized architecture with existing frontends

#### Deliverables
- **Proto Stubs Package**: Centralized TypeScript generation from protobuf
- **Web-Proxy Stability**: Production-ready gateway with error handling
- **Existing Frontend Migration**: All current frontends using standardized architecture
- **Shared Component Library**: Core components ready for reuse

#### Success Criteria
- All existing frontends render correctly with new architecture
- Web-proxy handles all current use cases without issues
- Proto generation pipeline is automated and reliable
- Shared components are documented and tested

### Phase 1: Linear Engine Foundation (Week 1-2)

#### Objectives
- Create linear engine service using standardized frontend architecture
- Implement core gRPC service endpoints
- Build basic linear execution engine
- Establish frontend structure following standards

#### Deliverables
- **Standardized Project Setup**: Linear engine with Quinoa + standardized frontend
- **gRPC Service**: LinearPipelineProcessorService with core methods
- **Frontend Shell**: Vue.js 3 frontend using shared components
- **Basic Execution**: Simple linear pipeline execution capability

#### Success Criteria
- Service follows all frontend standardization guidelines
- Frontend communicates through web-proxy successfully
- Basic linear pipeline can be created and executed
- Shared components integrate seamlessly

### Phase 2: Core Features (Week 2-3)

#### Objectives
- Implement streaming execution with real-time UI updates
- Build pipeline designer using shared components
- Add comprehensive validation framework
- Create development tools interface

#### Deliverables
- **Streaming Execution**: Real-time progress updates via gRPC streaming
- **Pipeline Designer**: Drag-and-drop interface using standardized components
- **Validation Framework**: Pipeline and module configuration validation
- **Testing Tools**: Single module and pipeline testing capabilities

#### Success Criteria
- Real-time streaming works smoothly in browser
- Pipeline designer provides excellent user experience
- Validation catches configuration errors effectively
- Testing tools accelerate development workflow

### Phase 3: Advanced Integration (Week 3-4)

#### Objectives
- Integrate with existing services (repository, mapping, opensearch-manager)
- Add batch processing capabilities
- Implement comprehensive monitoring and metrics
- Optimize performance for production use

#### Deliverables
- **Service Integration**: Full integration with existing microservices
- **Batch Processing**: Efficient multi-document processing
- **Monitoring Dashboard**: Execution metrics and performance monitoring
- **Production Optimization**: Performance tuning and error handling

#### Success Criteria
- Seamless integration with existing service ecosystem
- Batch processing handles large document sets efficiently
- Monitoring provides actionable insights
- Performance meets production requirements

### Phase 4: Feature Validation & Promotion (Week 4-5)

#### Objectives
- Use linear engine to test new features before network topology promotion
- Establish feature promotion workflow
- Document patterns for network topology integration
- Prepare for convergence planning

#### Deliverables
- **Feature Testing Framework**: Systematic testing of new capabilities
- **Promotion Workflow**: Process for moving features to network topology
- **Integration Patterns**: Documentation for network topology convergence
- **Convergence Roadmap**: Plan for eventual model unification

#### Success Criteria
- Linear engine successfully validates new features
- Clear process exists for promoting features to network topology
- Network topology integration patterns are established
- Roadmap for convergence is defined and agreed upon

## Technical Considerations

### 1. gRPC Streaming

#### Server-side Streaming
```java
public Multi<ExecuteLinearPipelineResponse> executeLinearPipeline(
    ExecuteLinearPipelineRequest request) {
    
    return Multi.createFrom().emitter(emitter -> {
        // Execute pipeline stages sequentially
        // Emit progress updates for each stage
        // Handle errors and cleanup
    });
}
```

#### Considerations
- **Backpressure Handling**: Manage high-volume streams without overwhelming clients
- **Connection Management**: Handle client disconnections gracefully
- **Error Propagation**: Proper error handling in streaming context
- **Resource Cleanup**: Ensure resources are cleaned up when streams end

### 2. Frontend-Backend Communication

#### gRPC-Web Configuration
```javascript
// grpcClient.js - gRPC-Web client setup
import { LinearPipelineProcessorClient } from './generated/linear_pipeline_processor_grpc_web_pb'

export const createLinearPipelineClient = () => {
  return new LinearPipelineProcessorClient(
    process.env.VUE_APP_GRPC_ENDPOINT || 'http://localhost:8080',
    null,
    null
  )
}
```

#### Real-time Updates
- **Reactive Streams**: Use reactive patterns for real-time updates
- **WebSocket Fallback**: Fallback to WebSockets if gRPC-Web has issues
- **Optimistic Updates**: Update UI optimistically for better user experience
- **Connection Recovery**: Automatic reconnection on connection loss

### 3. Performance Optimization

#### Backend Optimization
- **Async Processing**: Non-blocking operations throughout the pipeline
- **Connection Pooling**: Reuse connections to modules for better performance
- **Caching**: Cache frequently accessed data (module metadata, configurations)
- **Resource Management**: Proper resource cleanup and memory management

#### Frontend Optimization
- **Virtual Scrolling**: Handle large lists of pipelines/executions efficiently
- **Lazy Loading**: Load components and data on demand
- **Debouncing**: Debounce user inputs to reduce API calls
- **Caching**: Cache API responses and computed values

## Unique Value Propositions

### 1. Simplified Linear Processing
- **Focus on Sequential Pipelines**: Easier to understand and debug than complex topologies
- **Reduced Complexity**: Eliminates branching and merging complexities
- **Faster Development**: Quicker to create and test linear workflows
- **Better Debugging**: Easier to trace execution and identify issues

### 2. Real-time Development Experience
- **Immediate Feedback**: Real-time validation and execution progress
- **Interactive Design**: Visual pipeline creation with drag-and-drop
- **Live Testing**: Test pipelines as you build them
- **Instant Validation**: Catch errors before execution

### 3. Integrated Designer and Tools
- **Single Interface**: Design, test, and monitor in one application
- **Shared Components**: Consistent UI components across all tools
- **Seamless Workflow**: Smooth transition from design to testing to production
- **Developer-Focused**: Built specifically for pipeline developers

### 4. Module Testing Sandbox
- **Individual Module Testing**: Test modules in isolation
- **Quick Feedback Loop**: Rapid testing and iteration
- **Configuration Validation**: Validate module configurations before use
- **Performance Testing**: Test module performance under various conditions

### 5. Modern Technology Stack
- **Vue.js 3**: Modern, reactive frontend framework
- **gRPC Streaming**: Efficient, real-time communication
- **Quarkus**: Fast startup and low memory footprint
- **TypeScript**: Type safety and better development experience

## Future Enhancements

### Short-term (Next 3 months)
- **Pipeline Templates**: Pre-built pipeline templates for common use cases
- **Advanced Monitoring**: More detailed performance and error analytics
- **Module Marketplace**: Discover and install community modules
- **Export/Import**: Pipeline export/import for sharing and backup

### Medium-term (Next 6 months)
- **Visual Debugging**: Step-through debugging with visual execution flow
- **A/B Testing**: Built-in A/B testing for pipeline optimization
- **Auto-scaling**: Automatic scaling based on workload
- **Integration Testing**: Automated testing of pipeline integrations

### Long-term (Next year)
- **Machine Learning**: ML-powered pipeline optimization suggestions
- **Multi-tenant**: Support for multiple organizations/teams
- **Cloud Integration**: Native cloud provider integrations
- **Advanced Analytics**: Predictive analytics for pipeline performance

## Strategic Convergence Plan

### Current State: Dual-Track Development

#### Linear Engine (This Service)
- **Purpose**: Rapid feature development and testing sandbox
- **Architecture**: Sequential pipeline processing
- **Models**: Independent linear-specific models
- **Advantages**: Simpler, faster development, easier debugging

#### Network Topology Engine (Existing)
- **Purpose**: Production-grade complex pipeline processing
- **Architecture**: Graph-based pipeline processing with branching/merging
- **Models**: Complex network topology models
- **Advantages**: Full production capabilities, handles complex workflows

### Convergence Strategy

#### Phase 1: Independent Development (Current)
- Linear engine develops independently with its own models
- Features are tested and validated in linear context
- Network topology engine continues with existing architecture
- **Timeline**: Next 6 months

#### Phase 2: Feature Promotion (6-12 months)
- Proven features from linear engine are adapted for network topology
- Shared component library grows to support both engines
- Common patterns emerge for model translation
- **Key Milestone**: First major feature successfully promoted

#### Phase 3: Model Harmonization (12-18 months)
- Begin aligning models between both engines
- Introduce streaming capabilities to network topology
- Shared validation and execution patterns
- **Key Milestone**: 80% model compatibility achieved

#### Phase 4: Unified Architecture (18+ months)
- Both engines use the same underlying models
- Linear engine becomes a "streaming network topology" with simplified UI
- Network topology gains streaming capabilities from linear engine
- **Key Milestone**: Single codebase with dual interfaces

### Technical Convergence Approach

#### Shared Models Evolution
```protobuf
// Future unified model supporting both linear and network topologies
message UnifiedPipeline {
  string pipeline_id = 1;
  string name = 2;
  
  // Linear mode: stages processed sequentially
  repeated PipelineStage linear_stages = 3;
  
  // Network mode: complex graph topology
  repeated GraphNode network_nodes = 4;
  repeated GraphEdge network_edges = 5;
  
  // Execution mode determines which fields are used
  ExecutionMode mode = 6;
}

enum ExecutionMode {
  EXECUTION_MODE_UNSPECIFIED = 0;
  EXECUTION_MODE_LINEAR = 1;      // Use linear_stages
  EXECUTION_MODE_NETWORK = 2;     // Use network_nodes/edges
  EXECUTION_MODE_STREAMING = 3;   // Streaming network topology
}
```

#### Streaming Network Topology
```java
// Future: Network topology with streaming capabilities
@ApplicationScoped
public class StreamingNetworkExecutor {
    // Combines network topology complexity with linear engine streaming
    public Multi<NetworkExecutionResponse> executeStreamingNetwork(
        UnifiedPipeline pipeline) {
        
        if (pipeline.getMode() == EXECUTION_MODE_LINEAR) {
            return executeLinearStreaming(pipeline.getLinearStagesList());
        } else {
            return executeNetworkStreaming(
                pipeline.getNetworkNodesList(), 
                pipeline.getNetworkEdgesList()
            );
        }
    }
}
```

### Benefits of This Approach

#### 1. **Risk Mitigation**
- New features tested thoroughly in simpler linear context
- Network topology remains stable during feature development
- Rollback capability if linear features don't translate well

#### 2. **Accelerated Innovation**
- Linear engine's simplicity enables faster feature development
- Immediate feedback loop for new capabilities
- Reduced complexity during experimentation phase

#### 3. **User Experience Validation**
- UI/UX patterns validated in linear context first
- Shared component library ensures consistency
- User feedback incorporated before network topology integration

#### 4. **Technical Learning**
- Streaming patterns developed and refined in linear engine
- Performance optimizations discovered and validated
- Integration patterns established and documented

### Migration Strategy for Existing Users

#### Linear Engine Users
- **Immediate**: Full linear pipeline capabilities
- **6 months**: Enhanced features from network topology learnings
- **12 months**: Option to upgrade pipelines to network topology
- **18+ months**: Seamless transition to unified interface

#### Network Topology Users
- **Immediate**: Continued full functionality
- **6 months**: New features promoted from linear engine
- **12 months**: Streaming capabilities added
- **18+ months**: Enhanced interface with linear engine learnings

### Success Metrics

#### Short-term (6 months)
- [ ] 3+ major features developed and tested in linear engine
- [ ] 90%+ user satisfaction with linear engine interface
- [ ] 50%+ reduction in feature development time vs network topology

#### Medium-term (12 months)
- [ ] 2+ features successfully promoted to network topology
- [ ] Shared component library used by both engines
- [ ] Performance parity between engines for equivalent workloads

#### Long-term (18+ months)
- [ ] Unified model supports both execution modes
- [ ] Single codebase with dual interfaces
- [ ] Streaming network topology capabilities fully functional
- [ ] Migration path for all existing users defined and tested
