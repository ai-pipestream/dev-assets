# OpenSearch NAS stack

Single-node OpenSearch tuned for bulk ingest. Designed to run on the
ai-pipestream LAN NAS and serve every dev machine on the network.

## What's in here

- `docker-compose.yml` — three services:
  - `opensearch` — OpenSearch 3.5.0, 32 GB heap, security disabled, mlockall on
  - `opensearch-dashboards` — UI on port 5601
  - `init-templates` — one-shot sidecar that applies a low-priority default
    index template (6 shards / 0 replicas / 30 s refresh / best_compression)

## Why single node and not a 3-node cluster on the same host

Multiple OpenSearch instances on the same physical box share CPU, disk, and
RAM, and add coordination overhead (serialization across the loopback). They
do **not** index faster than one well-tuned node. Multi-node only helps when
the nodes are on separate hardware (HA) or when you specifically want to test
shard-rebalancing behavior. For bulk ingest on a single big NAS, run one node
and add shards.

## Deploying via Portainer

1. **Stacks → Add stack → Web editor** (or Repository if you point Portainer
   at this dev-assets repo).
2. Paste `docker-compose.yml` into the editor.
3. (Optional) under **Environment variables**, set any of:
   - `OS_VERSION` — image tag, default `3.5.0`
   - `OS_HEAP` — JVM heap, default `32g` (don't exceed 32 g — compressed-oops cutoff)
   - `OS_DEFAULT_SHARDS` — primary shards per new index, default `6`
   - `OS_DEFAULT_REPLICAS` — replicas per new index, default `0`
   - `OS_DEFAULT_REFRESH` — refresh interval for new indexes, default `30s`
   - `OS_REST_PORT` — host port for `:9200`, default `9200`
   - `OS_DASHBOARDS_PORT` — host port for `:5601`, default `5601`
   - `OS_PERF_PORT` — host port for performance-analyzer `:9600`, default `9600`
   - `OS_CLUSTER_NAME` / `OS_NODE_NAME` — defaults `pipestream-nas` / `opensearch-nas`
4. **Set the data volume** (this is the one thing you should NOT leave on the
   default). Two options:
   - **In the editor**: replace the `volumes:` block at the bottom with the
     bind-mount snippet shown there, pointing at your big drive.
   - **In Portainer's "Volumes" tab**: edit the `opensearch-data` volume to
     bind-mount your NAS path before deploying.
   First create the directory and chown to uid 1000 (the OpenSearch user):
   ```bash
   sudo mkdir -p /volume1/docker/opensearch/data
   sudo chown -R 1000:1000 /volume1/docker/opensearch/data
   ```
5. **Deploy the stack.**
6. Wait ~60 s for OpenSearch to be healthy (Portainer shows green dot). The
   `init-templates` sidecar exits with status 0 once the template is applied.
7. Browse: `http://<nas-ip>:5601` for Dashboards; `curl http://<nas-ip>:9200`
   for the REST API.

## Pointing the dev environment at it

Edit `~/.pipeline/dev/.env` on each dev box:

```
OPENSEARCH_HOST=<nas-ip>
OPENSEARCH_PORT=9200
OPENSEARCH_HOSTS=<nas-ip>:9200
OPENSEARCH_PROTOCOL=http
OPENSEARCH_SSL_VERIFY=false
```

(Drop the `OPENSEARCH_USERNAME` / `OPENSEARCH_PASSWORD` and SSL settings —
this stack runs the security plugin disabled to match the local dev pattern.)

## Tuning notes for ingest throughput

The default template gives every new index 6 shards / 0 replicas / 30 s
refresh. That's a reasonable middle ground. For specific bulk-ingest jobs
where you can afford to lose a few seconds of writes on a host crash, also
apply per-index settings before loading:

```bash
curl -X PUT "http://<nas-ip>:9200/<index>/_settings" -H 'Content-Type: application/json' -d '{
  "index": {
    "refresh_interval": "-1",
    "translog.durability": "async",
    "translog.sync_interval": "30s"
  }
}'
```

Bulk-load, then reset:

```bash
curl -X PUT "http://<nas-ip>:9200/<index>/_settings" -H 'Content-Type: application/json' -d '{
  "index": {
    "refresh_interval": "30s",
    "translog.durability": "request"
  }
}'
curl -X POST "http://<nas-ip>:9200/<index>/_forcemerge?max_num_segments=1"
```

Client side: parallel bulk requests (one worker per shard is a good start),
5–15 MB per batch.

## What this stack deliberately omits

- **gRPC API** (`transport-grpc` / port 9400). AWS managed OpenSearch doesn't
  support it, so the platform is moving back to the REST bulk API.
- **Security plugin / TLS**. Match the local dev pattern. If you want this in
  front of the public internet, put it behind a reverse proxy (Caddy/Nginx)
  with auth — don't enable the plugin in this compose without also setting
  up real certs.
- **Multiple nodes**. See "Why single node" above.
- **OpenSearch ML / KNN plugins**. Both ship in the base image; they're
  available, just not specially configured here.

## Backups

OpenSearch has a snapshot API. For NAS-local snapshots, register a
filesystem repo pointing at a path inside the container, then back the
host directory up via your NAS's normal snapshot/replication tooling:

```bash
curl -X PUT "http://<nas-ip>:9200/_snapshot/local" -H 'Content-Type: application/json' -d '{
  "type": "fs",
  "settings": { "location": "/usr/share/opensearch/snapshots" }
}'
```

Add a second volume mount for `/usr/share/opensearch/snapshots` if you go
this route. (Not in the default compose because plenty of NAS users will
just snapshot the data volume directly via their NAS UI.)
