# Architectural Patterns for Document-Level Security (DLS) in OpenSearch

## 1. Introduction

This document outlines architectural patterns for implementing robust Document-Level Security (DLS) in OpenSearch, particularly when Access Control Lists (ACLs) are managed in external systems (e.g., Active Directory, Confluence, Salesforce). The goal is to ensure users, whether accessing data via an API or directly through OpenSearch Dashboards, can only see the specific documents they are authorized to view.

### Core Principles

- **Server-Side Enforcement:** Security filtering should be applied automatically on the server side to be robust and prevent bypass by a client.
- **Defense in Depth:** The most secure models apply filtering at the data layer (within OpenSearch) and may combine multiple layers of permissions (e.g., index-level and document-level).
- **Transport Layer Security:** All communication between components (user-to-application, application-to-OpenSearch) must be encrypted with TLS/HTTPS to prevent Man-in-the-Middle (MITM) attacks.

## 2. Foundational Security Models

There are three foundational models for handling DLS. The choice of model determines where the security logic lives and how user identity is handled.

| Model | How it Works | Where Logic Lives | Is OpenSearch Aware of the End-User? | Primary Risk |
| :--- | :--- | :--- | :--- | :--- |
| **1. Application-Side Filtering (Proxy Model)** | The application receives a user query, modifies it to add a security filter, and sends the modified query to OpenSearch. | **Application Code** | **No.** OpenSearch only sees the application's service account. | **Insecure Application.** A bug in the application's query-building logic can break security and leak data. |
| **2. Data-Layer Enforcement (Security Plugin)** | The application authenticates the user and then tells OpenSearch to **impersonate** them. The OpenSearch Security Plugin (FGAC) applies a pre-configured DLS rule. | **OpenSearch Configuration** | **Yes.** The user's identity is passed via an impersonation header. | **Misconfiguration.** An incorrect DLS rule or role mapping in OpenSearch could lead to improper access. |
| **3. Identity Enrichment (Token Hook)** | This is a **helper pattern**, not a standalone enforcement model. An Identity Provider (e.g., Okta) calls an external service at login time to add extra permission claims to a user's token (JWT). | **External Hook Service** | N/A (Depends on which enforcement model uses the token) | **Session Staleness.** Permissions are only as fresh as the user's token. |

---

## 3. The Scalability Challenge: User vs. Group-Based ACLs

A naive DLS implementation involves storing a list of individual user IDs on every document (e.g., `allowed_users: ["user_a", "user_b", ...]`). This approach does not scale due to:

1.  **Field Bloat:** Storing thousands of user IDs on a single document is inefficient.
2.  **Update Amplification:** If a user is added to a group that has access to 1 million documents, all 1 million documents would need to be updated.

**Solution: Group-Based ACLs**

The correct, scalable approach is to use group-based permissions.

- **In OpenSearch:** Documents are indexed with a list of group IDs that can access them (e.g., `allowed_groups: ["group_eng", "group_alpha"]`).
- **In the User Token:** The user's token (from Okta/AD) contains the list of groups they belong to.
- **The DLS Rule:** The Security Plugin is configured with a DLS rule that compares these two lists: `{"terms": {"allowed_groups": "${user.claims.groups}"}}`.

This model is highly efficient. When a user's group membership changes in Active Directory, no documents in OpenSearch need to be updated. The change is automatically picked up when the user gets a new token.

---

## 4. Handling Externally-Managed ACLs

When ACLs are not in a central directory like AD/Okta (e.g., they live in Confluence), a process is needed to hydrate these permissions.

### Pattern A: Token Enrichment at Login (The Inline Hook Pattern)

This is the ideal use case for the Okta Token Inline Hook.

- **How:** At login, an Okta hook calls a custom service. This service makes a real-time API call to the external system (Confluence) to get the user's application-specific roles. These roles are then added as a new claim to the JWT.
- **Pros:** The expensive lookup happens only once at login. Search performance is excellent.
- **Cons:** **Session Staleness.** Permissions are only as fresh as the token. A permission change in Confluence is not reflected until the user's next login.

### Pattern B: Event-Driven ACL Synchronization (The Kafka Pattern)

This is the most robust pattern for keeping permissions fresh.

- **How:** The external system (Confluence, Salesforce) publishes all ACL changes to a Kafka topic. A dedicated consumer service listens to this stream and makes near real-time updates to the `allowed_groups` field on the corresponding documents in OpenSearch.
- **Pros:** **Near Real-Time Freshness** (seconds). Search performance is the best possible, as the check is against an indexed field.
- **Cons:** Higher implementation complexity (requires a Kafka pipeline and consumer service).

---

## 5. Recommended Architecture: The Gold Standard

For a system that requires high security, scalability, and near real-time permission updates, the recommended architecture combines these patterns:

1.  **Identity Provider:** **Okta**, synced with Active Directory as the primary source of truth for users and core groups.
2.  **Authentication:** Users log in to **OpenSearch Dashboards** via **SAML/OIDC**, using their Okta credentials.
3.  **Enforcement:** The **OpenSearch Security Plugin (FGAC)** is used for all authorization. It maps Okta users/groups to internal OpenSearch roles. These roles define both:
    - **Index-level permissions** (which indices a user can see).
    - **Document-level security (DLS)** rules.
4.  **ACL Hydration (Two-Pronged Approach):**
    - **Primary Method (Kafka):** An **event-driven pipeline using Kafka** streams ACL changes from external systems (Confluence, etc.) into an `allowed_groups` field on the OpenSearch documents. This is the preferred method for freshness and performance.
    - **Secondary Method (Token Hook):** For any remaining real-time, user-specific permissions that cannot be modeled via the Kafka sync, an **Okta Token Inline Hook** is used to add extra claims to the user's token at login.
5.  **The DLS Rule:** The DLS query in FGAC is configured to check against all available permission data:
    ```json
    {
      "bool": {
        "should": [
          { "terms": { "allowed_groups": "${user.claims.groups}" } },
          { "terms": { "allowed_groups": "${user.claims.confluence_roles}" } }
        ],
        "minimum_should_match": 1
      }
    }
    ```

This architecture is secure, scalable, and provides a seamless experience for end-users, ensuring they can only ever see the data they are explicitly authorized to view.

---
## Appendix: Technical FAQ

- **Is Amazon FGAC the same as the Security Plugin?** Yes. FGAC is AWS's managed offering of the official OpenSearch Security Plugin. All concepts (DLS, roles, impersonation) are the same.
- **Can OpenSearch do a real-time external lookup at query time?** No. This is intentionally not supported due to severe performance and stability risks. The ACL data must be present in either the user's token or the document itself *before* the query begins.
- **Should `post_filter` be used for security?** No. `post_filter` applies after aggregations are calculated, which can lead to information leakage. Security filtering must be done in a `bool` query's `filter` clause to ensure all results, including aggregations, are correctly trimmed.