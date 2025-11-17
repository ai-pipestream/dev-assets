## 23. Implement `ServiceHealthManager` for Proactive Health Checks

**Goal:** Implement a `ServiceHealthManager` that can proactively check the health of registered modules and update their status in Consul, preventing the engine from sending requests to unhealthy services.

### Ticket 23.1: Create the `ServiceHealthManager`

**Title:** Feature: Implement the `ServiceHealthManager` for proactive health checks

**Description:**
Create a new `@ApplicationScoped` bean called `ServiceHealthManager` that periodically checks the health of all registered modules.

**Tasks:**
1.  The `ServiceHealthManager` should use a scheduled executor to periodically iterate through all registered services.
2.  For each service, it should call the `GetServiceRegistration` RPC with a `health_check_requested` flag set to `true`.
3.  Based on the `health_check_passed` field in the response, the manager should update the service's health status in Consul.

### Ticket 23.2: Integrate `ServiceHealthManager` with the Engine

**Title:** Feature: Integrate the `ServiceHealthManager` with the `pipestream-engine`

**Description:**
The `pipestream-engine` should use the health information from the `ServiceHealthManager` to avoid sending requests to unhealthy services.

**Tasks:**
1.  The `ConsulModuleRegistryService` should be updated to expose the health status of each service.
2.  The `PipeStreamEngineImpl` should check the health status of a service before sending a request to it.
3.  If a service is unhealthy, the engine should either reroute the request to a healthy instance or fail the request with an appropriate error message.
