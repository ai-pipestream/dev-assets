## 29. Implement `PipelineSecurityService` for Fine-Grained Access Control

**Goal:** Implement a `PipelineSecurityService` that provides fine-grained access control for pipelines and modules.

### Ticket 29.1: Create the `PipelineSecurityService`

**Title:** Feature: Implement a `PipelineSecurityService` for fine-grained access control

**Description:**
Create a new `@ApplicationScoped` bean called `PipelineSecurityService` that is responsible for enforcing access control policies.

**Tasks:**
1.  The `PipelineSecurityService` should be able to define policies that control who can:
    *   Create, read, update, and delete pipelines.
    *   Execute pipelines.
    *   Register and use modules.
2.  Policies should be based on user roles and permissions.
3.  The service should integrate with an existing identity provider, such as Keycloak or LDAP.

### Ticket 29.2: Integrate `PipelineSecurityService` with the API

**Title:** Feature: Integrate the `PipelineSecurityService` with the REST API

**Description:**
The REST API should use the `PipelineSecurityService` to enforce access control policies.

**Tasks:**
1.  Add security annotations to the REST endpoints to specify the required permissions.
2.  The `PipelineSecurityService` should be used to check if the current user has the required permissions before allowing access to an endpoint.
3.  If the user does not have the required permissions, the API should return a `403 Forbidden` error.
