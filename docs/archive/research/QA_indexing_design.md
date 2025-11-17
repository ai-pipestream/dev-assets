### 📋 Detailed Implementation Questions

#### A. Index Management & Naming

*   **Index naming for Strategy 1 (Embedded Object) : What's the naming convention? Is it {prefix}-{doc_type} (e.g., pipeline-article)?**
    *   Yes, that is the exact convention. The `SchemaManagerService` we designed will use the `document_type` from the `PipeDoc` to construct an index name like `pipeline-article`.

*   **Multiple document types : Can different document types share the same index, or do we always create separate indices per doc_type?**
    *   The current design creates separate indices for each `doc_type`. This is the cleanest approach as it prevents any potential mapping conflicts between different types of documents.

*   **Index lifecycle : Who decides when to create new indices vs reuse existing ones? Is this based on doc_type only?**
    *   Creation is handled on-demand by the `SchemaManagerService`. When the `opensearch-sink` module receives a document with a `doc_type` it hasn't seen before, it will ask the service to ensure the index exists. The service will then create it if it's new. Reuse is the default for all subsequent documents of the same type.

*   **Strategy coexistence : When both strategies run simultaneously, do they use completely separate index naming schemes to avoid conflicts?**
    *   Yes. Strategy 1 uses the simple `{prefix}-{doc_type}` scheme. Strategy 2 (Denormalized) uses the robust, sanitized, and joined naming scheme (e.g., `pipeline-article___body_chunks___minilm_l6`). They are designed to be completely distinct and can coexist without conflict.

#### B. Schema Management Service Integration

*   **Vector dimensions : How do we handle different embedding models with different dimensions in the same nested field? Do we create separate nested fields per dimension, or use the largest dimension?**
    *   This is a critical point. A single `knn_vector` field in OpenSearch requires a fixed dimension. Therefore, all vectors within a single `nested` field (like our `embeddings` field) **must** share the same dimension. The current design does not support mixing dimensions within that single field.

*   **Schema evolution : If we add a new embedding model with different dimensions, do we update existing indices or create new ones?**
    *   Given the limitation above, we would have to create a new index (e.g., `pipeline-article-v2`) or add a new, separate nested field to the existing index. The `SchemaManagerService` as currently designed only supports creation, not modification, so creating a new index is the most likely path.

*   **Nested field naming : Is the nested field always called "embeddings", or can it be configurable per index?**
    *   In the `OpenSearchSchemaService` interface and mock we designed, the nested field name is a parameter, so it is configurable. However, for Strategy 1, we have standardized on calling it `"embeddings"`.

*   **Multiple nested fields : Could we have multiple nested fields like embeddings_384, embeddings_768 for different dimensions?**
    *   Yes, this is the recommended approach for handling multiple, different vector dimensions within the same document. The `SchemaManagerService` would need to be called for each distinct nested field to ensure its mapping exists.

#### C. Document Processing & Aggregation

*   **Document aggregation timing : In the opensearch-sink, how long do we wait to collect all embeddings for a document before indexing? Is this time-based, count-based, or event-driven?**
    *   This is a key piece of logic for the `opensearch-sink` module that is **To Be Determined**. It will likely be a combination of time-based and count-based aggregation to balance latency and throughput.

*   **Partial document updates : What happens if we receive embeddings for a document that's already indexed? Do we replace the entire embeddings array or merge?**
    *   This is also **To Be Determined**. The simplest implementation is to perform a full document replacement. A more advanced (and complex) implementation could use OpenSearch's scripting capabilities to merge the new embeddings into the existing nested array.

*   **Document versioning : How do we handle document updates? Do we use OpenSearch's versioning, or manage it ourselves?**
    *   We should use OpenSearch's built-in external versioning. We can use the `last_modified_date` timestamp from the `PipeDoc` as the external version number to prevent out-of-order updates.

*   **Duplicate handling : If we receive the same embedding twice (same chunk_config_id + embedding_id), do we deduplicate or allow duplicates?**
    *   The `opensearch-sink`'s aggregation logic should be responsible for deduplicating embeddings based on a composite key of `chunk_config_id` and `embedding_id` before indexing the final document.

#### D. Embedding Object Structure

*   **Vector field precision : Are vectors always float, or do we need to support different precisions (float16, float32, etc.)?**
    *   The `Embedding` protobuf message defines the vector as `repeated float`, which corresponds to `float32`. This is the only precision currently in scope.

*   **Context text usage : The context_text field is repeated string - are these meant to be searchable keywords, or just metadata?**
    *   They are intended for future hybrid search capabilities. The goal is to allow keyword-based `match` queries to run against the `context_text` field in parallel with the vector search on the `vector` field.

*   **Primary vs secondary : For is_primary, do primary embeddings get special treatment in search queries or just in organization?**
    *   They get special treatment in search queries. The `is_primary` flag allows queries to be more targeted, for example, by searching *only* on embeddings where `is_primary: true` (e.g., from a document title) to get higher-relevance results.

*   **Chunk boundaries : For chunked documents, do we store chunk boundaries/positions, or just the source_text?**
    *   The `Embedding` message in our `opensearch_document.proto` only stores the `source_text`. The original `SemanticChunk` message in `pipeline_core_types.proto` *does* contain offsets, but we are not currently propagating them to the final `Embedding` object. This is a potential area for future enhancement if needed.

#### E. JSON Conversion & OpenSearch Integration

*   **Protobuf to JSON : When converting OpenSearchDocument to JSON for indexing, do we use the standard protobuf JSON mapping, or custom serialization?**
    *   We will use the standard Protobuf JSON mapping provided by libraries like `JsonFormat`. There is no need for custom serialization at this time.

*   **Timestamp handling : How are google.protobuf.Timestamp fields converted to OpenSearch date format?**
    *   The standard mapping converts them to ISO 8601 date strings (e.g., `"2025-08-01T12:00:00Z"`), which is the default format for the OpenSearch `date` field type.

*   **Custom fields : The google.protobuf.Struct custom_fields - does this flatten into the root document or stay nested?**
    *   It should be flattened into the root of the OpenSearch document. This makes the fields within the struct directly and easily queryable.

*   **Null handling : How do we handle optional fields that aren't set in the protobuf?**
    *   They will be omitted from the final JSON output during serialization. OpenSearch will correctly treat them as missing fields.

#### F. Search & Retrieval Patterns

*   **Hybrid search queries : What's the typical query pattern? Do we search across all embeddings in the nested array, or filter by specific chunk_config_id/embedding_id first?**
    *   A typical query would use a `nested` query on the `embeddings.vector` field. This would be combined with a `bool` query to filter by `embeddings.chunk_config_id` or `embeddings.embedding_id` within the nested query's filter context.

*   **Result structure : When searching, do we return the entire document or just matching embedding objects?**
    *   By default, OpenSearch returns the entire document. However, the correct approach is to use the `inner_hits` feature within the `nested` query to return only the specific `Embedding` object(s) that matched the search, along with their scores.

*   **Scoring : How do we handle scoring when multiple embeddings in the same document match?**
    *   The `inner_hits` feature will provide a relevance score for each matching nested document. The application layer can then decide how to aggregate these scores (e.g., use the maximum score, sum them, etc.).

#### G. A/B Testing & Multi-Model Support

*   **Test isolation : For A/B testing, do we query specific embedding_id/chunk_config_id combinations, or compare results across all combinations?**
    *   The design fully supports querying specific combinations by filtering on the `embedding_id` and `chunk_config_id` fields within the nested query.

*   **Model comparison : When testing multiple embedding models, do we expect the same source_text to appear multiple times with different embedding_ids?**
    *   Yes, precisely. This is a core tenet of the design. The same `source_text` will exist in multiple `Embedding` objects, distinguished only by their `embedding_id`, allowing for direct comparison.

*   **Performance impact : With multiple embeddings per document, what's the expected impact on index size and query performance?**
    *   The index size will increase linearly with the number of embeddings stored. Query performance may see some degradation as the number of vectors to compare within a document grows, but `nested` fields are optimized for this use case.

#### H. Strategy 2 (Denormalized) Specifics

*   **Index explosion : With the denormalized approach, how many indices do you expect in a typical deployment? Hundreds? Thousands?**
    *   This could easily lead to thousands of indices in a complex deployment with many document types and A/B tests. This is the primary drawback of this strategy.

*   **Cross-index search : Do we ever need to search across multiple denormalized indices simultaneously?**
    *   Yes. OpenSearch allows searching across multiple indices using wildcards (e.g., `pipeline-article-body-*`), which would be the primary method for comparing results across different A/B test indices.

*   **Index management : Who manages the lifecycle of these many indices (creation, deletion, optimization)?**
    *   This would require a dedicated, automated lifecycle management process. It would not be feasible to manage these indices manually.

#### I. Error Handling & Edge Cases

*   **Malformed embeddings : What happens if an embedding has the wrong dimension or invalid data?**
    *   The `opensearch-sink` should ideally perform a pre-flight validation of vector dimensions. If an invalid embedding is sent to OpenSearch, the bulk indexing request for that document will fail. This failure should be caught, logged, and the problematic `PipeDoc` should be routed to a Dead Letter Queue (DLQ).

*   **Missing dependencies : What if we receive embeddings for a document_id that doesn't exist yet?**
    *   This is the core challenge for the `opensearch-sink`. It must implement a stateful aggregation mechanism (likely using a temporary cache like Redis) with a timeout. If all parts of a document do not arrive within the timeout window, the incomplete document should be sent to a DLQ or a separate "incomplete" index for later reconciliation.

*   **Schema conflicts : What if two services try to create incompatible schemas for the same index?**
    *   The distributed lock in the `SchemaManagerService` is designed specifically to prevent this race condition. The first service to acquire the lock for a given index name will create the schema, and all subsequent attempts will see that the schema already exists.

#### J. Implementation Priority

*   **Which strategy first : Should we implement Strategy 1 (Embedded Object) first, then Strategy 2, or build both simultaneously?**
    *   Strategy 1 (Embedded Object) should be implemented first. It is the primary, most flexible, and most generally applicable approach.

*   **Migration path : Do you need to migrate existing data, or is this a greenfield implementation?**
    *   This is a greenfield implementation. We have not discussed any data migration requirements.

*   **Testing approach : How do you want to validate that both strategies produce equivalent search results?**
    *   By creating a standardized set of benchmark queries. We would execute these queries against both strategies (querying the nested field in Strategy 1, and querying across the denormalized indices in Strategy 2) and then compare the returned document IDs and their relevance scores to ensure they are equivalent.
