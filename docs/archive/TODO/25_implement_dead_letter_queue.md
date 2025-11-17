## 25. Implement `DeadLetterQueue` for Failed Messages

**Goal:** Implement a dead-letter queue (DLQ) mechanism to handle messages that fail processing after multiple retries.

### Ticket 25.1: Create a `DeadLetterQueueService`

**Title:** Feature: Implement a `DeadLetterQueueService` to handle failed messages

**Description:**
Create a new `@ApplicationScoped` bean called `DeadLetterQueueService` that is responsible for sending failed messages to a DLQ.

**Tasks:**
1.  The `DeadLetterQueueService` should provide a method, `sendToDlq(PipeStream)`, that sends a failed `PipeStream` to a configured DLQ.
2.  The DLQ can be implemented using a Kafka topic, a database table, or a file-based queue.
3.  The service should enrich the message with metadata about the failure, such as the error message, stack trace, and the number of retries.

### Ticket 25.2: Integrate DLQ with the Pipestream Engine

**Title:** Feature: Integrate the `DeadLetterQueueService` with the `pipestream-engine`

**Description:**
The `pipestream-engine` should use the `DeadLetterQueueService` to handle messages that have exhausted their retry attempts.

**Tasks:**
1.  In the `PipeStreamEngineImpl`, after a message has failed processing and all retries have been attempted, call the `DeadLetterQueueService.sendToDlq()` method.
2.  Add configuration options to enable or disable the DLQ on a per-pipeline or per-step basis.
