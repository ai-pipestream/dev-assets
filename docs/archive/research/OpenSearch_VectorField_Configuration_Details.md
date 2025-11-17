

# **Vector Field Capabilities in OpenSearch 3.1.0: An Exhaustive Technical Analysis**

## **The Architectural Landscape of Vector Fields in OpenSearch 3.1.0**

The release of OpenSearch 3.1.0 marks a significant maturation point for its vector search capabilities, solidifying its position as a comprehensive solution for AI-powered search and analytics. This version introduces a suite of enhancements that cater to a spectrum of users, from MLOps engineers requiring granular control over performance and cost to application developers seeking rapid, streamlined integration of semantic search. Key advancements include the general availability of GPU acceleration for index builds, a novel semantic field type to simplify workflows, and substantial performance improvements for hybrid search and memory-constrained environments.1

This evolution reflects a deliberate architectural strategy. On one hand, OpenSearch is deepening its "power-user" features, offering sophisticated controls over the underlying k-Nearest Neighbor (k-NN) engines, memory optimization, and storage formats.1 On the other hand, it is introducing higher-level abstractions that automate complex configuration steps, lowering the barrier to entry for building intelligent applications.1 This dual approach allows OpenSearch to serve both the high-performance, fine-tuning demands of production ML systems and the ease-of-use requirements of modern application development.

At the core of this architecture are two primary field types for managing vector data, each representing a distinct path to implementation:

* **The knn\_vector Field:** This is the foundational and highly configurable field type for storing and searching vector embeddings. It provides direct, granular control over the Approximate Nearest Neighbor (ANN) algorithm, the backend search library (engine), distance metrics, and storage parameters. This field type is the "expert path," designed for users who need to meticulously tune their vector search implementation for optimal performance, recall, and resource consumption.2  
* **The semantic Field:** Introduced in OpenSearch 3.1.0, this is a high-level abstraction designed to dramatically simplify the setup of semantic search applications.1 It acts as an intelligent wrapper, automatically provisioning the necessary underlying vector storage fields (  
  knn\_vector or rank\_features) based on the metadata of a specified machine learning model. This approach automates vector dimension configuration and can even eliminate the need for a separate ingest pipeline to generate embeddings, making it the "developer-friendly" path.1

## **Definitive Guide to the knn\_vector Field Type**

The knn\_vector field is the cornerstone of vector search in OpenSearch, providing the most comprehensive set of options for defining, indexing, and searching vector embeddings. Mastery of this field type is essential for building high-performance, production-grade vector search systems.

### **Core Mapping Parameters**

When defining a knn\_vector field in an index mapping, a set of top-level parameters controls its fundamental behavior. The following table provides a complete reference for these parameters as of OpenSearch 3.1.0.2

| Parameter | Data Type | Required/Optional | Default | Description |
| :---- | :---- | :---- | :---- | :---- |
| type | String | Required | N/A | Specifies the field type. Must be set to knn\_vector. |
| dimension | Integer | Required | N/A | The number of dimensions in the vector. Valid values are between 1 and 16,000. This must match the output dimension of the embedding model used. |
| data\_type | String | Optional | float | The data type of the vector's elements. Valid values are float, byte, and binary. |
| space\_type | String | Optional | l2 | The mathematical space used to calculate distance/similarity between vectors. Can also be specified within the method object. Valid values include l2, l1, linf, cosinesimil, innerproduct, hamming, and hammingbit. Not all engines support all spaces. |
| mode | String | Optional | in\_memory | Optimizes for either low latency (in\_memory) or low cost (on\_disk). The on\_disk mode reduces memory usage by not loading all vector data into the JVM heap. |
| compression\_level | String | Optional | 1x (none) | Selects a quantization encoder to reduce vector memory consumption. Valid values are 1x, 2x, 4x, 8x, 16x, and 32x. Primarily used with on\_disk mode. |
| method | Object | Optional | N/A | Defines the ANN algorithm and engine to use when the algorithm does not require a separate training step (e.g., HNSW). |
| model\_id | String | Optional | N/A | Specifies the ID of a pre-trained model to use for ANN algorithms that require a training phase (e.g., Faiss IVF). This is mutually exclusive with method. |

### **Configuration via Method Definition**

For ANN algorithms like HNSW that do not require a separate training phase, the method object is the primary configuration mechanism. This object is defined directly within the knn\_vector field mapping and specifies the algorithm, the backend library, the distance space, and any algorithm-specific tuning parameters.4

A typical method definition structure is as follows:

JSON

"my\_vector\_field": {  
  "type": "knn\_vector",  
  "dimension": 768,  
  "method": {  
    "name": "hnsw",  
    "engine": "lucene",  
    "space\_type": "l2",  
    "parameters": {  
      "m": 16,  
      "ef\_construction": 256  
    }  
  }  
}

### **Deep Dive into ANN Engines, Methods, and Parameters**

OpenSearch's k-NN plugin provides a pluggable architecture that supports multiple backend libraries, or "engines," for performing approximate nearest neighbor search. The choice of engine is a critical architectural decision that impacts performance, memory usage, filtering capabilities, and available tuning parameters. The following table provides a comprehensive comparison of the available engines and their methods in OpenSearch 3.1.0.

| Engine | Method | Index-Time Parameters | Search-Time Parameters | Supported space\_type | Key Architectural Notes |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Lucene** | hnsw | m: (Integer) Max connections per node. ef\_construction: (Integer) Size of the dynamic list for graph construction. | ef\_search: (Integer) Size of the dynamic list for search. Overridden at query time. | l2, cosinesimil, innerproduct | Native to OpenSearch/Lucene. Offers highly efficient pre-filtering. Can search Faiss-built HNSW indexes in 3.1.0. Max dimension is 1,024.6 |
| **Faiss** | hnsw | m: (Integer) Max connections per node. ef\_construction: (Integer) Size of the dynamic list for graph construction. encoder: (Object) Defines a quantization encoder (e.g., pq). | ef\_search: (Integer) Size of the dynamic list for search. Overridden at query time. | l2, innerproduct | High-performance C++ library. Supports quantization (pq) for memory optimization. Supports efficient filtering.8 Benefits from GPU-accelerated index building.1 |
| **Faiss** | ivf | nlist: (Integer) Number of inverted lists (clusters). encoder: (Object) Defines a quantization encoder (e.g., pq). | nprobes: (Integer) Number of inverted lists to probe at search time. | l2, innerproduct | Requires a separate training step to create a model\_id. Excellent for extremely large datasets. Supports efficient filtering.8 |
| **NMSLIB** (Deprecated) | hnsw | m: (Integer) Max connections per node. ef\_construction: (Integer) Size of the dynamic list for graph construction. | ef\_search: (Integer) Size of the dynamic list for search. Set in index settings, not per-query. | l2, cosinesimil, innerproduct | Original engine in the k-NN plugin. Now deprecated in favor of Lucene and Faiss. Filtering is less efficient (post-filtering only).8 |

#### **The Lucene Engine**

The integration of Apache Lucene as a native engine for the knn\_vector field is a strategic enhancement. Initially considered as a separate dense\_vector field type, the decision to merge this functionality into the existing knn\_vector API demonstrates a commitment to a unified user experience and avoidance of API fragmentation.6

The Lucene engine uses its own implementation of the HNSW algorithm. Its primary advantages are its tight integration with the core of OpenSearch and its superior filtering performance. Because the vector index and the filterable fields are both managed by Lucene, it can perform highly efficient "pre-filtering," where the document set is narrowed by the filter *before* the expensive vector search is executed.6

Key Parameters for Lucene HNSW 6:

* m: An integer that maps to Lucene's max\_connections, controlling the number of links each node in the graph can have.  
* ef\_construction: An integer that maps to Lucene's beam\_width, controlling the candidate list size during graph construction.

A groundbreaking feature in OpenSearch 3.1.0 is the ability to use the Lucene engine to search HNSW graphs that were originally built by the Faiss engine.1 This hybrid approach offers the best of both worlds: users can leverage Faiss for its extremely fast, GPU-accelerated index building, and then use Lucene for its memory-efficient search capabilities, which support partial byte loading and effective early termination. This makes it possible to search massive indexes (e.g., a 30 GB Faiss index) in memory-constrained environments (e.g., a 16 GB instance), a task that would be impossible with the Faiss C++ library alone.1

#### **The Faiss Engine**

Faiss (Facebook AI Similarity Search) is a high-performance C++ library specializing in efficient similarity search and clustering of dense vectors. It is the engine of choice for use cases involving very large scale (billions of vectors) and those requiring advanced memory optimization techniques like quantization.4 The general availability of GPU acceleration for index builds in OpenSearch 3.1.0 makes Faiss particularly compelling for users who need to create or update massive indexes rapidly.1

Faiss supports two primary methods:

1. **HNSW (hnsw):** Similar to the Lucene implementation, this method builds a hierarchical graph structure. It supports efficient filtering (as of version 2.9) and can be combined with a Product Quantization (pq) encoder to compress vectors and reduce memory footprint.4  
   * **HNSW Parameters:** m, ef\_construction.  
   * **PQ Encoder Parameters:** m (number of sub-vectors), code\_size (bits to encode each sub-vector).  
2. **IVF (ivf):** The Inverted File method partitions vectors into clusters (defined by nlist) and, at search time, probes a subset of these clusters (nprobes). This method requires a training step and is thus configured via a model\_id rather than a method block. It is highly effective for billion-scale datasets and also supports pq encoding and efficient filtering (as of version 2.10).4

#### **The NMSLIB Engine (Deprecated)**

NMSLIB (Non-Metric Space Library) was the original engine supported by the k-NN plugin. While it is now deprecated in favor of the more feature-rich and performant Lucene and Faiss engines, it is included for backward compatibility.8 It supports the

hnsw method with parameters m and ef\_construction.4 Its filtering is limited to less-efficient post-filtering, where the vector search is performed first and the results are filtered afterward, which can lead to fewer than

k results being returned.10

### **Configuration via Model ID**

For ANN algorithms that require a training phase, most notably Faiss ivf, the knn\_vector field is configured by referencing a model\_id. This workflow involves three distinct steps 4:

1. **Create a Training Index:** An index is created with a simple knn\_vector field that only specifies the dimension. A representative sample of the vector data is then ingested into this index.  
2. **Train the Model:** The Train API (POST /\_plugins/\_knn/models/\_train) is called, pointing to the training index and field. The request body includes the full method definition that will be used (e.g., Faiss ivf with its nlist parameter). This API call trains the model (e.g., determines the cluster centroids for IVF) and returns a model\_id.  
3. **Create the Production Index:** The final production index is created with a knn\_vector mapping that specifies the model\_id obtained in the previous step. When documents are ingested into this index, OpenSearch uses the trained model to correctly structure the underlying native library files.

## **The semantic Field Type: A New Abstraction in OpenSearch 3.1.0**

Recognizing the complexity involved in setting up a full vector search pipeline, OpenSearch 3.1.0 introduces the semantic field type. This feature represents a significant philosophical shift, moving from providing a low-level "toolkit" to offering a high-level "solution" for semantic search.1

### **A Simplified Path to Semantic Search**

The semantic field acts as an intelligent abstraction layer. When a field is mapped with type: "semantic", the only required parameter is a model\_id pointing to a deployed text embedding model.1 OpenSearch then automatically handles several complex configuration steps:

* **Automatic Field Creation:** It inspects the model's metadata and creates the appropriate underlying storage field—either a knn\_vector for dense models or rank\_features for sparse models—with the correct dimension and other parameters.1  
* **Automated Ingestion:** It automatically generates vector embeddings for incoming documents without requiring the user to configure a separate ingest pipeline with a text\_embedding or ml\_inference processor.1  
* **Simplified Querying:** The neural query can now directly target a semantic field with raw query text. OpenSearch transparently handles the generation of the query embedding and resolution to the correct underlying vector field.1

This automation dramatically streamlines the process of building a semantic search application. However, this simplicity comes at the cost of granular control. For production systems where fine-grained tuning of ANN parameters (m, ef\_construction, etc.), storage modes, or compression is required, the manual knn\_vector approach remains the recommended path. The semantic field is ideal for rapid prototyping, proof-of-concepts, and simpler production use cases where the default configurations are sufficient.

### **Mapping and Features**

The mapping for a semantic field is minimal. In addition to the required model\_id, it also supports a flag for automatic text chunking, which can split long text fields into smaller passages before embedding generation, further simplifying the data preparation workflow.1

Example mapping:

JSON

"mappings": {  
  "properties": {  
    "my\_text\_field": {  
      "type": "semantic",  
      "model\_id": "your-embedding-model-id"  
    }  
  }  
}

## **Data Ingestion and Pipeline Integration**

Once a vector field is defined in the index mapping, the next step is to populate it with vector embeddings. OpenSearch provides flexible options to accommodate different MLOps workflows, including the user's scenario of having an existing embedding pipeline.

### **Data Formatting for Vector Fields**

The knn\_vector field expects vector data in a specific format depending on the configured data\_type 2:

* **float (default):** An array of floating-point numbers. Example: \[1.2, 3.4, \-0.5,...\]  
* **byte:** An array of integers between \-128 and 127\. Example: \[10, \-25, 110,...\]  
* **binary:** A Base64-encoded string representing the binary vector data.

In all cases, the number of elements in the vector must exactly match the dimension specified in the mapping.

### **Integrating Custom Embedding Workflows**

For a user with an existing, external embedding pipeline, there are two primary integration patterns. The choice between them is a critical architectural decision based on trade-offs between system coupling, latency, and operational complexity.

#### **Path 1: Pushing Pre-Computed Vectors**

This is the most direct and decoupled approach. The external embedding pipeline is responsible for converting text into vectors. These vectors are then included as a field in the JSON document that is sent to OpenSearch's standard \_index or \_bulk APIs.11

* **Workflow:**  
  1. Application generates or retrieves a document with a text field.  
  2. The text is sent to the external embedding pipeline/service.  
  3. The service returns a vector embedding.  
  4. The application constructs a JSON document containing both the original text and the vector array.  
  5. The application sends this complete document to the OpenSearch \_bulk endpoint.  
* **Advantages:** Keeps the search and ML inference stacks completely separate. This simplifies dependency management and allows the ML stack to be scaled and managed independently.  
* **Disadvantages:** May introduce additional network latency between the application, the embedding service, and OpenSearch. The client application logic is more complex as it must orchestrate this multi-step process.

#### **Path 2: Integrating the Model into OpenSearch**

This approach leverages OpenSearch's ML-Commons plugin to manage and execute the embedding model directly. This co-locates inference with data storage and is the more tightly integrated pattern.

* **Workflow:**  
  1. The custom embedding model is registered and deployed within OpenSearch, either by uploading it directly or by configuring a connector to a remote model hosted on a platform like Amazon SageMaker.12  
  2. An OpenSearch ingest pipeline is created with a text\_embedding or ml\_inference processor.14 This processor is configured to read from a source text field, send it to the deployed model for inference, and write the resulting vector into the target  
     knn\_vector field.  
  3. The application sends a JSON document containing only the raw text field to the OpenSearch \_bulk endpoint, specifying the ingest pipeline in the request (?pipeline=my-embedding-pipeline).  
  4. OpenSearch intercepts the document, executes the pipeline, generates the vector, and indexes the enriched document automatically.  
* **Advantages:** Simplifies client application logic, as it only needs to send raw text. Can reduce overall latency by eliminating a network hop to an external service. Allows OpenSearch to manage the resources and scaling for the inference workload.  
* **Disadvantages:** Tightly couples the ML model lifecycle with the search cluster. Requires managing models within the ML-Commons framework.

## **Query-Side Machine Learning Integration**

Effective vector search requires that the query text be converted into an embedding using the exact same model that was used to embed the documents. OpenSearch provides a rich set of pre-trained models and a robust mechanism for handling complex model types, such as asymmetric embeddings.

### **Complete Inventory of Pre-trained Models**

OpenSearch provides a curated list of pre-trained text embedding and sparse encoding models that can be deployed out-of-the-box. The dense text embedding models are primarily sourced from Hugging Face, while the sparse models are trained by OpenSearch.15 These models cover a range of use cases, from general-purpose semantic similarity to specialized question-answering and multilingual applications.

The table below provides a complete list of the pre-trained dense and sparse models available for OpenSearch 3.1.0.15

| Model Type | Model Name | Version | Vector Dimensions | Key Use Case |
| :---- | :---- | :---- | :---- | :---- |
| **Sentence Transformer** | huggingface/sentence-transformers/all-distilroberta-v1 | 1.0.2 | 768 | General Purpose |
| **Sentence Transformer** | huggingface/sentence-transformers/all-MiniLM-L6-v2 | 1.0.2 | 384 | General Purpose, Balanced Performance |
| **Sentence Transformer** | huggingface/sentence-transformers/all-MiniLM-L12-v2 | 1.0.2 | 384 | General Purpose, Higher Accuracy |
| **Sentence Transformer** | huggingface/sentence-transformers/all-mpnet-base-v2 | 1.0.2 | 768 | High-Quality General Purpose |
| **Sentence Transformer** | huggingface/sentence-transformers/msmarco-distilbert-base-tas-b | 1.0.3 | 768 | Optimized for Semantic Search |
| **Sentence Transformer** | huggingface/sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 1.0.2 | 384 | Optimized for Question Answering |
| **Sentence Transformer** | huggingface/sentence-transformers/multi-qa-mpnet-base-dot-v1 | 1.0.2 | 768 | High-Quality Question Answering |
| **Sentence Transformer** | huggingface/sentence-transformers/paraphrase-MiniLM-L3-v2 | 1.0.2 | 384 | Optimized for Paraphrase Detection |
| **Sentence Transformer** | huggingface/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 | 1.0.2 | 384 | Multilingual Paraphrase Detection |
| **Sentence Transformer** | huggingface/sentence-transformers/paraphrase-mpnet-base-v2 | 1.0.1 | 768 | High-Quality Paraphrase Detection |
| **Sentence Transformer** | huggingface/sentence-transformers/distiluse-base-multilingual-cased-v1 | 1.0.2 | 512 | Multilingual General Purpose |
| **Neural Sparse** | amazon/neural-sparse/opensearch-neural-sparse-encoding-v1 | 1.0.1 | N/A (Sparse) | Sparse Retrieval |
| **Neural Sparse** | amazon/neural-sparse/opensearch-neural-sparse-encoding-v2-distill | 1.0.0 | N/A (Sparse) | Distilled Sparse Retrieval |
| **Neural Sparse** | amazon/neural-sparse/opensearch-neural-sparse-encoding-doc-v1 | 1.0.1 | N/A (Sparse) | Document-Optimized Sparse Retrieval |

**Note for OpenSearch 3.1.0 Users:** When uploading a local model using the opensearch-py-ml Python client, a change in OpenSearch 3.1.0 requires an additional field in the model's config.json file to avoid an illegal\_argument\_exception. The key-value pair "function\_name": "TEXT\_EMBEDDING" must be added to the configuration file before the model\_config object for the upload to succeed.16

### **Asymmetric Embeddings: A Deep Dive into Query vs. Indexing Prefixes**

Asymmetric embedding models are designed to embed queries and documents (passages) into different vector spaces to improve search relevance. They often achieve this by prepending a specific prefix to the input text (e.g., "query: " for queries, "passage: " for documents) before generating the embedding. OpenSearch supports this workflow through a combination of model configuration and pipeline processing.17

The implementation requires correct configuration at three stages: model registration, data ingestion, and search execution.

Step 1: Model Registration with Prefixes  
When registering the asymmetric model with the ML-Commons plugin, you must specify the query\_prefix and passage\_prefix within the model\_config object.

JSON

POST /\_plugins/\_ml/models/\_register  
{  
  "name": "intfloat/multilingual-e5-small",  
  "version": "1.0.0",  
  "model\_group\_id": "your-model-group-id",  
  "model\_format": "TORCH\_SCRIPT",  
  "function\_name": "TEXT\_EMBEDDING",  
  "model\_config": {  
    "model\_type": "e5",  
    "embedding\_dimension": 384,  
    "framework\_type": "sentence\_transformers",  
    "all\_config": "...",  
    "query\_prefix": "query: ",  
    "passage\_prefix": "passage: "  
  }  
}

Step 2: Ingest Pipeline for Passage Embedding  
To automate the embedding of documents during indexing, an ingest pipeline is used. The ml\_inference processor is configured to generate embeddings for the incoming documents, which are considered "passages."

JSON

PUT /\_ingest/pipeline/asymmetric\_passage\_pipeline  
{  
  "description": "Generate passage embeddings using an asymmetric model",  
  "processors": \[  
    {  
      "ml\_inference": {  
        "model\_id": "your-asymmetric-model-id",  
        "input\_map": \[  
          {  
            "text\_docs": "source\_text\_field"  
          }  
        \],  
        "output\_map": \[  
          {  
            "passage\_embedding": "$.inference\_results.output.data"  
          }  
        \],  
        "model\_input": "{\\"text\_docs\\":\[\\"${\_ingest.input\_map.text\_docs}\\"\], \\"parameters\\":{\\"content\_type\\":\\"passage\\"}}"  
      }  
    }  
  \]  
}

In this pipeline, the model\_input explicitly sets "content\_type":"passage". When a document is indexed using this pipeline, the ML-Commons plugin will prepend the configured passage\_prefix to the content of source\_text\_field before sending it to the model.

Step 3: Search Pipeline for Query Embedding  
To handle queries correctly, a search pipeline is created. This pipeline intercepts the search request, extracts the query text, generates a "query" embedding, and injects it into the k-NN query clause.

JSON

PUT /\_search/pipeline/asymmetric\_query\_pipeline  
{  
  "request\_processors": \[  
    {  
      "ml\_inference": {  
        "model\_id": "your-asymmetric-model-id",  
        "input\_map": {  
          "query": "query.neural.my\_vector\_field.query\_text"  
        },  
        "output\_map": {  
          "query\_embedding": "$.inference\_results.output.data"  
        },  
        "model\_input": "{ \\"text\_docs\\": \[\\"${\_search.input\_map.query}\\"\], \\"parameters\\": {\\"content\_type\\": \\"query\\"} }",  
        "query\_template": "{\\"query\\":{\\"knn\\":{\\"my\_vector\_field\\":{\\"vector\\":${\_search.output\_map.query\_embedding},\\"k\\":5}}}}"  
      }  
    }  
  \]  
}

Here, the model\_input sets "content\_type":"query", ensuring the query\_prefix is used. The query\_template then constructs the final knn query using the generated query\_embedding. When a user runs a neural search against an index with this search pipeline enabled, the entire asymmetric workflow is executed automatically.

## **Source Code Reference: The KnnVectorFieldMapper Class**

For developers seeking to understand the deepest implementation details, the source code provides the ultimate source of truth. The core Java class responsible for handling the knn\_vector field type within the k-NN plugin is KnnVectorFieldMapper.

* Direct Link to Source Code (main branch):  
  https://github.com/opensearch-project/k-NN/blob/main/src/main/java/org/opensearch/knn/index/mapper/KNNVectorFieldMapper.java

### **Architectural Role of the Class**

The KNNVectorFieldMapper is the critical component that bridges the gap between the high-level, declarative JSON mapping provided by the user and the low-level index structures required by Lucene and the native ANN libraries. Its primary responsibilities include:

* **Parsing:** It parses the knn\_vector object from the index mapping, extracting and validating all parameters like dimension, method, engine, and space\_type.18  
* **Validation:** It performs crucial validation checks, such as ensuring that vector field names do not contain illegal characters, which is important for preventing issues with the underlying file-based storage of native library indexes.19  
* **Field Construction:** It constructs the appropriate internal field representation that Lucene will use to process the vector data. An interesting implementation detail revealed in the code and related discussions is that there are different internal paths. For native engines like Faiss and NMSLIB, KNNVectorFieldMapper creates a VectorField, whereas for the Lucene engine, a different mapper creates a KnnVectorField. This hints at the distinct logic required to interface with the external C++ libraries versus the native Lucene implementation.18

By examining this class, developers can gain a profound understanding of how their mapping choices translate into concrete index structures and behaviors.

## **Conclusion and Strategic Recommendations**

OpenSearch 3.1.0 delivers a powerful and versatile platform for vector search, offering a multi-layered toolkit that empowers engineers to select the appropriate level of abstraction and control for their specific use case. From the highly tunable knn\_vector field with its multiple backend engines to the new, streamlined semantic field, the platform effectively caters to both deep-tech MLOps and agile application development. The general availability of GPU acceleration, advanced memory optimization techniques, and sophisticated pipeline-based ML integration further cement its status as a first-class vector database.

To navigate these capabilities effectively, the following strategic recommendations provide a framework for making key architectural decisions.

* **Choosing Your Field Type (semantic vs. knn\_vector):**  
  * **Use the semantic field for:** Rapid prototyping, proof-of-concepts, and simpler production applications where ease of use and speed of development are paramount. It is the ideal choice when the default vector search configuration is sufficient and the goal is to quickly integrate semantic capabilities.  
  * **Use the knn\_vector field for:** Production systems that require high performance, large scale, and cost optimization. This path provides the essential granular control over ANN algorithm parameters, memory management (on\_disk mode), quantization, and filtering strategies needed to tune the system for specific recall, latency, and cost requirements.  
* **Choosing Your ANN Engine (Lucene vs. Faiss):**  
  * **Choose the Lucene engine for:** Use cases where tight integration with OpenSearch's core functionality, simplicity, and highly efficient pre-filtering are the primary concerns. It is an excellent default choice for many applications.  
  * **Choose the Faiss engine for:** Use cases at the extremes of scale (hundreds of millions or billions of vectors) or those that can benefit from advanced features like product quantization (pq) for memory reduction or training-based methods (ivf). With GPU-accelerated indexing now generally available, Faiss is the premier choice for building very large indexes as quickly as possible.  
  * **Consider the Hybrid Approach:** For a powerful, best-of-both-worlds strategy, use the Faiss engine to build indexes (leveraging GPU acceleration) and then use the Lucene engine to search them (leveraging superior memory management and filtering). This new capability in 3.1.0 is a game-changer for memory-constrained, high-performance environments.  
* **Choosing Your Pipeline Integration Strategy:**  
  * **Push Pre-Computed Vectors if:** Your organization has a mature, established MLOps workflow for generating embeddings, and the priority is to maintain a clean separation and decoupling between the ML inference stack and the search stack.  
  * **Integrate the Model into OpenSearch if:** The priority is to simplify client-side application logic, reduce network latency, and leverage the OpenSearch cluster to manage the scaling and lifecycle of the embedding model. This creates a more unified and streamlined architecture.

By carefully considering these trade-offs, engineers can harness the full power of OpenSearch 3.1.0 to build sophisticated, scalable, and cost-effective AI-powered search applications.

#### **Works cited**

1. Get started with OpenSearch 3.1 \- OpenSearch, accessed August 1, 2025, [https://opensearch.org/blog/get-started-with-opensearch-3-1/](https://opensearch.org/blog/get-started-with-opensearch-3-1/)  
2. k-NN vector \- OpenSearch Documentation, accessed August 1, 2025, [https://docs.opensearch.org/docs/latest/field-types/supported-field-types/knn-vector/](https://docs.opensearch.org/docs/latest/field-types/supported-field-types/knn-vector/)  
3. Supported field types \- OpenSearch Documentation, accessed August 1, 2025, [https://docs.opensearch.org/docs/latest/field-types/supported-field-types/index/](https://docs.opensearch.org/docs/latest/field-types/supported-field-types/index/)  
4. How to Set Up Vector Search in OpenSearch, With Examples \- Opster, accessed August 1, 2025, [https://opster.com/guides/opensearch/opensearch-machine-learning/how-to-set-up-vector-search-in-opensearch/](https://opster.com/guides/opensearch/opensearch-machine-learning/how-to-set-up-vector-search-in-opensearch/)  
5. k-NN Index \- OpenSearch Documentation, accessed August 1, 2025, [https://docs.opensearch.org/docs/1.3/search-plugins/knn/knn-index/](https://docs.opensearch.org/docs/1.3/search-plugins/knn/knn-index/)  
6. \[RFC\] Lucene based kNN search support in core OpenSearch ..., accessed August 1, 2025, [https://github.com/opensearch-project/OpenSearch/issues/3545](https://github.com/opensearch-project/OpenSearch/issues/3545)  
7. \[Feature\] \[META\] Add Efficient filtering support for Faiss Engine · Issue \#903 · opensearch-project/k-NN \- GitHub, accessed August 1, 2025, [https://github.com/opensearch-project/k-NN/issues/903](https://github.com/opensearch-project/k-NN/issues/903)  
8. Filtering data \- OpenSearch Documentation, accessed August 1, 2025, [https://opensearch.org/docs/latest/vector-search/filter-search-knn/index/](https://opensearch.org/docs/latest/vector-search/filter-search-knn/index/)  
9. OpenSearch kNN Plugin \- Uses, Benefits and Examples \- Opster, accessed August 1, 2025, [https://opster.com/guides/opensearch/opensearch-machine-learning/opensearch-knn/](https://opster.com/guides/opensearch/opensearch-machine-learning/opensearch-knn/)  
10. Approximate k-NN search \- OpenSearch, accessed August 1, 2025, [https://opensearch.org/docs/1.0/search-plugins/knn/approximate-knn/](https://opensearch.org/docs/1.0/search-plugins/knn/approximate-knn/)  
11. OpenSearch KNN Plugin Tutorial \- Sease.io, accessed August 1, 2025, [https://sease.io/2024/01/opensearch-knn-plugin-tutorial.html](https://sease.io/2024/01/opensearch-knn-plugin-tutorial.html)  
12. Getting started with semantic and hybrid search \- OpenSearch Documentation, accessed August 1, 2025, [https://docs.opensearch.org/docs/latest/tutorials/vector-search/neural-search-tutorial/](https://docs.opensearch.org/docs/latest/tutorials/vector-search/neural-search-tutorial/)  
13. Neural Search on OpenSearch \- Medium, accessed August 1, 2025, [https://medium.com/@zelal.gungordu/neural-search-on-opensearch-69d394495ab7](https://medium.com/@zelal.gungordu/neural-search-on-opensearch-69d394495ab7)  
14. OpenSearch Neural Search Plugin Tutorial \- Sease.io, accessed August 1, 2025, [https://sease.io/2022/12/opensearch-neural-search-plugin-tutorial.html](https://sease.io/2022/12/opensearch-neural-search-plugin-tutorial.html)  
15. Pretrained models \- OpenSearch Documentation, accessed August 1, 2025, [https://docs.opensearch.org/docs/latest/ml-commons-plugin/pretrained-models/](https://docs.opensearch.org/docs/latest/ml-commons-plugin/pretrained-models/)  
16. Error uploading local model to OS 3.1.0 \- Machine Learning \- OpenSearch Forum, accessed August 1, 2025, [https://forum.opensearch.org/t/error-uploading-local-model-to-os-3-1-0/25778](https://forum.opensearch.org/t/error-uploading-local-model-to-os-3-1-0/25778)  
17. Approximate k-NN search \- OpenSearch Documentation, accessed August 1, 2025, [https://docs.opensearch.org/latest/vector-search/vector-search-techniques/approximate-knn/](https://docs.opensearch.org/latest/vector-search/vector-search-techniques/approximate-knn/)  
18. Remove duplicated parseCreateField in LuceneFieldMapper · Issue \#1632 · opensearch-project/k-NN \- GitHub, accessed August 1, 2025, [https://github.com/opensearch-project/k-NN/issues/1632](https://github.com/opensearch-project/k-NN/issues/1632)  
19. \[BUG\] Fail to upgrade to OpenSearch 2.17 due to KNN field name validation \#2219 \- GitHub, accessed August 1, 2025, [https://github.com/opensearch-project/k-NN/issues/2219](https://github.com/opensearch-project/k-NN/issues/2219)