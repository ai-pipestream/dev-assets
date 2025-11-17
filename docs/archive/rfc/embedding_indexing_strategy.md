# RFC: A Unified, Nested Strategy for Embedding Indexing

**Status:** Proposed

## 1. Summary

This document proposes a single, unified strategy for indexing vector embeddings in OpenSearch. The goal is to create a robust, flexible, and future-proof system that can handle complex A/B testing scenarios, support powerful hybrid search, and provide a clear path for future enhancements like Retrieval-Augmented Generation (RAG).

As a powerful alternative for users who require maximum data isolation, a second, "Denormalized" strategy is also proposed, which can be run concurrently.

The core of the primary proposal is to abandon complex, top-level field naming conventions in favor of a single, canonical `Embedding` object stored within a `nested` field in OpenSearch.

## 2. The Problem

Our pipeline needs to support a variety of A/B testing scenarios. We need to be able to test different chunking strategies and different embedding models on the same source data. Early design discussions focused on creating unique, dynamically generated field names for each A/B test combination (e.g., `body_text__sentences_512__minilm__vector`).

This approach, while functional, was found to have several critical flaws:

*   **Complexity:** It required a complex, stateful `SchemaManagerService` with fragile, escape-based sanitization logic to prevent field name collisions.
*   **Rigidity:** It was difficult to add new metadata to the test context without changing the entire naming convention.
*   **Poor Hybrid Search:** It did not provide an elegant way to co-locate the original source text with its vector for efficient hybrid search.

## 3. The Proposed Solution: The "Embedded Object" Strategy

This proposal advocates for a complete architectural pivot to a model that leverages OpenSearch's `nested` data type. This approach treats all embeddings—whether from a small, non-chunked field like a `title` or from one of many chunks of a large `body`—as instances of a single, canonical `Embedding` object.

### 3.1. The Canonical Data Model

We will define a single gRPC message, `OpenSearchDocument`, which will be the standard representation of a document to be indexed. This message will contain a list of `Embedding` objects.

**The `Embedding` Object:**

This is the fundamental unit of our design. Each `Embedding` object represents a single vector and its complete context.

```proto
message Embedding {
  repeated float vector = 1;
  string source_text = 2;
  repeated string context_text = 3;
  string chunk_config_id = 4;
  string embedding_id = 5;
  bool is_primary = 6;
}
```

*   `vector`: The vector embedding.
*   `source_text`: The original text that generated the vector. This is critical for hybrid search.
*   `context_text`: An array for derived textual data (keywords, summaries, etc.) to be added by data scientists or GenAI agents.
*   `chunk_config_id`: The ID of the chunking strategy.
*   `embedding_id`: The ID of the embedding model.
*   `is_primary`: A boolean flag to differentiate primary fields (like a title) from secondary chunks (from a body).

### 3.2. The OpenSearch Mapping

A parent document in OpenSearch will contain a single field, e.g., `embeddings`, which will be mapped with `type: "nested"`. This field will contain the array of `Embedding` objects.

```json
{
  "mappings": {
    "properties": {
      "embeddings": {
        "type": "nested",
        "properties": {
          "vector": { "type": "knn_vector", "dimension": 384 },
          "source_text": { "type": "text" },
          "context_text": { "type": "keyword" },
          "chunk_config_id": { "type": "keyword" },
          "embedding_id": { "type": "keyword" },
          "is_primary": { "type": "boolean" }
        }
      }
    }
  }
}
```

### 3.3. How It Solves the Problems

*   **Simplicity:** The complex field name sanitization and collision problem is completely eliminated. The user-provided IDs are now just data values, not part of the schema structure.
*   **Flexibility:** Adding new metadata is easy—we just add a new field to the `Embedding` object. The schema is clean and easy to understand.
*   **Powerful Hybrid Search:** By co-locating the `vector` and `source_text` within the same nested object, we can perform highly efficient hybrid queries using a single `nested` query clause.
*   **Unified Workflow:** Non-chunked fields are simply treated as a special case where the data is processed as a single chunk with `is_primary: true`. This creates a single, elegant data flow for all use cases.

## 4. The Role of Supporting Services

*   **`opensearch-sink`:** Its role shifts from stateless stream processing to stateful stream aggregation. It must now group all `Embedding` objects by their original document ID before assembling the final `OpenSearchDocument` to be indexed. This is a natural fit for a Kafka Streams application.
*   **`SchemaManagerService`:** Its role is dramatically simplified. It no longer manages complex field names. Its only job is to ensure that a given index has the standard, predefined `nested` mapping for the `embeddings` field.

This unified, nested strategy provides a robust, scalable, and future-proof foundation for our entire embedding indexing pipeline.

---

## 5. Alternative Strategy: Denormalized Multi-Index Approach

For use cases that demand absolute data isolation and simpler queries at the cost of managing many indices, a denormalized strategy can be offered concurrently.

### 5.1. Core Principle

Instead of a single index with nested objects, this strategy creates a **separate, dedicated OpenSearch index for each unique A/B test combination**. Each `Embedding` object from the pipeline becomes a standalone document in its corresponding index.

### 5.2. Index Naming Convention

The complexity in this model shifts from field naming to **index naming**. The index name must be dynamically and uniquely generated from the context of the embedding.

*   **Components:** The index name will be a combination of a static prefix, the document type, the source field, the chunker config ID, and the embedder config ID.
*   **Example Index Name:** `pipeline-article-body-c_10_2-e_minilm`

### 5.3. Index Name Collision and Sanitization

This approach re-introduces the risk of collisions if user-provided IDs are not handled carefully. To solve this, we will adopt a robust **"Sanitize and Join"** strategy for creating index names.

1.  **User-Facing Validation:** All user-provided configuration IDs (for chunkers, embedders, etc.) will be validated at creation time by a strict regex: `^[a-zA-Z0-9][a-zA-Z0-9_-]*$`. This prevents the use of problematic characters like `.` or `/` and ensures names cannot start with `_` or `-`.

2.  **Internal Sanitization (The Escape System):** To prevent collisions between IDs like `my-id` and `my_id`, a two-step sanitization process will be used internally before creating the index name:
    *   First, every literal underscore (`_`) is replaced with a double underscore (`__`).
    *   Then, every hyphen (`-`) is replaced with a single underscore (`_`).
    *   This creates a guaranteed one-to-one mapping from a user ID to a sanitized ID.

3.  **Internal Delimiter:** The sanitized components will be joined together using a **triple underscore (`___`)** as a delimiter. This is guaranteed to be unique and will not conflict with the sanitized components.

*   **Example:** An embedding from `source_field: "body-text"` and `chunk_config_id: "my_chunker"` would result in sanitized components `body_text` and `my__chunker`, which are then joined to form part of the index name: `...___body_text___my__chunker___...`

### 5.4. Implementation

This strategy would likely be implemented by a separate, downstream indexing service. This service would consume the same canonical `Embedding` objects from a Kafka topic but would perform no aggregation. It would process each `Embedding` as a separate event, dynamically calculating the target index name and indexing it as a single document. The `SchemaManagerService` would be responsible for creating these dynamic indices and their simple mappings on demand.