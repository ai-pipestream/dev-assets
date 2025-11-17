# MCP (Model Context Protocol) – Dev Manual

This manual shows how to exercise the Repository Service’s MCP server from the command line using curl, validate gRPC health (what Consul uses), and hook up stdio-only clients (Codex) via the stdio→SSE proxy. It focuses on fast, repeatable dev flows and error diagnosis.

## Prerequisites

- Run the Repository Service in dev: `./gradlew :applications:pipedoc-repository-service:quarkusDev`
- Default HTTP port: `38102` (change if you’ve customized it)
- MCP endpoints (Quarkus dev):
  - Streamable HTTP: `http://localhost:38102/mcp`
  - SSE stream: `http://localhost:38102/mcp/sse`

Notes:
- For Streamable HTTP (`/mcp`), the Accept header MUST include both `application/json` and `text/event-stream`.
- Consul checks gRPC health — see the grpcurl section below.

## Streamable HTTP via curl

The Streamable HTTP transport uses JSON-RPC over plain HTTP. The flow is:
1) initialize → server returns capabilities and an MCP session id in the response header
2) notifications/initialized → client confirms init
3) tools/prompt/resource requests
4) DELETE to terminate the session

Set a base URL for your environment:

```bash
# From the host:
export BASE=http://localhost:38102/mcp

# From inside a container (default Docker bridge example):
# BASE=http://172.17.0.1:38102/mcp
```

Initialize (step 1):

```bash
curl -sS -D /tmp/mcp_init_headers.txt -o /tmp/mcp_init_body.json \
  -X POST "$BASE" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data-raw '{
    "jsonrpc":"2.0",
    "id":"init-1",
    "method":"initialize",
    "params":{
      "protocolVersion":"2025-03-26",
      "clientInfo":{"name":"curl","version":"0.1"},
      "capabilities":{}
    }
  }'

echo "Init body:" && cat /tmp/mcp_init_body.json && echo
SESSION=$(awk -F': ' 'tolower($1)=="mcp-session-id" {print $2}' /tmp/mcp_init_headers.txt | tr -d '\r')
echo "SESSION=$SESSION"
```

Confirm initialize (step 2):

```bash
curl -sS -i -X POST "$BASE" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SESSION" \
  --data-raw '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}'
```

List tools:

```bash
curl -sS -X POST "$BASE" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SESSION" \
  --data-raw '{"jsonrpc":"2.0","id":"list-1","method":"tools/list","params":{}}'
```

Call a tool (examples):

```bash
# Tail last 200 dev log lines
curl -sS -X POST "$BASE" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SESSION" \
  --data-raw '{
    "jsonrpc":"2.0","id":"call-1","method":"tools/call",
    "params":{"name":"tailLogs","arguments":{"lines":200}}
  }'

# Recent errors (WARN/ERROR)
curl -sS -X POST "$BASE" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SESSION" \
  --data-raw '{
    "jsonrpc":"2.0","id":"call-2","method":"tools/call",
    "params":{"name":"recentErrors","arguments":{"lines":200}}
  }'

# Set log level for a category
curl -sS -X POST "$BASE" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SESSION" \
  --data-raw '{
    "jsonrpc":"2.0","id":"call-3","method":"tools/call",
    "params":{"name":"setLogLevel","arguments":{"category":"io.pipeline","level":"DEBUG"}}
  }'

# Service health via REST endpoint (JSON)
curl -sS -X POST "$BASE" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SESSION" \
  --data-raw '{"jsonrpc":"2.0","id":"call-4","method":"tools/call","params":{"name":"health","arguments":{}}}'

# Metrics (if Micrometer endpoint enabled)
curl -sS -X POST "$BASE" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SESSION" \
  --data-raw '{"jsonrpc":"2.0","id":"call-5","method":"tools/call","params":{"name":"metrics","arguments":{}}}'
```

Prompts (examples):

```bash
# service_state prompt (dev-only prompt in this repo)
curl -sS -X POST "$BASE" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SESSION" \
  --data-raw '{
    "jsonrpc":"2.0","id":"prompt-1","method":"prompts/get",
    "params":{"name":"service_state","arguments":{"verbose":"true"}}
  }'
```

Terminate the session:

```bash
curl -sS -X DELETE "$BASE" -H "Mcp-Session-Id: $SESSION" -i
```

### Common Errors (Streamable HTTP)

- `400` with `Invalid Accept header` → Include `-H 'Accept: application/json, text/event-stream'`.
- `Client not initialized yet` → Send `notifications/initialized` after `initialize`.
- `404 Mcp session not found` → Invalid/expired `Mcp-Session-Id` or session was terminated.

## SSE transport (for stdio-only clients)

SSE is convenient for IDE/chat integrations and the stdio→SSE proxy. Manual curl of SSE is optional in dev:

1) Use Streamable HTTP (`/mcp`) to establish a session and find the message endpoint (the stdio→SSE proxy handles this automatically).
2) Open SSE stream at `/mcp/sse` with the `Mcp-Session-Id` header to receive events.
3) POST JSON-RPC messages to the provided message endpoint path (e.g., `/mcp/messages/{id}`).

For stdio-only clients (Codex), use the proxy in the next section.

## Codex (stdio) via stdio→SSE proxy

Use JBang to run the proxy, or the helper script in this repo:

```bash
./scripts/mcp-proxy.sh http://localhost:38102/mcp/sse
```

Codex config (`~/.codex/config.toml`):

```toml
[projects."/home/some_user/projects/pipeline"]
trust_level = "trusted"
[projects."/home/some_user/projects/pipeline-engine-refactor"]
trust_level = "trusted"
[mcp_servers.pipedoc-repo-dev]
command = "jbang"
args = ["io.quarkiverse.mcp:quarkus-mcp-stdio-sse-proxy:RELEASE", "http://localhost:38102/mcp/sse"]
```

## gRPC Health (Consul equivalent)

Consul checks gRPC health, not HTTP. Use grpcurl from the container network’s perspective:

```bash
# Example for the default docker bridge
grpcurl -plaintext 172.17.0.1:38102 grpc.health.v1.Health/Check -d '{"service":""}'
```

If your docker network uses a different host-gateway, replace `172.17.0.1` accordingly.

## Troubleshooting

- Streamable HTTP 400: Add the Accept header with both content types.
- `Client not initialized yet`: Always send `notifications/initialized` after `initialize`.
- Session header: Keep and pass the `Mcp-Session-Id` for subsequent calls.
- From containers: Point `BASE` to a host IP your containers can reach (e.g., `http://172.17.0.1:38102/mcp`).
- Check service health: Use `grpcurl` as shown above.

## Programmatic test reference

See `applications/repository-service/src/test/java/io/pipeline/repository/mcp/McpStreamableHttpIT.java`. It performs:

- initialize (with Accept), asserts `Mcp-Session-Id`
- notifications/initialized
- tools/list

All steps log status, headers, and body for clarity when debugging.

