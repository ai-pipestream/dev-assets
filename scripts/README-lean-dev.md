# Lean / remote-infra dev profile

Run the JVM services on a memory-constrained box (e.g. a 24 GB laptop) while
OpenSearch, Redis, DJL serving, and Docling live on a NAS / remote host.

## Files
- `setup-mac.sh` — prompts for an install root (default `~/work`), writes a
  per-machine `~/.config/ai-pipestream/workspace.toml` override, clones+builds
  the repos there, seeds `~/.pipeline`, then runs `configure-external.sh`.
- `configure-external.sh` — prompts for each external endpoint, **live-tests**
  it, and writes a delimited block into `~/.pipeline/dev/.env`. Idempotent.
- `templates/redis.compose.yml` — 10 GB Redis (Portainer / `docker compose`).
- `templates/compose-devservices.override.lean.yml` — copy to
  `~/.pipeline/compose-devservices.override.yml` to stop the local
  OpenSearch/Redis/UI/observability containers (keeps Kafka + Apicurio +
  Postgres + Consul + SeaweedFS local).
- `templates/external-defaults.env.example` — copy to
  `~/.pipeline/dev/external-defaults.env` and set your real hostnames there
  (machine-local, never committed); `configure-external.sh` sources it for
  prompt defaults.

## Quick start (remote dev box)
```bash
git clone https://github.com/ai-pipestream/dev-assets.git
cp dev-assets/scripts/templates/external-defaults.env.example ~/.pipeline/dev/external-defaults.env  # optional: pre-fill hosts
dev-assets/scripts/setup-mac.sh
cp dev-assets/scripts/templates/compose-devservices.override.lean.yml ~/.pipeline/compose-devservices.override.yml
dev-services up
process-compose -f ~/.pipeline/dev/process-compose.yaml up
```

## Test just Redis
Deploy `templates/redis.compose.yml` on the NAS, then:
```bash
( exec 3<>/dev/tcp/<host>/6379; printf 'PING\r\n' >&3; head -c 16 <&3 )   # expect +PONG
```
