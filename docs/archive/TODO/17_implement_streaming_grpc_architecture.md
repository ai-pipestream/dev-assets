## 17. Implement Streaming gRPC Architecture for Large Document Processing

**Goal:** Replace unary gRPC calls with streaming interfaces to handle large documents efficiently and eliminate message size limitations.

### Background
Current architecture sends entire documents (potentially 3,202+ chunks) as single gRPC messages, causing:
- `RESOURCE_EXHAUSTED: gRPC message exceeds maximum size 4194304` errors
- Memory pressure and timeout issues
- Blocking operations that don't leverage Quarkus reactive capabilities

### Design Decision: Always Streaming Architecture

**Strategy:** Implement streaming alongside existing unary interfaces for backward compatibility and gradual migration.

#### Core Principles:
1. **Always Stream** - No thresholds, no conditional logic
2. **Natural Backpressure** - Let Mutiny handle reactive flow control
3. **Engine-Controlled** - Engine orchestrates streaming, modules focus on domain logic
4. **Backward Compatible** - Keep existing unary interfaces alongside new streaming

#### Architecture Flow:
```
Engine → ALWAYS uses streaming interface → Module
       → [chunk batch 1] → [results 1]
       → [chunk batch 2] → [results 2]  
       → [chunk batch N] → [results N]
       → Reassembles final result
```

#### Implementation Plan:

### Ticket 17.1: Enhance Proto Interface Usage

**Title:** Implement streaming gRPC methods alongside existing unary methods

**Description:**
The proto interface already supports both unary (`processData`) and streaming (`processDataStream`) methods. Implement the streaming variants in all modules while keeping existing implementations.

**Tasks:**
1. **Module Implementation**: Implement `processDataStream()` in all modules (embedder, chunker, parser, etc.)
2. **Streaming Logic**: `Multi<Chunk> → Multi<Result>` reactive processing
3. **Preserve Ordering**: Ensure chunk-to-result mapping maintains document integrity
4. **Error Handling**: Graceful failure handling in streaming context

### Ticket 17.2: Engine Streaming Orchestration

**Title:** Add streaming support to PipeStreamEngine with dual-mode operation

**Description:**
Enhance the engine to support both unary and streaming gRPC calls with configuration-controlled selection.

**Tasks:**
1. **Dual Interface Support**: Engine can call either unary or streaming methods
2. **Batching Strategy**: Engine controls chunk batch sizes for optimal performance
3. **Configuration**: Feature flags to control streaming vs unary per module type
4. **Result Reassembly**: Collect streaming results back into final document format

### Ticket 17.3: Performance Testing and Migration

**Title:** A/B test streaming vs unary performance and implement gradual migration

**Description:**
Compare performance characteristics and implement safe migration path.

**Tasks:**
1. **Benchmark Testing**: Compare streaming vs unary with large documents (1000+ chunks)
2. **Memory Profiling**: Measure memory usage improvements
3. **Configuration Migration**: Gradual rollout strategy with rollback capability
4. **Documentation**: Update integration guides for streaming architecture

### Benefits:
- **Eliminates message size errors** - No more 4MB/2GB limits needed
- **Better memory utilization** - Process chunks as they arrive
- **Natural backpressure** - Reactive streams handle flow control
- **Quarkus-aligned** - Leverages Mutiny reactive programming fully
- **Scalable** - Handles documents of any size gracefully
