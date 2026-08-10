# Seeding a platform

"Seeding" is how a machine's runtime configuration (`~/.pipeline/`) is
hydrated from the git checkouts. The grid never runs from inside a checkout —
it runs from copies, so a workspace can move, rebuild, or disappear without
taking the running rig's config with it. This file is generated from
`dev-assets/config/workspace-docs/SEEDING.md` by the bootstrap — edit it
there, not here.

## The one command

```bash
cd main/dev-tools/dev-assets
./bootstrap.sh seed             # --dry-run to preview, --force to skip backups
```

Idempotent. Re-run it after pulling changes to `pipestream-platform` or
`dev-assets` so the live copies catch up.

## What lands where

Most seeded files come from the platform's dev-services extension —
`pipestream-platform/pipestream-quarkus-devservices/runtime/src/main/resources/`
("platform" below); the rest from `dev-assets/assets/` ("dev-assets").

| Destination | Source | What it is |
|---|---|---|
| `~/.pipeline/compose-devservices.yml` | platform | infra containers (Postgres, Kafka, Apicurio, OpenSearch, …) |
| `~/.pipeline/init-postgres.sql` | platform | Postgres bootstrap DDL |
| `~/.pipeline/dev/process-compose.yaml` | platform | the dev grid: every process, boot waves, restart policy |
| `~/.pipeline/dev/process-compose.env.example` | platform | documented template for `.env` |
| `~/.pipeline/dev/check-*.sh`, `dev-grid-health.sh` | platform | readiness probes and the health gate |
| `~/.pipeline/dev/start-dev-djl.sh` | platform | DJL launcher; skips the container when the DJL URL is remote |
| `~/.pipeline/dev/register-dev-djl-models.sh` | platform | model registration/probe script |
| `~/.pipeline/dev/nvidia-gpu-setup.sh` | platform | GPU host setup |
| `~/.pipeline/dev/dev-grid.sh`, `dev-pane.sh`, `dev-grid-kitty.sh` | dev-assets | tmux/kitty grid launchers |
| `~/.local/bin/dev-services` | dev-assets | docker-compose wrapper for the infra stack |
| `~/.gradle/init.gradle` | dev-assets | repo resolution (Reposilite/Forgejo); carries no secrets |

Everything is a **copy, not a symlink**. `.sh` files get the executable bit
restored after copying.

## `.env` — yours, never overwritten

`~/.pipeline/dev/.env` is generated **once** if missing, then owned by the
machine. Seed never touches an existing one. It carries the machine-local
truth the yaml can't:

- workspace paths (`CORE_SERVICES_DIR`, `MODULES_DIR`, `CONNECTORS_DIR`,
  `FRONTEND_DIR`, per-service worktree overrides)
- `PC_PORT_NUM` — the process-compose API port (default 8765)
- registration wiring (`PIPESTREAM_REGISTRATION_REGISTRATION_SERVICE_HOST`/`PORT`)
- `PROTO_LOCAL_DIR` — protobuf source for the frontend build
- `EMBEDDER_DJL_SERVING_URL` — set it to a non-localhost URL (e.g.
  `https://djl.example.com`) and the grid runs **remote DJL**: no local
  container is launched, the model script probes the remote instead. Real
  hostnames stay in this file only — never in a repo.

Remember: process-compose captures `.env` at `up` time. After editing it,
`dev-down` + `dev-up` — nothing less applies it.

## Drift: hand-edits vs. the repo

```bash
./bootstrap.sh drift    # exits nonzero when any live copy differs from git
```

Run it **before** seeding. A difference means someone hand-edited the running
rig — that is the moment to reconcile the edit into `pipestream-platform` (or
`dev-assets`) through a PR, not to lose it. If you seed over a modified file
anyway, seed backs it up first as `<name>.local-<timestamp>.bak` (`--force`
skips the backup). Stale `.bak` files under `~/.pipeline/` are safe to prune
once reconciled.

## A whole new machine

```bash
git clone https://git.rokkon.com/ai-pipestream/dev-assets \
  /work/main/dev-tools/dev-assets
cd /work/main/dev-tools/dev-assets
./bootstrap.sh all      # check -> clone -> build -> seed -> dev-up -> health gate
```

Per-machine settings (workspace root, maven local path, per-JVM RAM cap, an
alternate tree) go in `~/.config/ai-pipestream/workspace.toml` — only
overridden fields; the repo manifest is inherited from
`dev-assets/config/workspace.toml`.
