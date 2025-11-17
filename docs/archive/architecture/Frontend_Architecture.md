# Frontend Architecture Documentation

## Introduction: A gRPC-first Frontend

This project's frontend architecture is built on a modern, gRPC-first approach that eliminates traditional REST APIs in favor of efficient, type-safe, binary protocols.

This is accomplished using the modern [Connect-RPC](https://connectrpc.com/) library suite from Buf (`@connectrpc/connect`, `@connectrpc/connect-express`). This allows us to define our APIs once in `.proto` files and use them to generate both the Java backend services and the TypeScript clients for the frontend.

This approach provides several key benefits:
*   **Speed & Efficiency:** Payloads are sent in the efficient Protobuf binary format, which uses less bandwidth than JSON.
*   **Type Safety:** Using generated TypeScript clients ensures that frontend and backend communication is type-safe at compile time.
*   **Schema Evolution:** Protobuf's design allows for backward and forward compatibility, and using Apicurio as a schema registry lets us track the evolution of our APIs and data types.

A central **Web Proxy** service handles the translation from the browser's protocol (Connect-RPC over HTTP/1.1) to the backend's native gRPC over HTTP/2.

## The Two Frontend Philosophies

It is critical to understand that there are two distinct strategies for building frontends in this project, depending on the component's purpose.

### 1. Base Service UIs
*   **What they are:** User interfaces for the core, foundational services of the platform (e.g., Repository Service, OpenSearch Manager, the Platform Shell itself).
*   **How they are built:** These UIs are **manually crafted** using standard Vue 3 and Vuetify components. This provides maximum flexibility to create rich, complex user experiences.

### 2. Module Configuration UIs
*   **What they are:** Configuration forms for the language-agnostic, plug-and-play processing steps in a pipeline (e.g., a Parser, Chunker, or Embedder module).
*   **How they are built:** These UIs are **auto-generated** from an OpenAPI 3.1 schema provided by the module developer. This allows developers to create modules in any language without writing any frontend code.

## Core Architectural Components

This document serves as a high-level overview. For detailed explanations of each part of the architecture, please see the dedicated documents below.

*   **[Platform Shell](./frontend/Platform_Shell.md)**
    > Describes the main application shell that provides the unified navigation, layout, and hosting for all other frontend applications.

*   **[Web Proxy](./frontend/Web_Proxy.md)**
    > The critical gateway that translates browser API calls to the backend, handles dynamic service discovery, and provides a centralized entry point for all services.

*   **[Service Discovery and Health](./frontend/Service_Discovery_and_Health.md)**
    > Explains the end-to-end flow of how frontends find and monitor the health of backend services using the web-proxy and a live-watching mechanism.

*   **[Module UI Rendering](./frontend/Module_UI_Rendering.md)**
    > Details the process of how an OpenAPI 3.1 schema provided by a module is automatically rendered into a fully functional configuration form using the JSON Forms library.

*   **[Protobuf Forms (INCOMPLETE)](./frontend/Protobuf_Forms.md)**
    > Outlines a separate, incomplete feature for a generic tool that could render a form for *any* Protobuf message, intended for developer tools or the Mapping Service.

## Developer Code Examples

For practical code examples of how to make gRPC calls from both backend Node.js services and frontend Vue components, please see the dedicated [gRPC Client Code Examples](./frontend/GRPC_Client_Examples.md) document.

## CRITICAL: Understanding Protobuf Types vs Schemas in TypeScript

*(This section is a key reference for any developer working on the frontend.)*

### The Core Concept
**protobuf-es v2 generates TWO things for each message:**
1.  **A TypeScript `type`** (e.g., `PipeDoc`) - This is ONLY for TypeScript compile-time type checking and DOES NOT EXIST in the final JavaScript.
2.  **A JavaScript `Schema` constant** (e.g., `PipeDocSchema`) - This is the ACTUAL runtime value used to create and describe messages.

### The Import Pattern You MUST Follow
```typescript
// Import runtime values normally
import { PipeDocRepositoryService, create, PipeDocSchema } from '@pipeline/proto-stubs';

// Import TypeScript types with 'import type'
import type { PipeDoc } from '@pipeline/proto-stubs';
```

### How to Create Protobuf Messages
```typescript
// ❌ WRONG - Types are not constructors!
// const pipeDoc = new PipeDoc({ ... });

// ✅ CORRECT - Use create() with the Schema
const pipeDoc = create(PipeDocSchema, {
  guid: crypto.randomUUID(),
  source: { path: file.name }
});
```
*(For more detailed examples, see the original document or generated code.)*
