## 27. Implement `PipelineAnalyticsService` for Performance Monitoring

**Goal:** Implement a `PipelineAnalyticsService` that can collect and analyze performance data for pipelines, providing insights into bottlenecks and areas for optimization.

### Ticket 27.1: Create the `PipelineAnalyticsService`

**Title:** Feature: Implement a `PipelineAnalyticsService` for performance monitoring

**Description:**
Create a new `@ApplicationScoped` bean called `PipelineAnalyticsService` that is responsible for collecting and analyzing pipeline performance data.

**Tasks:**
1.  The `PipelineAnalyticsService` should collect data on:
    *   The time spent in each step of a pipeline.
    *   The number of messages processed by each step.
    *   The number of errors and retries in each step.
2.  This data should be stored in a time-series database, such as Prometheus or InfluxDB.

### Ticket 27.2: Integrate `PipelineAnalyticsService` with the Engine

**Title:** Feature: Integrate the `PipelineAnalyticsService` with the `pipestream-engine`

**Description:**
The `pipestream-engine` should use the `PipelineAnalyticsService` to record performance data for each step of a pipeline.

**Tasks:**
1.  In the `PipeStreamEngineImpl`, after each step is executed, record the performance data using the `PipelineAnalyticsService`.
2.  Add a new REST endpoint, `GET /api/v1/pipelines/{pipelineId}/analytics`, that returns a summary of the performance data for a pipeline.
3.  Create a Grafana dashboard to visualize the performance data.
