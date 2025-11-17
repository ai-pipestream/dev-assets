# Fan-Out to Fan-In Join Strategy: Research Note

## Overview

This document explores the feasibility and design considerations for implementing a "fan-out to fan-in" join strategy in the Pipestream Platform pipeline engine. This would allow parallel processing branches to converge and merge results before proceeding to the next processing stage.

## Current State

### What Works Today

- **Fan-out**: The engine can route a single document to multiple processing steps in parallel
  - Example: Route one document to multiple chunkers with different strategies
  - Example: Route chunked document to multiple embedders for A/B testing
- **Independent Processing**: Each branch processes independently and routes to its own next step(s)

### What's Missing

- **Fan-in/Join**: No mechanism to wait for multiple parallel branches to complete and merge their results
- **Sequential Fan-out**: Currently, if you want to do "double chunking then double embedding", you must:
  1. Do first chunking strategy sequentially
  2. Then do second chunking strategy sequentially  
  3. Then do embeddings sequentially

## Proposed Enhancement

### Use Case

Enable patterns like:
- **Parallel Chunking → Join → Parallel Embedding**
  - Fan-out: Document goes to Chunker-A (512 chars) and Chunker-B (1024 chars) simultaneously
  - Fan-in: Both chunking results merge into single PipeDoc with multiple `SemanticProcessingResult` entries
  - Fan-out: Merged document goes to Embedder-A and Embedder-B simultaneously
  - Result: Document has chunks from both strategies, each with embeddings from both models

### Design Considerations

#### 1. State Tracking

The engine would need to track:
- Which branches are in-flight for a given `stream_id`
- Expected completion count (how many branches to wait for)
- Completion status of each branch
- Timeout handling for branches that don't complete

#### 2. Result Merging Strategy

When all branches complete, merge multiple PipeDocs:
- **Append Strategy**: Add all `SemanticProcessingResult` entries to the merged PipeDoc
- **Metadata Merging**: Combine metadata maps intelligently
- **Conflict Resolution**: Handle cases where multiple branches modify the same field

#### 3. Timeout and Error Handling

- What happens if one branch fails?
- What happens if one branch times out?
- Options:
  - Fail entire join (strict)
  - Continue with partial results (lenient)
  - Retry failed branches
  - Route to error handler

#### 4. gRPC Considerations

- Each branch returns independently via gRPC request/response
- Engine must:
  - Track pending branches per `stream_id`
  - Collect responses asynchronously as they arrive
  - Detect when all expected responses are received
  - Merge results and route merged PipeDoc to next step

#### 5. Configuration

Join step configuration would specify:
```json
{
  "stepName": "join-after-chunking",
  "stepType": "JOIN",
  "joinConfig": {
    "waitForSteps": ["chunker-512", "chunker-1024"],
    "mergeStrategy": "append_semantic_results",
    "timeoutMs": 30000,
    "failureMode": "partial" // or "strict"
  }
}
```

## Similarity to Existing Patterns

This pattern is similar to the **S3 streaming chunk assembly** strategy:
- Multiple chunks arrive asynchronously
- System tracks which chunks are received
- When all chunks complete, assembles final document
- Engine would act as the "assembler" for parallel processing results

## Implementation Complexity

### Medium Complexity

- Requires state management in engine
- Requires merge logic for PipeDoc structures
- Requires timeout and error handling
- But leverages existing gRPC infrastructure

### Challenges

- **State Management**: Engine must maintain join state across async operations
- **Merge Logic**: Need robust merging of complex nested structures (SemanticProcessingResult, metadata maps)
- **Debugging**: More complex to trace execution through join points
- **Performance**: Join points add latency (must wait for slowest branch)

## Decision

**Status**: Not currently planned for implementation

**Rationale**: 
- Current sequential approach is sufficient for most use cases
- Adds significant complexity to engine
- Can achieve similar results with careful pipeline design
- May be reconsidered if strong use cases emerge

## Future Considerations

If this feature is needed in the future:
1. Start with simple append strategy for `SemanticProcessingResult`
2. Add join step type to pipeline configuration
3. Implement state tracking in engine
4. Add merge logic for PipeDoc structures
5. Implement timeout and error handling
6. Add observability for join operations

## Related Concepts

- **S3 Streaming Chunk Assembly**: Similar pattern of collecting async results
- **Kafka Consumer Groups**: Similar concept of waiting for multiple messages
- **Map-Reduce**: Similar pattern of parallel processing with aggregation

