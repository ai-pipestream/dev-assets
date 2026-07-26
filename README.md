# dev-assets — the PipeStream workspace bootstrap

This is the repo you clone first. It carries the workspace manifest, the
prerequisite installer, and the one command that turns a bare machine into a
running PipeStream dev environment.

`/work/main` is a **multi-repo workspace**, not a single repo: every directory
under `core-services/`, `modules/`, `connectors/`, `frontend/`, `deploy/` and
`dev-tools/` is its own git repo on the `ai-pipestream` org. There is no root
repo and no submodules, which is why this README lives here — this is the only
repo that knows about all the others.

Source of truth is Forgejo (`git.rokkon.com`); GitHub is a push mirror, never
clone from it.

## One command

```bash
git clone https://git.rokkon.com/ai-pipestream/dev-assets \
  /work/main/dev-tools/dev-assets
cd /work/main/dev-tools/dev-assets
./bootstrap.sh all
```

`all` runs **check → clone → build → seed → dev-up → health gate** and exits
nonzero if the result is not a working dev grid. That last step matters:
`process-compose` returns as soon as it has launched things and stops probing a
process once its readiness budget is spent, so without a gate "it came up" is an
opinion rather than a fact.

Expect the first run to take a while — it clones ~50 repos and compiles the
whole fleet so that 19 cold `quarkus dev` builds do not land on the readiness
critical path afterwards.

Useful variants:

```bash
./bootstrap.sh all --yes                 # no prompts
./bootstrap.sh all --no-dev-up           # set the workspace up, do not start it
./bootstrap.sh all --skip check,clone    # resume a partial run
./bootstrap.sh dev-health                # gate an already-running grid
./bootstrap.sh drift                     # what did I hand-edit in ~/.pipeline?
./bootstrap.sh dev-down                  # stop the grid
```

Configuration is `config/workspace.toml`; per-machine overrides go in
`~/.config/ai-pipestream/workspace.toml`.

## Prerequisites

`./bootstrap.sh check` detects all of these and offers to install the ones it
can. Two are hard stops it will not install for you:

| Tool | Why | Auto-install |
|---|---|---|
| **docker** | all infra runs in containers | no — per-developer setup |
| **git** | it is a multi-repo workspace | no — use your package manager |
| uv | Python tooling | yes |
| sdkman + java 25 | every backend service | yes |
| quarkus CLI | `quarkus dev` is how services run in the grid | yes |
| node 22+ / pnpm | frontend workspace | yes |
| **bun** | the frontend BFF process *is* `bun --watch` | yes |
| **buf** | the frontend's protobuf codegen | yes |
| process-compose | the dev grid supervisor | yes |
| gh (+ auth) | HTTPS git operations, private repos | yes |
| nvidia-container-toolkit | GPU docling/embedder only; skipped on non-NVIDIA hosts | yes |

Optional: `grpcurl` (the health gate's module-catalog check skips without it),
`tmux` + PyYAML (only for the `dev-grid.sh` tmux launcher).

## The two rigs

They run the same platform and **must not run at the same time** — they bind the
same ports and the same `pipeline-*` container names.

**Dev grid (process-compose)** — what `bootstrap all` starts. Every service is a
host-local `quarkus dev` process with hot reload, on top of shared infra
containers. This is the rig for changing code.

```bash
./bootstrap.sh dev-up          # start
./bootstrap.sh dev-health      # is it actually usable?
./bootstrap.sh dev-down        # stop
process-compose attach -p 8765 # the TUI
tail -f ~/.pipeline/dev/logs/<process>.log
```

**Docker stack (`deploy/compose-stack`)** — every service as a built image.
This is the rig for testing what ships.

```bash
cd /work/main/deploy/compose-stack
./build-stack.sh               # build + up + health gate
```

Both consume the *same* infra definition, `compose-devservices.yml`. The dev
grid gets its copy seeded into `~/.pipeline/` from
`pipestream-platform/pipestream-quarkus-devservices/runtime/src/main/resources/`;
`bootstrap.sh drift` tells you when your live copy has diverged from git.

## Ports

Infra (`compose-devservices.yml`):

| What | Port |
|---|---|
| Postgres | 5432 |
| Kafka (host listener) | 9094 |
| Apicurio registry / UI | 8081 / 8890 |
| OpenSearch REST / perf analyzer | 9200 / 9600 |
| OpenSearch dashboards | 5601 |
| S3-compatible storage (rustfs) | 8333 (admin console 9001) |
| Redis | 6379 |
| kafka-ui | 8889 |
| DJL serving | 8090 |
| docling-gpu (profile `gpu`) | 5001 |
| OVMS gRPC (profile `openvino-gpu`) | 9002 |
| Grafana LGTM | 3001 (OTLP 5317/5318) |

Core services (HTTP and gRPC share one port):

| Service | Port |
|---|---|
| engine | 18100 |
| platform-registration | 18101 |
| repository | 18102 |
| opensearch-manager | 18103 |
| account | 18105 |
| connector-admin | 18107 |
| connector-intake | 18108 |
| jdbc-connector | 18121 |
| s3-connector | 18220 |

Modules and frontend:

| Service | Port |
|---|---|
| module-echo | 19100 |
| module-parser | 19101 |
| module-chunker | 19102 |
| module-embedder | 19103 |
| module-opensearch-sink | 19104 |
| module-quality | 19006 |
| module-semantic-graph | 19110 |
| module-testing-sidecar | 19140 |
| frontend BFF | 38106 |
| frontend UI (vite) | 33000 |
| process-compose API/TUI | 8765 |

## When it goes wrong

- **A service is stuck.** `./bootstrap.sh dev-health` names it and why. Then
  `~/.pipeline/dev/logs/<process>.log`.
- **The BFF's Lab features 503.** The `frontend_bff` database is created by
  `init-postgres.sql`, which postgres runs **only on a fresh volume**. On an
  existing volume: `docker exec pipeline-postgres createdb -U pipeline frontend_bff`.
- **Repository calls 500 with NoSuchBucket.** The `rustfs-init` one-shot creates
  the `pipestream` bucket; check it exited 0
  (`docker inspect pipeline-rustfs-init`).
- **`.env` changes did nothing.** process-compose does not re-read
  `~/.pipeline/dev/.env` on `process restart` — full `dev-down` then `dev-up`.
- **A seed overwrote my edit.** It backed it up first:
  `~/.pipeline/dev/<file>.local-<timestamp>.bak`. Run `./bootstrap.sh drift`
  before seeding next time, and port the change into the repo.

## What else is in here

```
assets/dev/        tmux grid launchers (alternative to process-compose)
config/            workspace.toml — the repo manifest
docker/            standalone opensearch / redis compose files
docs/standards/    the written standards (start at docs/standards/README.md)
installers/        docling + DJL installers
scripts/           bootstrap implementation and its tests
```

Workspace rules and the platform mental model live in `/work/main/AGENTS.md`;
testing conventions in `/work/main/CLAUDE.md`.

## Contributing

Run the tests before pushing: `pytest scripts/tests -q`. Anything that changes
what a fresh machine gets — the manifest, the prereq list, the seeded files —
needs a test in `scripts/tests/`, because the failure mode is always "it works
here".
