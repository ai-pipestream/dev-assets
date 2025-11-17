## 26. Implement `PipelineVersionManager` for Blue-Green Deployments

**Goal:** Implement a `PipelineVersionManager` that can manage multiple versions of a pipeline, enabling blue-green deployments and A/B testing.

### Ticket 26.1: Create the `PipelineVersionManager`

**Title:** Feature: Implement a `PipelineVersionManager` for blue-green deployments

**Description:**
Create a new `@ApplicationScoped` bean called `PipelineVersionManager` that is responsible for managing pipeline versions.

**Tasks:**
1.  The `PipelineVersionManager` should be able to store and retrieve multiple versions of a pipeline configuration.
2.  It should provide methods for activating a specific version of a pipeline, which will make it the "live" version.
3.  It should also support routing a percentage of traffic to a new version for A/B testing.

### Ticket 26.2: Integrate `PipelineVersionManager` with the Engine

**Title:** Feature: Integrate the `PipelineVersionManager` with the `pipestream-engine`

**Description:**
The `pipestream-engine` should use the `PipelineVersionManager` to determine which version of a pipeline to execute.

**Tasks:**
1.  When a request comes in, the `PipeStreamEngineImpl` should consult the `PipelineVersionManager` to get the appropriate version of the pipeline configuration.
2.  The engine should then execute the pipeline using that configuration.
3.  The `PipelineVersionManager` should be able to route traffic based on various criteria, such as headers, cookies, or a random percentage.
