## 2. Implement Fan-Out with Kafka

**Goal:** Introduce an asynchronous, message-based communication channel using Kafka to enable fan-out scenarios and improve pipeline scalability and resilience.

### Ticket 2.1: Implement Dynamic Kafka Listeners

**Title:** Feature: Implement dynamic Kafka topic listeners

**Description:**
To support dynamic pipelines where topics can be created, destroyed, and repartitioned at runtime, a dynamic Kafka listener management system is required. This system will replace the need for static `@Incoming` annotations and allow the application to adapt to changing topic configurations.

**Tasks:**
1.  Design and implement a service that can start and stop Kafka consumers on demand.
2.  This service should be able to monitor for new topics (perhaps via a naming convention or a configuration source) and automatically create consumers for them.
3.  The service should also handle rebalancing and gracefully shut down consumers for topics that are no longer needed.
4.  Integrate this dynamic listener service with the `pipestream-engine` to manage the lifecycle of consumers based on the deployed pipeline configurations.

### Ticket 2.2: Update Pipestream Engine to Support Kafka Outputs

**Title:** Feature: Add Kafka producer support to the Pipestream Engine

**Description:**
The `PipeStreamEngineImpl` needs to be updated to handle steps that output to a Kafka topic instead of (or in addition to) a gRPC service.

**Tasks:**
1.  In `PipeStreamEngineImpl`, when a step's output is of type `KAFKA`, use a Kafka producer to send the data to the specified topic.
2.  The engine should be able to handle multiple output types for a single step (e.g., one gRPC output and one Kafka output). This will likely require changes to the `PipelineStepConfig` model to allow a list of outputs.
3.  Ensure that the engine can gracefully handle Kafka connection errors and retries.

### Ticket 2.3: Add Kafka to Local Development Environment

**Title:** Chore: Add Kafka and Zookeeper to the Docker Compose setup

**Description:**
To support local development and testing of the new Kafka-based features, the project's `docker-compose.yml` file needs to be updated to include Kafka and Zookeeper services.

**Tasks:**
1.  Add a Zookeeper service to the `docker-compose.yml` file.
2.  Add a Kafka broker service that depends on the Zookeeper service.
3.  Configure the Kafka service with appropriate ports and environment variables for a single-broker setup.
4.  Update the project's documentation to explain how to run Kafka locally.
