# grpcurl Useful Commands (Repository Suite)

These commands exercise the repository-service gRPC APIs end-to-end using grpcurl, including S3-backed filesystem operations, PipeDoc storage, and ProcessRequest storage. All commands use plaintext (h2c) against the Quarkus HTTP port.

Prerequisites
- Compose dev stack running (MySQL, Kafka, Apicurio, MinIO, OpenSearch, LGTM).
- Services started locally (default ports):
  - repository-service: 38102
  - opensearch-manager: 38103
  - platform-registration-service: 38101
- grpcurl installed and available on PATH.

Notes
- Plaintext flag: add `-plaintext` to grpcurl.
- Any payloads: use `"@type": "type.googleapis.com/<FullMessageName>"` with a value field.
- Replace placeholders like `NODE_ID` and `STORAGE_ID` with values returned by previous commands.

---

## A) Filesystem + S3: create drive, upload a file, verify

1) Create a drive
- What it does: Creates a new logical filesystem (mapped to a dedicated S3 bucket in dev) managed by repository-service.
- Command:
```bash
grpcurl -plaintext \
  -d '{
    "name":"dev-drive",
    "description":"Dev test drive",
    "metadata": {"env":"dev"}
  }' \
  localhost:38102 \
  io.pipeline.repository.filesystem.FilesystemService/CreateDrive
```

2) Upload a small file immediately (inline payload)
- What it does: Initiates an upload and stores a small text payload inline via Any (google.protobuf.StringValue). Returns the created `node_id` and completion state.
- Command:
```bash
grpcurl -plaintext \
  -d '{
    "drive":"dev-drive",
    "parentId":"",
    "name":"hello.txt",
    "mimeType":"text/plain",
    "payload":{
      "@type":"type.googleapis.com/google.protobuf.StringValue",
      "value":"Hello from grpcurl"
    }
  }' \
  localhost:38102 \
  io.pipeline.repository.filesystem.upload.NodeUploadService/InitiateUpload
```

3) Get the node (with payload)
- What it does: Fetches the node by id and includes the stored payload for verification.
- Command (replace NODE_ID):
```bash
grpcurl -plaintext \
  -d '{
    "drive":"dev-drive",
    "id":"NODE_ID",
    "includePayload":true
  }' \
  localhost:38102 \
  io.pipeline.repository.filesystem.FilesystemService/GetNode
```

4) List children of root
- What it does: Lists nodes under the root; you should see `hello.txt`.
- Command:
```bash
grpcurl -plaintext \
  -d '{"drive":"dev-drive","parentId":""}' \
  localhost:38102 \
  io.pipeline.repository.filesystem.FilesystemService/GetChildren
```

Note on chunked uploads
- The service supports client-streaming `UploadChunks` for large files. grpcurl isn’t convenient for streaming; prefer a small client for that flow. The immediate-upload path above is sufficient for smoke tests.

---

## B) PipeDoc repository: create stored + get

1) Create a stored PipeDoc
- What it does: Stores a PipeDoc with metadata and returns a storage id plus repository metadata.
- Command:
```bash
grpcurl -plaintext \
  -d '{
    "pipeDoc": {
      "docId": "doc-001",
      "searchMetadata": {
        "title": "Hello Doc",
        "body": "Body content for search"
      }
    },
    "description": "Test PipeDoc",
    "tags": {"tagData": {"project":"dev","type":"sample"}}
  }' \
  localhost:38102 \
  io.pipeline.repository.v1.PipeDocRepositoryService/CreateStoredPipeDoc
```

2) Get stored PipeDoc
- What it does: Retrieves the stored PipeDoc and repository metadata by storage id.
- Command (replace STORAGE_ID):
```bash
grpcurl -plaintext \
  -d '{"storageId":"STORAGE_ID"}' \
  localhost:38102 \
  io.pipeline.repository.v1.PipeDocRepositoryService/GetStoredPipeDoc
```

---

## C) ProcessRequest repository: create stored + get

1) Create a stored ProcessRequest
- What it does: Stores a ModuleProcessRequest (with an embedded PipeDoc) and returns a storage id plus repository metadata.
- Command:
```bash
grpcurl -plaintext \
  -d '{
    "processRequest": {
      "document": {
        "docId": "req-001",
        "searchMetadata": {"title":"Request Doc","body":"Processing body"}
      }
    },
    "name": "test-request",
    "description": "Sample process request",
    "tags": {"tagData": {"env":"dev"}}
  }' \
  localhost:38102 \
  io.pipeline.repository.v1.ProcessRequestRepositoryService/CreateStoredProcessRequest
```

2) Get stored ProcessRequest
- What it does: Retrieves the stored ProcessRequest and repository metadata by storage id.
- Command (replace STORAGE_ID):
```bash
grpcurl -plaintext \
  -d '{"storageId":"STORAGE_ID"}' \
  localhost:38102 \
  io.pipeline.repository.v1.ProcessRequestRepositoryService/GetStoredProcessRequest
```

---

## D) Health and utilities

1) Quarkus HTTP readiness (per service)
- What it does: Returns 200 when the Quarkus app is ready to serve requests.
- Commands:
```bash
# repository-service
curl -sf http://localhost:38102/q/health/ready || echo "not ready"
# opensearch-manager
curl -sf http://localhost:38103/q/health/ready || echo "not ready"
# platform-registration-service
curl -sf http://localhost:38101/q/health/ready || echo "not ready"
```

2) gRPC health (service-wide)
- What it does: Checks overall gRPC health via the standard health service.
- Commands:
```bash
# repository-service
grpcurl -plaintext -d '{"service":""}' localhost:38102 grpc.health.v1.Health/Check
# opensearch-manager
grpcurl -plaintext -d '{"service":""}' localhost:38103 grpc.health.v1.Health/Check
```

3) gRPC reflection helpers (if enabled)
- What it does: Lists available services or describes a symbol.
- Commands:
```bash
# list services (repository-service)
grpcurl -plaintext localhost:38102 list
# describe standard health
grpcurl -plaintext localhost:38102 describe grpc.health.v1.Health
```

4) Consul discovery (opensearch-manager)
- What it does: Shows instances registered in Consul for the opensearch-manager service.
- Command:
```bash
curl -sf http://localhost:8500/v1/health/service/opensearch-manager | jq
```

---

Troubleshooting tips
- If grpcurl fails to connect: ensure the service port is open (e.g., `ss -lntp | rg 38102`) and the Quarkus readiness endpoint returns 200.
- If an Any payload fails to parse, double‑check the `@type` URL and that the target message is on the server’s classpath.
- For large uploads, prefer a client that supports gRPC client‑streaming for `UploadChunks`.

---

## E) Admin: drive/bucket status and dev bucket creation

1) List drive bucket status
- What it does: Lists each drive's alias, resolved bucket name, and S3 headBucket access result.
- Command:
```bash
grpcurl -plaintext -d '{}'   localhost:38102   io.pipeline.repository.filesystem.FilesystemAdminService/ListDriveBucketStatus
```

2) Create missing dev buckets (for seeded drives)
- What it does: Calls CreateDrive for known dev drives to trigger S3 bucket creation when `repository.s3.auto-create-buckets=true`.
- Commands:
```bash
# Create/ensure buckets for default dev drives
for d in pipedocs-drive process-requests-drive process-responses-drive graph-nodes-drive modules-drive; do   grpcurl -plaintext -d '{"name":"'"$d"'","description":"Dev default drive"}'     localhost:38102 io.pipeline.repository.filesystem.FilesystemService/CreateDrive || true; done
```

3) Re-check status
- Command:
```bash
grpcurl -plaintext -d '{}'   localhost:38102   io.pipeline.repository.filesystem.FilesystemAdminService/ListDriveBucketStatus
```

Notes
- In dev, `repository.s3.auto-create-buckets=true` allows the server to create buckets on demand.
- In non-dev, ensure buckets exist ahead of time (no auto-create) and set `bucket_name` when creating drives.


### List services running 
```bash
grpcurl -plaintext -d '{}' localhost:38101 io.pipeline.platform.registration.PlatformRegistration/ListServices
```

### List file bucket status (Admin required)
```bash
 grpcurl -plaintext -d '{}' localhost:38102 io.pipeline.repository.filesystem.FilesystemAdminService/ListDriveBucketStatus
```

### Resolve address via registration (repo service)

```bash
grpcurl -plaintext -d \
      '{"serviceName":"repository-service","preferLocal":true}' \
      localhost:38101 \
      io.pipeline.platform.registration.PlatformRegistration/ResolveService
```

### List stored pipedocs

```bash
grpcurl -plaintext -H 'x-target-backend: repository-service' -d \
      '{"pagination":{"pageSize":10}}' localhost:38106 \
      io.pipeline.repository.v1.PipeDocRepositoryService/ListStoredPipeDocs
```


### Workflow - create and list pipedoc

- Create a stored PipeDoc
```bash
grpcurl -plaintext -d '{
      "pipeDoc": {
      "docId": "doc-001",
      "searchMetadata": {"title": "Hello Doc", "body": "Body content"}
      },
      "description": "Test PipeDoc",
      "tags": {"tagData": {"project": "dev", "type": "sample"}}
      }' \
      localhost:38102 io.pipeline.repository.v1.PipeDocRepositoryService/CreateStoredPipeDoc

```
List again 
```bash
grpcurl -plaintext -d '{"pagination":{"pageSize":10}}' \
      localhost:38102 io.pipeline.repository.v1.PipeDocRepositoryService/ListStoredPipeDocs
```
Get by storageId (replace STORAGE_ID from the create response)
```bash
grpcurl -plaintext -d '{"storageId":"STORAGE_ID"}' \
      localhost:38102 io.pipeline.repository.v1.PipeDocRepositoryService/GetStoredPipeDoc
```


## E) Search

This section collects the grpcurl calls we used while wiring up search via OpenSearch. It covers the three layers: OpenSearch Manager (low-level search), FilesystemService (repository facade), and PipeDocRepositoryService (metadata-only search for PipeDocs).

Assumptions
- repository-service gRPC: `localhost:38102`
- opensearch-manager gRPC: `localhost:38103`
- Default PipeDoc drive: `pipedocs-drive` (adjust if your drive differs)

1) Seed a few PipeDocs for search demos
- What it does: Creates three stored PipeDocs with simple titles/body and metadata tags.
- Commands (bash helper to create three docs):
```bash
create_doc(){ idx=$1; grpcurl -plaintext -d '{
  "pipeDoc": {
    "docId": "demo-'"$idx"'",
    "searchMetadata": {"title":"SearchDemo '"$idx"'","body":"This is body '"$idx"' for search pagination"}
  },
  "tags": {"tagData": {"category":"report","series":"demo"}},
  "description": "Doc '"$idx"' for search demo"
}' localhost:38102 io.pipeline.repository.v1.PipeDocRepositoryService/CreateStoredPipeDoc; }

create_doc 1; create_doc 2; create_doc 3;
```

2) OpenSearch Manager (direct) – FilesystemMeta search
- What it does: Runs the underlying OpenSearch-backed search. Useful to debug query behavior independent of repository layers.
- Basic search (no filters):
```bash
grpcurl -plaintext -d '{
  "drive":"pipedocs-drive",
  "query":"SearchDemo",
  "pageSize": 2
}' localhost:38103 io.pipeline.opensearch.v1.OpenSearchManagerService/SearchFilesystemMeta
```
- With metadata filters (currently a no-op until filter mapping is implemented):
```bash
grpcurl -plaintext -d '{
  "drive":"pipedocs-drive",
  "query":"SearchDemo",
  "pageSize": 2,
  "metadataFilters": {"category":"report"}
}' localhost:38103 io.pipeline.opensearch.v1.OpenSearchManagerService/SearchFilesystemMeta
```

3) Repository facade – FilesystemService.SearchNodes
- What it does: Calls the repository-service API that proxies to OpenSearch Manager. Today this is a stub/passthrough; we’ll expand it to support filters, pagination tokens, and highlights.
- Page 1:
```bash
grpcurl -plaintext -d '{
  "drive":"pipedocs-drive",
  "query":"SearchDemo",
  "pageSize": 2
}' localhost:38102 io.pipeline.repository.filesystem.FilesystemService/SearchNodes
```
- Page 2 (use next_page_token once implemented):
```bash
grpcurl -plaintext -d '{
  "drive":"pipedocs-drive",
  "query":"SearchDemo",
  "pageSize": 2,
  "pageToken": "<paste_next_page_token>"
}' localhost:38102 io.pipeline.repository.filesystem.FilesystemService/SearchNodes
```
- With metadata filters (pending full support):
```bash
grpcurl -plaintext -d '{
  "drive":"pipedocs-drive",
  "query":"SearchDemo",
  "pageSize": 2,
  "metadataFilters": {"category":"report"}
}' localhost:38102 io.pipeline.repository.filesystem.FilesystemService/SearchNodes
```

4) PipeDoc metadata-only – PipeDocRepositoryService.SearchPipeDocs
- What it does: Returns metadata-only PipeDoc search results, backed by SearchNodes. Hydration to full docs continues via `GetStoredPipeDoc`.
- Page 1:
```bash
grpcurl -plaintext -d '{
  "query":"SearchDemo",
  "pagination": {"pageSize": 2}
}' localhost:38102 io.pipeline.repository.v1.PipeDocRepositoryService/SearchPipeDocs
```
- Page 2 (use next_page_token once surfaced):
```bash
grpcurl -plaintext -d '{
  "query":"SearchDemo",
  "pagination": {"pageSize": 2, "pageToken":"<paste_next_page_token>"}
}' localhost:38102 io.pipeline.repository.v1.PipeDocRepositoryService/SearchPipeDocs
```
- With metadata filters (pending full support end-to-end):
```bash
grpcurl -plaintext -d '{
  "query":"SearchDemo",
  "metadataFilters": {"category":"report"},
  "pagination": {"pageSize": 2}
}' localhost:38102 io.pipeline.repository.v1.PipeDocRepositoryService/SearchPipeDocs
```

5) Hydrate a search result
- What it does: Uses the storage id to retrieve the full StoredPipeDoc after a metadata-only search. Ensure search returns the actual storage id (UUID) once SearchNodes returns real node ids.
- Command (replace STORAGE_ID with actual node id/UUID):
```bash
grpcurl -plaintext -d '{"storageId":"STORAGE_ID"}'   localhost:38102   io.pipeline.repository.v1.PipeDocRepositoryService/GetStoredPipeDoc
```

Notes
- Current state: SearchNodes is a stub; page_size, next_page_token, filters, and highlights will be wired as we implement real OpenSearch mapping and search_after pagination.
- ID shape: Ensure the index and manager return the node storage id (UUID) so hydration via `GetStoredPipeDoc` works directly. Returning doc_id will cause NotFound on hydration.


## PipeDocs Drive: Common grpcurl Operations

### List drives
```bash
grpcurl -plaintext -d '{}' \
  localhost:38102 \
  io.pipeline.repository.filesystem.FilesystemService/ListDrives
```

### Check the configured PipeDocs drive exists (default: pipedocs-drive)
```bash
grpcurl -plaintext -d '{"name":"pipedocs-drive"}' \
  localhost:38102 \
  io.pipeline.repository.filesystem.FilesystemService/GetDrive
```

### Search for any files under the PipeDocs drive
```bash
grpcurl -plaintext -d '{
  "drive": "pipedocs-drive",
  "types": ["FILE"],
  "pageSize": 20,
  "query": ""
}' \
  localhost:38102 \
  io.pipeline.repository.filesystem.FilesystemService/SearchNodes
```

### If nodes are returned, fetch one by id to confirm payload/unpack works
Replace `NODE_ID` with the id from SearchNodes output.
```bash
grpcurl -plaintext -d '{
  "drive": "pipedocs-drive",
  "id": "0e3cc9c0-d7ac-4462-aa35-5370d70e0f4b"
}' \
  localhost:38102 \
  io.pipeline.repository.filesystem.FilesystemService/GetNode
```

---

If SearchNodes returns nodes but ListStoredPipeDocs still errors for a specific storageId, that’s an orphan reference. You can:

### Rebuild the PipeDocs folder index (calls SearchNodes internally with query="")
```bash
grpcurl -plaintext -d '{"pagination":{"pageSize":10}}' \
  localhost:38102 \
  io.pipeline.repository.v1.PipeDocRepositoryService/ListStoredPipeDocs
```

### If still empty, seed one doc to reestablish baseline
```bash
grpcurl -plaintext -d '{
  "pipeDoc": {
    "docId": "doc-1",
    "searchMetadata": {
      "title": "Seed",
      "body": "first",
      "sourceMimeType": "text/plain"
    }
  }
}' \
  localhost:38102 \
  io.pipeline.repository.v1.PipeDocRepositoryService/CreateStoredPipeDoc
```

### Then list again
```bash
grpcurl -plaintext -d '{"pagination":{"pageSize":10}}' \
  localhost:38102 \
  io.pipeline.repository.v1.PipeDocRepositoryService/ListStoredPipeDocs
```
