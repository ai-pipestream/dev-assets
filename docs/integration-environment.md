# The integration environment and the release train

How krick-1 became a from-scratch, installer-driven integration box that
mirrors main, and the repeatable plan that fell out of it. Written from the
2026-07-28 bring-up, where every step below was executed and every gotcha was
hit for real. This is the reference for standing up the NEXT box and for the
downstream-CD wiring.

## The model

- One manifest (`config/workspace.toml`), two trees. A per-machine override
  (`~/.config/ai-pipestream/workspace.toml` containing `[workspace]
  tree = "integration"`) relocates the ENTIRE layout to
  `/work/integration/<category>/<repo>`. `/work/main` stays a dev tree;
  the integration tree is disposable and rebuildable from the installer.
- Runtime mirrors main two ways, in order of fidelity:
  1. **Dev grid** (process-compose, `quarkus dev` from the integration
     checkouts): proves source-level main.
  2. **Container stack** (compose-stack, every `*_TAG=snapshot` from the
     Forgejo registry): proves the published snapshot images, i.e. exactly
     what downstream CD would deploy after a green main build.

## The recipe (all through the installer)

```bash
# 0. teardown: docker compose -p <project> down for every project, THEN
#    verify: docker ps -a empty, grid ports silent. Never docker rm -f a
#    compose project's containers (stale ids poison the next up), never
#    pkill process-compose (orphaned JVMs keep ports and fake green gates).
git clone https://git.rokkon.com/ai-pipestream/dev-assets.git /work/integration/dev-tools/dev-assets
printf '[workspace]\ntree = "integration"\n' > ~/.config/ai-pipestream/workspace.toml
cd /work/integration/dev-tools/dev-assets
TMPDIR=/work/tmp bash -ic './bootstrap.sh all --yes --no-dev-up'   # check, clone, build, seed
bash -ic './bootstrap.sh reference-sync'                            # OSS upstreams, parallel-safe
# hand-edit ~/.pipeline/dev/.env: machine hardware facts ONLY (see below)
bash -ic './bootstrap.sh dev-up && ./bootstrap.sh dev-health --wait 1500'
bash -ic './bootstrap.sh e2e-smoke'    # goldenPath + demoJdbcSeed, live leg
```

`bash -ic` matters on a headless box: java (sdkman) and node/pnpm (nvm) are
interactive-shell-only. `TMPDIR=/work/tmp` matters until the /tmp-on-NVMe
fstab bind is live (tmpfs usrquota killed CI for two days; never build on
quota'd tmpfs).

### The .env: what is machine-specific (and what is NOT)

The seed now generates everything layout-derived (workspace dirs,
FRONTEND_DIR, EMBEDDER_DJL_SERVING_URL, the OpenSearch triplet,
OVMS_RENDER_GID auto-detect). The hand-written hardware block reduced to:

```bash
MODULE_PARSER_DOCLING_DEVSERVICES_ENABLED=true   # host has no NVIDIA
VITE_ALLOWED_HOSTS=<hostname>
```

Everything else that used to be hand-tuned is now auto-detected or was
actively harmful: the old openvino-gpu compose profile + hand EMBEDDER_*
overrides double-started OVMS and clobbered the auto-detected routing.
`start-dev-djl.sh` owns backend selection: NVIDIA -> DJL GPU; Intel ->
OVMS (GPU) + DJL (CPU) side by side; else DJL CPU. The env_file it writes
is the single source of embedding routing.

### The stack cutover

```bash
bash -ic './bootstrap.sh dev-down'      # verify ports silent afterwards
cd /work/integration/deploy/compose-stack
# .env: every *_TAG=snapshot, IMAGE_REGISTRY=git.rokkon.com,
# IMAGE_NAMESPACE=ai-pipestream, fresh PIPESTREAM_SECRETS_LOCAL_KEY,
# OVMS_HOST/OVMS_GRPC_HOST_PORT for the surviving pipeline-ovms.
docker compose -p pipestream-stack --env-file .env \
  -f docker-compose.stack.yml -f docker-compose-cpu.yaml \
  -f krick1-openvino.override.yml up -d --pull always
# converge: every container healthy or Exited(0); the three UI containers
# (apicurio-ui, kafka-ui, opensearch-dashboards) have no healthcheck.
```

Pre-flight the registry first: `docker manifest inspect
git.rokkon.com/ai-pipestream/<img>:snapshot` for every service (verify by
resolving, never by listing).

### The batteries against the stack

```bash
# sidecar pipeline-crawl e2e (from the integration checkout):
cd /work/integration/modules/module-testing-sidecar
./gradlew quarkusIntTest -PrunPipelineE2E --rerun --no-daemon
# verify from build/test-results/quarkusIntTest XML: tests>0, skipped=0

# FE regression, live leg, STACK ports:
FE_BASE_URL=http://localhost:38106 \
REGRESSION_ENGINE_GRPC=http://localhost:38100 \
REGRESSION_LEG=live pnpm -C apps/pipestream-frontend test:regression
```

The stack publishes engine on 38100 (dev grid: 18100); without
`REGRESSION_ENGINE_GRPC` the teardown specs dial a dead port.

## Verified results (2026-07-28, krick-1)

- Dev grid: full OOTB cycle green through the installer alone;
  `e2e-smoke` (goldenPath 8/8 + demoJdbcSeed 8/8) green via `bootstrap.sh`.
- Stack (all-snapshot): 37 healthy + 2 clean one-shots + 3 UI containers;
  sidecar battery 6/0/0/0 (simple, sentence-completeness, complex plans);
  FE live leg 129+ passing, with one open product finding (below).

## Version skew and the snapshot cascade (release-train facts)

- Snapshot images tag `snapshot` + `main-<sha>`; the sidecar only gained its
  snapshot publish on 2026-07-28 (its arm64 leg had been silently killing
  the manifest for weeks: a mixed-version stack then fails crawls with
  `root_table is required`, the exact skew the mirrors-main model prevents).
- After a RELEASE, axion advances every snapshot: protos 0.8.12 tag ->
  0.8.13-SNAPSHOT stubs, platform 0.7.44 tag -> 0.7.45-SNAPSHOT BOM. Any
  proto change after the release therefore needs the pin cascade: platform
  libs.versions.toml stubs pin, then each consumer's pipestreamBomVersion.
  Consumers still pinning the pre-release snapshot resolve a FROZEN jar and
  silently never see new fields.

## Open items

- Downstream-CD trigger: wire a Forgejo workflow (or krick-1 cron) that
  re-pulls `:snapshot` and recreates the stack after main builds; today the
  refresh is manual (`docker compose ... up -d --pull always`).
- opensearch#59: trace projection exceeds the goldenPath 240s window on the
  containerized stack (attribution correct, just slow); the goldenPath spec
  deliberately treats that as a throughput regression.
- semantic-graph got the provider abstraction (its #23); once its snapshot
  carries it, revert the Intel dual-DJL mode (platform #86) to OVMS-only.
- build-stack.sh has no extra-override hook; the krick-1 stack is driven
  with a raw docker compose command instead of the health-gated script.
