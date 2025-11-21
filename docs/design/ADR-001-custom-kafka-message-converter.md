# ADR-001: Custom Kafka MessageConverter for Consumers

**Status:** Proposed

**Context:**

The current platform standard for consuming Kafka messages is to use a method signature that explicitly accepts the entire Kafka record, like `consume(ConsumerRecord<UUID, MyEvent> record)`. This pattern is robust and correctly enforces the platform's standard of using UUID keys and specific Protobuf event types.

However, it requires developers to be aware of the Kafka client library's `ConsumerRecord` wrapper and to manually extract the payload (`record.value()`) in their business logic. This adds a small amount of boilerplate and presents a signature that is more complex than necessary for the simple case of processing an event payload.

**Decision:**

We propose the creation of a custom `io.smallrye.reactive.messaging.MessageConverter` to simplify the consumer signature. This would allow developers to write consumer methods that directly accept the Protobuf event payload, abstracting away the Kafka-specific wrapper.

The desired developer experience would be:
```java
@Incoming("my-channel")
public Uni<Void> consume(MyEvent event) {
    // Business logic focused purely on the event payload.
    // The ConsumerRecord wrapper is handled automatically.
}
```

**Implementation Details:**

This would be implemented as a new class, `PipestreamEventConverter`, within the `pipeline-commons` library.

1.  **High Priority:** The converter would be registered with a high priority (`@Priority(Priorities.APPLICATION)`) to ensure it is evaluated before the default converters provided by Quarkus.
2.  **Conversion Logic:**
    - The `canConvert` method will inspect the incoming message. It will return `true` if the message payload is a `ConsumerRecord` where the key is a `UUID` and the value is a Protobuf `Message`, and if the target `@Incoming` method parameter is of the same type as the record's value.
    - The `convert` method will perform the transformation, extracting the payload from the `ConsumerRecord` and passing it on.
3.  **Enhanced Traceability:** As part of the conversion, the converter can automatically log the `UUID` key from the record, providing consistent traceability for all incoming events without requiring developers to add this logging to every consumer.

**Consequences:**

*   **Positive:**
    -   **Simplified DX:** Consumer method signatures become much cleaner and more focused on business logic.
    -   **More Robust Standard:** Creates an even stronger, "branded" contract for consumers, making it more intuitive for new developers and LLM-based tools.
    -   **Centralized Boilerplate:** Logic for handling the `ConsumerRecord` is centralized, ensuring consistency.

*   **Neutral:**
    -   **Abstraction Layer:** This introduces a new layer of "magic" specific to the platform. Developers will need to be aware that this converter exists and is processing messages behind the scenes. The explicitness of the `ConsumerRecord` is lost.

**Initial Implementation Reference (`platform-libraries` Issue):**
- See [ai-pipestream/platform-libraries#39](https://github.com/ai-pipestream/platform-libraries/issues/39)

This ADR captures the aspiration for a future enhancement. The current, documented standard remains the use of the `ConsumerRecord<UUID, T>` signature.
