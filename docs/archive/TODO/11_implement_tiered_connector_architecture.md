## 11. Implement Tiered Connector Architecture

**Goal:** Implement the tiered connector architecture based on the existing protobuf definitions.

### Ticket 11.1: Implement Tier 1 Connector Registration

**Title:** Feature: Implement registration for Tier 1 connectors

**Description:**
Implement the server-side logic for the `RegisterConnector` RPC defined in `pipeline_connector_server.proto`. This will allow trusted, client-managed connectors to register with the system.

**Tasks:**
1.  Create a new service, `ConnectorCoordinatorService`, that implements the `ConnectorCoordinator` gRPC service.
2.  Implement the `registerConnector` method to handle `RegisterConnectorRequest` messages.
3.  The implementation should:
    *   Validate the request.
    *   Store the connector's information (type, endpoint, capabilities, configuration) in a persistent data store (e.g., a database or Consul).
    *   Generate a unique `connector_id` and return it in the `RegisterConnectorResponse`.
4.  Add authentication and authorization to the `registerConnector` method to ensure that only trusted clients can register new connectors.

### Ticket 11.2: Implement Tier 2 Connector Polling

**Title:** Feature: Implement polling for Tier 2 connectors

**Description:**
Implement the logic to periodically poll Tier 2 connectors for data. This will involve using the `TriggerSync` RPC and handling the data that is returned.

**Tasks:**
1.  Create a new service, `ConnectorPollingService`, that is responsible for scheduling and triggering sync operations.
2.  This service should periodically call the `TriggerSync` RPC on registered Tier 2 connectors.
3.  The `ConnectorPollingService` should be able to handle both full and incremental syncs, based on the connector's capabilities.
4.  Implement the logic to process the data that is returned from the sync operation, including handling errors and retries.
