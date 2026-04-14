# 00 — Source of truth

The ai-pipestream platform has three single-source-of-truth locations. When something disagrees with the README, **the code in these locations wins**.

## 1. `reference-code/` — the authoritative reference for open-source dependencies

Location: sibling to the rest of the platform repos at the top level of the workspace (`../../../reference-code/` relative to this file; typically `$WORKSPACE/reference-code/` on a developer machine).

This folder holds vendored copies of the open-source projects the platform builds on, pinned to the versions the platform actually uses. Current contents include at minimum:

- `reference-code/quarkus/` — Quarkus source at the version pinned in `pipestream-platform/gradle.properties`
- `reference-code/apicurio-registry/` — Apicurio Registry source
- `reference-code/wiremock-grpc-extension/` — the grpc-wiremock extension the platform uses

The full manifest lives in `dev-tools/dev-assets/scripts/config/reference-repos.tsv`, and the `reference-code-sync.sh` script is responsible for populating and updating the tree. New developers should be able to run a single command to check out every repo in that manifest — see `dev-tools/dev-assets/scripts/reference-code-sync.sh`.

**The rule:** when answering "how does Quarkus do X" or "what does Apicurio option Y mean" or "which wiremock-grpc pattern fits this case", grep `reference-code/` before opening a browser tab. Web results will give you the wrong version at least half the time.

Concretely, from the workspace root:

```bash
# Find the Quarkus source for a build item you're not sure about:
grep -rn "ExtensionSslNativeSupportBuildItem" reference-code/quarkus/
```

When you cite a behavior in code review, cite the vendored file — `reference-code/quarkus/extensions/grpc/runtime/src/main/java/.../GrpcServerRecorder.java:147` — not a URL.

**If a feature isn't in `reference-code/`, it isn't in our Quarkus.** Upgrading pulls new code into the vendored copy; until that happens, don't rely on features that don't exist there yet.

## 2. `pipestream-protos` — the only place `.proto` files live

Location: `core-projects/pipestream-protos/` in the workspace.

Every `.proto` file in the platform lives in `pipestream-protos`. It is organized as a multi-module Buf workspace (21 modules as of April 2026), each module publishing to `buf.build/pipestreamai/<module>`. Examples:

- `buf.build/pipestreamai/common` — shared data types and events
- `buf.build/pipestreamai/registration` — `PlatformRegistrationService`
- `buf.build/pipestreamai/repo` — pipedoc, document, graph
- `buf.build/pipestreamai/parser` — Tika and Docling parsers
- `buf.build/pipestreamai/opensearch` — opensearch manager, chunking, embeddings

**Rules:**

- **Services and modules never define their own `.proto` files.** If you need a new message or RPC, open a PR against `pipestream-protos`, merge it, publish, and then bump the version in the consuming project.
- **Consumers pull protos via `quarkus-buf-grpc-generator`**, never by copying files. See [`01-protobufs-apicurio-grpc.md`](01-protobufs-apicurio-grpc.md).
- **Breaking changes run through `buf breaking`** before they land. The Buf workspace is configured to check `FILE`-level breaking rules.
- **Linting is STANDARD.** No field renames, no tag renumbering, no "temporary" changes that would break the BSR contract.

## 3. `pipestream-platform` — the BOM and every Quarkus extension

Location: `core-projects/pipestream-platform/` in the workspace.

`pipestream-platform` owns:

- **The BOM** (`bom/build.gradle`). Every downstream project imports `ai.pipestream:pipestream-bom:<version>` and does not pin pipestream library versions individually. The BOM strictly overrides a few upstream versions (Apicurio Registry in particular) that differ from the Quarkus platform defaults.
- **Every Quarkus extension** the platform ships. See [`03-platform-extensions.md`](03-platform-extensions.md) for what each one does. Downstream projects consume them with `implementation 'ai.pipestream:<extension-name>'` (no version — the BOM manages it).
- **The canonical `gradle.properties`** with the pinned Quarkus version. When upgrading Quarkus, the upgrade happens here first, and downstream projects pick it up by bumping `pipestreamBomVersion`.

**Rules:**

- **Never fork an extension into a service repo.** If you need a capability an extension doesn't provide, add it to the extension or propose a new one.
- **Never pin Quarkus or Apicurio versions in a downstream project.** The BOM owns those.
- **Never add `ai.pipestream:*` dependencies without the BOM.** If you see a project doing this, fix it.

## Why three SSOTs instead of one

They cover different axes:

- `reference-code/` answers "how does this open-source thing actually behave at our version"
- `pipestream-protos` answers "what is the contract between our services"
- `pipestream-platform` answers "what can I get for free from the platform"

Conflating them tends to produce duplicate proto files or inline versions that drift. Keep them separate, keep them authoritative.

## The pipeline project is deprecated

The top-level `pipeline` project (predecessor to the current multi-project layout) is deprecated. New work lands in `pipestream-platform`, `pipestream-protos`, or a service/module repo under `core-projects/` or `modules/`. If you find yourself editing `pipeline`, stop and ask whether the work belongs elsewhere.
