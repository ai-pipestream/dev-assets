### Shell Health & Navigation – Implementation Plan (frontend-only)
Clarifying Questions:

1. Task 1 (Health page): The current HealthPage already consumes
   ShellService.watchHealth via the useShellHealth composable. Should I
   enhance it to add the fallback to the /connect/system/health-snapshot
   endpoint when streaming fails?
2. Task 2 (Dynamic navigation): The NavShell component already fetches
   from /connect/system-nav/menu-items.json and handles disabled states. Do
   you want me to enhance this further with periodic refresh or a manual
   refresh button?
3. Task 4 (Service UI normalization): I see references to multiple
   service UIs but the plan mentions starting with 2 at a time. Should I
   start with platform-registration-service and opensearch-manager first
   since they're explicitly mentioned?
4. Shared components: I noticed ServiceStatusCard.vue and
   GrpcHealthStatus.vue in shared-components. Should I use these as the
   HealthCard component mentioned, or create a new one?
5. Base paths: For the service UIs that need normalization, should I
   verify their current Vite/Quinoa configurations match the Traefik routes
   (like /repository/, /opensearch-manager/)?

Clarifying Answers:
Answers to clarifying questions
1. Health fallback
   • Yes. Keep streaming via ShellService.watchHealth; on stream error or timeout, fetch /connect/system/health-snapshot as a
   fallback and display that state until the stream reconnects (auto-retry with backoff).
2. Dynamic navigation refresh
   • Yes. Add a manual “Refresh” button now. Optionally add a lightweight periodic refresh (e.g., every 60s) with cancellation
   on unmount to avoid unnecessary load.
3. Service UI normalization order
   • Yes. Start with platform-registration-service and opensearch-manager first, then proceed to repository-service. That
   sequence gives immediate value and stable targets.
4. Shared Health components
   • Reuse the existing components. Use ServiceStatusCard.vue and GrpcHealthStatus.vue (from shared-components) as the
   HealthCard building blocks. If needed, create a thin wrapper (HealthCard) that standardizes props/styles but do not
   fork/duplicate logic.
5. Base path verification (Vite/Quinoa/Traefik)
   • Yes. For each service UI, verify:
   • Vite:
   • base: '/service-name/'
   • server.host: true
   • dev proxy '/connect' -> http://localhost:38106
   • Quinoa (application.properties):
   • quarkus.quinoa.enabled=true
   • quarkus.quinoa.ui-dir=src/main/ui-vue
   • quarkus.quinoa.build-dir=dist
   • quarkus.quinoa.package-manager=pnpm
   • quarkus.quinoa.package-manager-command.build=run build
   • quarkus.quinoa.dev-server=false
   • quarkus.quinoa.enable-spa-routing=true
   • For services that need a dev root path: %dev.quarkus.http.root-path=/service-name
   • Traefik (dynamic.yml):
   • Router PathPrefix('/service-name') with trailing slash handling (redirect/rewrite)
   • All frontend API calls go through web-proxy '/connect' with x-target-backend where needed.



This document defines the incremental, measurable tasks to implement a consistent Platform Shell (Health, Navigation, Links) across services, without changing backend functionality. It is designed for parallel workstreams and reproducible builds on Linux/macOS.

## Read-first references (code + config to study before starting)
- Web proxy (Connect gateway)
  - `applications/node/web-proxy/src/index.ts`
  - `applications/node/web-proxy/src/routes/connectRoutes.ts` (ShellService.watchHealth, health snapshot, nav items)
  - `applications/node/web-proxy/package.json` (proto:sync, proto:generate scripts)
- Shared frontend libraries
  - `applications/node/libraries/shared-nav` (NavShell and types)
  - `applications/node/libraries/shared-components` (Health/search/upload components; patterns)
  - `applications/node/libraries/proto-stubs` (exported generated services/types; transports)
- Shell app + service UIs (examples of Quinoa/Vite config)
  - `applications/node/platform-shell`
  - `applications/opensearch-manager/src/main/ui-vue`
  - `applications/repository-service/src/main/ui-vue`
- Traefik dev routing
  - `src/test/resources/traefik/dynamic.yml`

## Environment & startup (frontend-only)
- Node 22.x with Corepack; pnpm pinned
  - `corepack enable && corepack prepare "pnpm@10.15.1" --activate`
  - `pnpm -w install --frozen-lockfile`
- Build shared node libs & shell (no Java):
  - `./scripts/initialize-dev-linux.sh --no-gradle`
- Start services for UI work:
  - Optional Traefik: `./scripts/devservices-up.sh`
  - Proxy (clean protos first time): `./scripts/start-web-proxy.sh --clean-protos`
  - Optional live data: `./scripts/start-platform-registration.sh` and any target service

## Scope and constraints
- Frontend-only tasks. Do not modify backend contracts or create new endpoints.
- All UI network calls must go through the `web-proxy` using Connect-RPC (HTTP).
- Respect the per-service base path `/service-name/` for all UIs (Quinoa/Vite).
- Use existing shared components and exports; do not duplicate code or hardcode paths.

## Transport conventions (browser)
- Prefer `createConnectTransport` (from `@connectrpc/connect-web`) with baseUrl set to the proxy path:
  - For apps served under Traefik: baseUrl `"/connect"` (relative)
  - For local proxy dev without Traefik: baseUrl `"http://localhost:38106/connect"`
- When targeting a specific backend, set header `x-target-backend: service-name`.

## Data sources available now
- Health
  - Streaming: `ShellService.watchHealth` (provided by `web-proxy`) – aggregated service health updates.
  - Snapshot (fallback): `GET /connect/system/health-snapshot` (JSON)
- Navigation
  - `GET /connect/system-nav/menu-items.json` (JSON). Items may include `disabled: true` when a service is not resolvable.

## Task list (incremental, measurable)

### 1) Health page (Platform Shell)
- Implement Health view that consumes `ShellService.watchHealth` and renders cards for each known service.
- Fallback to `GET /connect/system/health-snapshot` if streaming fails.
- Visuals: status chip (Serving/Unknown), service name, target endpoint, last updated.
- States: loading, empty (no services), error; auto-reconnect friendly.
- Acceptance:
  - With only `platform-registration-service` running, Health shows it as Connected, others as Unknown/disabled.
  - Stream updates live when services start/stop.

### 2) Dynamic navigation (Platform Shell)
- Fetch items from `/connect/system-nav/menu-items.json` on load and periodically (e.g., 30–60s) or via refresh button.
- Render via `@pipeline/shared-nav/NavShell`; respect `disabled` and `external` flags.
- Ensure internal links use app base paths (e.g., `/repository/`, `/opensearch-manager/`).
- Acceptance:
  - Services not resolvable are greyed out or disabled.
  - External links (e.g., Consul) open in a new tab.

### 3) Links page (Platform Shell)
- Curate a static + dynamic list of useful links (docs, admin UIs) – dynamic items may come from nav feed when present.
- Simple, searchable list with categories.
- Acceptance:
  - Page loads under shell route; links open correctly.

### 4) Normalize shell layout across apps (each service UI)
- Adopt `NavShell` header/drawer in:
  - `platform-registration-service`, `opensearch-manager`, `mapping-service`, `repository-service`, and module UIs (echo, parser, chunker, embedder, sink).
- Base path correctness:
  - Vite `base` matches `/service-name/`. Quinoa: `quarkus.quinoa.ui-dir`, `build-dir`, `package-manager`, `enable-spa-routing=true`, `dev-server=false`.
- Acceptance:
  - Each app renders with consistent top bar/nav; routes work under Traefik and direct dev.

### 5) Shared components integration
- HealthCard: reusable card for service status (colors/icons consistent).
- SearchPanel: embed where appropriate (e.g., `opensearch-manager`, `repository-service`).
- UploadPanel (future): integrate into repository UI for single/bulk uploads.
- Acceptance:
  - Components render and function identically across apps; no local forks.

### 6) Error handling & UX polish
- Uniform alert/snackbar patterns (Vuetify) for network errors and empty states.
- Spinner/placeholder standards.
- Acceptance:
  - No raw errors; clear, consistent messaging.

### 7) CI & reproducibility checks (frontend)
- Add a CI job (or local script) that runs:
  - `./scripts/initialize-dev-linux.sh --no-gradle`
  - Builds all Node libs and UIs referenced by Quinoa
- Acceptance:
  - Clean build passes on a fresh environment without manual steps.

## Implementation guidelines
- Imports & packages
  - Use workspace packages (e.g., `@pipeline/shared-nav`, `@pipeline/shared-components`, `@pipeline/proto-stubs`).
  - Avoid absolute paths; no machine-specific configs.
- Connect clients
  - Browser: `createConnectTransport`; set `x-target-backend` when needed.
  - Do not call backends directly; always through `web-proxy`.
- Base paths
  - Ensure Vite `base` and Quinoa `root-path` align with `/service-name/`.
- No backend changes
  - Do not add/modify endpoints; rely on existing `web-proxy` routes and service contracts.

## Branching & work distribution
- Create feature branch: `feat/shell-health-nav`
- Safe parallelization:
  - Health page & Dynamic nav can proceed immediately (backend already exposes endpoints).
  - Links page & layout normalization can run concurrently.
- PR checkpoints:
  - PR1: Health page streaming + fallback complete.
  - PR2: Dynamic nav consumption + disabled state.
  - PR3: Links page.
  - PR4+: Normalize two service UIs at a time to the shared shell.

## Acceptance criteria (overall)
- Shell Health shows live status for all registered services with graceful degradation.
- Dynamic nav reflects resolvable services; disabled when unavailable.
- Links page present and useful.
- Two service UIs updated to shared shell layout with correct base paths; no routing regressions.
- Frontend builds clean on fresh machine (Linux/macOS) following the Environment steps.

## Troubleshooting quick notes
- Proxy fails with missing stubs: start with `./scripts/start-web-proxy.sh --clean-protos`.
- Health streaming 500: ensure `platform-registration-service` is running (or use snapshot).
- Vite/Quinoa base path 404s: verify Vite `base` and Traefik routes match `/service-name/`.
- Type mismatches: import from `@pipeline/proto-stubs` and prefer generated service exports provided there.
