# PipeStream workspace — agent orientation

This directory is the workspace root of a **multi-repo** workspace: every
directory under `main/core-services/`, `main/modules/`, `main/connectors/`,
`main/frontend/`, `main/deploy/`, `main/dev-tools/` and `main/grpc-services/`
is its own git repository. There is no root repo and no submodules. This file
is generated from `dev-assets/config/workspace-docs/AGENTS.md` by the
bootstrap — edit it there, not here.

## First moves in any session

```bash
source ./env.sh        # from the workspace root
```

That puts the workspace toolchain (bun, process-compose) on PATH and points
Gradle/Maven at the caches that live on this disk. Builds run without it will
use the machine-global `~/.gradle`/`~/.m2` and may not resolve internal
artifacts at all.

## Ground rules

- **Source of truth is Forgejo** (`git.rokkon.com/ai-pipestream`). GitHub is a
  push mirror — never clone from or push to it. Exception: the
  `grpc-services/` category is GitHub-hosted; see its own `AGENTS.md`.
- **All changes go through PRs.** Branch, push to Forgejo, open the PR there.
  `FORGEJO_TOKEN` lives in the developer's `~/.zshrc` — source it to use the
  API, and never print it.
- **Commit hooks reject AI attribution.** Commit without `Co-Authored-By`
  or session-link trailers.
- **No Mutiny.** The stack runs on virtual threads; write blocking code, and
  tests use blocking gRPC stubs. Do not introduce reactive types.
- **No `new ServerSocket(0)` port-picking in test profiles** — it races.
  Let the OS assign ports (`quarkus.http.test-port=0` and friends).
- **Secrets and private hostnames are environment-only.** Real internal URLs
  (e.g. the remote DJL serving host) live in `~/.pipeline/dev/.env`; repo
  docs and code use `*.example.com` placeholders. Never commit a real one.
- `main/reference-code/` holds vendored OSS upstreams. Read them, never build
  or modify them; they are excluded from every fleet-wide script.

## Layout

```
env.sh                    activate the workspace (source it)
run-tests.sh              gradlew test across the fleet, serial on purpose
run-integration-tests.sh  gradlew quarkusIntTest across the fleet, serial
main/<category>/<repo>    one git repo each; some categories carry AGENTS.md
main/dev-tools/dev-assets the bootstrap repo — the only repo that knows all
                          the others (manifest: config/workspace.toml)
reposilite/               local artifact mirror (docker compose; port 8084)
tools/                    pinned toolchain (bun, process-compose)
```

Test scripts run **serially** because every suite is Testcontainers-backed
and the Docker VM has limited memory — parallel repos OOM it and the failures
look like flakes. `TESTCONTAINERS_REUSE_ENABLE=false` (set by `env.sh`) is
load-bearing for the same reason: reused containers leak state between suites.

## The bootstrap (updates, builds, seeding)

Everything fleet-wide goes through `main/dev-tools/dev-assets/bootstrap.sh`:

```bash
cd main/dev-tools/dev-assets
./bootstrap.sh clone --update   # fast-forward every repo in the manifest
./bootstrap.sh build            # re-warm: publishToMavenLocal on the BOM/
                                # platform repos, gradlew classes on the rest,
                                # pnpm install+codegen+build for the frontend
./bootstrap.sh drift            # what was hand-edited under ~/.pipeline?
./bootstrap.sh seed             # refresh ~/.pipeline from the checkouts
./bootstrap.sh all              # bare machine -> running, health-gated grid
```

**After pulling changes across the fleet, run `clone --update` then `build`.**
Run `drift` before `seed`, and reconcile hand-edits back into the repos
instead of letting seed back them up. Seeding is documented in `SEEDING.md`
next to this file.

## The dev grid

The runtime is a process-compose stack (~20 processes: infra, core services,
connectors, modules, frontend) driven from `~/.pipeline/dev/`:

```bash
./bootstrap.sh dev-up           # start (refuses if declared ports are held)
./bootstrap.sh dev-health       # health gate — exit nonzero when wrong
./bootstrap.sh dev-down         # stop
process-compose attach -p 8765  # live TUI; q detaches — F10 KILLS the grid
```

Operational facts that bite:

- **`.env` is captured at `up` time.** Editing `~/.pipeline/dev/.env` does
  nothing until a full `dev-down` + `dev-up`; per-process restarts and
  `project update` inherit the server's original environment.
- Boot order is staged with `depends_on: process_healthy` waves. A process
  that exhausts its restart budget sits "Completed" and its dependents sit
  "Skipped" — recover with
  `process-compose process restart <name> -p 8765`, dependency-order.
- Quarkus dev mode does **not** hot-reload Quarkus *extension* jars. After
  changing an extension (e.g. under `pipestream-platform` or the embedder
  extension), restart the consuming process.
- Services register with platform-registration over gRPC; the health gate
  (`dev-health` or `~/.pipeline/dev/dev-grid-health.sh`) is the fact of
  record, not "process-compose said Running".

## Frontend

`main/frontend/pipestream-frontend` runs on bun/pnpm. It needs
`PROTO_LOCAL_DIR` pointing at the `pipestream-protos` checkout (env.sh and
the grid `.env` both set it) or the fresh-clone guard kills the BFF at boot.
The BFF runs under `bun --watch`: it restarts on every file save.
