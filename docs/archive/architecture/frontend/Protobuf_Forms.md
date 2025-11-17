# Protobuf Forms (INCOMPLETE)

**Status: This feature is incomplete and not currently used in the main application.**

This document outlines the intended purpose of the `@pipeline/protobuf-forms` library.

## 1. Concept

While the [Module UI Rendering](./Module_UI_Rendering.md) system is specifically for generating module configuration UIs from OpenAPI 3.1 schemas, the `@pipeline/protobuf-forms` library was envisioned for a more generic and powerful purpose: **to render a form for *any* Protobuf message on-the-fly.**

This would be a powerful developer tool or administrative utility, allowing users to edit or map any Protobuf message for which a schema exists in the Apicurio registry, without needing a pre-defined OpenAPI specification.

## 2. Intended Workflow

The envisioned workflow is as follows:

1.  **Descriptor Fetch:** A user in an admin or developer UI wants to create or edit a specific Protobuf message (e.g., a `PipeDoc` or a custom message from a module).
2.  **Backend Call:** The frontend makes a backend call to retrieve the `FileDescriptorSet` for that message type from Apicurio Registry.
3.  **Form Generation:** The `FileDescriptorSet` is passed to the `@pipeline/protobuf-forms` library.
4.  **Rendering:** The library would then dynamically generate and render a form, similar to how the module configuration works, allowing the user to edit the fields of the Protobuf message.

This would be particularly useful in the **Mapping Service**, where a user might need to visually map fields from one Protobuf message to another.
