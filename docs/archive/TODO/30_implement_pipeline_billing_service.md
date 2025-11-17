## 30. Implement `PipelineBillingService` for Usage-Based Billing

**Goal:** Implement a `PipelineBillingService` that can track pipeline usage and generate billing reports.

### Ticket 30.1: Create the `PipelineBillingService`

**Title:** Feature: Implement a `PipelineBillingService` for usage-based billing

**Description:**
Create a new `@ApplicationScoped` bean called `PipelineBillingService` that is responsible for tracking pipeline usage.

**Tasks:**
1.  The `PipelineBillingService` should track usage based on:
    *   The number of messages processed.
    *   The amount of data processed.
    *   The CPU and memory resources consumed.
2.  This data should be stored in a billing database.

### Ticket 30.2: Integrate `PipelineBillingService` with the Engine

**Title:** Feature: Integrate the `PipelineBillingService` with the `pipestream-engine`

**Description:**
The `pipestream-engine` should use the `PipelineBillingService` to record usage data for each pipeline.

**Tasks:**
1.  In the `PipeStreamEngineImpl`, after each step is executed, record the usage data using the `PipelineBillingService`.
2.  Add a new REST endpoint, `GET /api/v1/billing/reports`, that generates billing reports for a given time period.
3.  Integrate with a payment gateway, such as Stripe or Braintree, to process payments.
