## 24. Implement `PipelineLifecycleManager` for Graceful Shutdown

**Goal:** Implement a `PipelineLifecycleManager` that can gracefully shut down all active pipelines, ensuring that all in-flight data is persisted before the application exits.

### Ticket 24.1: Create the `PipelineLifecycleManager`

**Title:** Feature: Implement the `PipelineLifecycleManager` for graceful shutdown

**Description:**
Create a new `@ApplicationScoped` bean called `PipelineLifecycleManager` that is responsible for managing the lifecycle of pipelines.

**Tasks:**
1.  The `PipelineLifecycleManager` should listen for the Quarkus `ShutdownEvent`.
2.  When a shutdown is initiated, the manager should:
    *   Stop all connector polling.
    *   Wait for all in-flight gRPC requests to complete.
    *   Persist all `ProcessingBuffer` instances to disk.
    *   Deregister the service from Consul.

### Ticket 24.2: Integrate `PipelineLifecycleManager` with Connectors

**Title:** Feature: Integrate the `PipelineLifecycleManager` with connector polling

**Description:**
The `ConnectorPollingService` should be integrated with the `PipelineLifecycleManager` to allow for graceful shutdown.

**Tasks:**
1.  The `ConnectorPollingService` should be updated to be stoppable.
2.  When the `PipelineLifecycleManager` initiates a shutdown, it should call a `stop()` method on the `ConnectorPollingService`.
3.  The `stop()` method should prevent any new polling operations from starting and wait for any in-progress operations to complete.
