"""Warm the build caches so `process-compose up` is not a compile race.

Three phases, in order:

1. **seed** — `./gradlew publishToMavenLocal` SERIALLY on every
   `build_first=true` repo. The first repo to compile in a fresh tree warms
   ~/.m2 with the platform's transitive dependencies; if several gradle builds
   race to write the same artifacts on a cold cache they intermittently corrupt
   the maven local repository.

2. **prebuild** — `./gradlew classes` on every other gradle repo. Without this,
   19 cold `quarkus dev` builds land on process-compose's readiness-probe
   critical path: each one resolves dependencies, generates code, compiles, and
   augments while a probe with a finite failure_threshold counts down against
   it. process-compose STOPS PROBING once that budget is gone, so a service that
   was merely slow gets parked in `Running` and never recovers. Compiling ahead
   of time is what `sea-of-slop/design-notes/fast-dev-startup-plan.md` calls the
   `dev-services prebuild` step; `classes` is the cheapest task that produces
   compiled output plus a resolved dependency graph (`assemble` would also build
   jars nobody reads here).

3. **frontend** — `pnpm install`, protobuf codegen, `pnpm build`. The dev grid
   runs `bun --watch src/index.ts` for the BFF and `pnpm dev` for the UI; from a
   clean checkout neither has node_modules, and `packages/protobuf-forms` has no
   generated stubs at all. There was no frontend leg here before, which is why
   `bootstrap` could report success and still leave two of the grid's processes
   unable to start.

Failures are collected rather than fatal for phases 2 and 3: one repo that will
not compile should not stop the other eighteen from being warmed. The exit code
still reflects them.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import ui
from .manifest import Repo, Workspace

_SEED_TASK = "publishToMavenLocal"
_PREBUILD_TASK = "classes"

# Repos that are not gradle builds and must never be handed to ./gradlew.
# The frontend has its own phase; the court-fixture and corpus repos are data.
# Written tree-relative (no leading "main"/"integration" segment) so the
# check holds under any workspace.tree.
_NON_GRADLE_PATH_PREFIXES = (
    "frontend",
    "core-services/test-docs",
    "deploy",
)
_NON_GRADLE_NAMES = frozenset({
    "dev-assets",
    "corpus-data",
    "sample-documents",
    "pipestream-protos",
})

FRONTEND_REPO = "pipestream-frontend"


def build_seed(ws: Workspace) -> int:
    """Phase 1 only: publishToMavenLocal on the build_first repos.

    :param ws: the loaded workspace manifest
    :return: 0 on success, else the failing gradle exit code
    """
    seeds = [r for r in ws.repos if r.build_first]
    if not seeds:
        ui.warn("No build_first repos in manifest — nothing to seed.")
        return 0

    ws.m2_repo.mkdir(parents=True, exist_ok=True)

    ui.header("Maven local seed build")
    ui.info(f"Gradle task:  {_SEED_TASK}")
    ui.info(f"Seed repos:   {len(seeds)} ({', '.join(r.name for r in seeds)})")
    ui.info(f"JAVA_HOME:    {_resolve_java_home() or '(not pinned)'}")
    ui.info(f"Maven local:  {ws.m2_repo}")
    ui.plain("")

    for repo in seeds:
        rc = _gradle(repo, ws, _SEED_TASK)
        if rc != 0:
            return rc

    ui.plain("")
    ui.ok(f"All {len(seeds)} seed build(s) published to {ws.m2_repo}.")
    _m2_hint(ws)
    return 0


def build_all(ws: Workspace, skip_frontend: bool = False) -> int:
    """Run all three phases.

    :param ws: the loaded workspace manifest
    :param skip_frontend: when True, stop after the gradle phases
    :return: 0 when every phase succeeded, 1 otherwise
    """
    rc = build_seed(ws)
    if rc != 0:
        ui.error("Seed build failed — not prebuilding the rest of the fleet.")
        return rc

    failures: list[str] = []
    failures += _prebuild_fleet(ws)
    if not skip_frontend:
        failures += _build_frontend(ws)

    ui.plain("")
    if failures:
        ui.header("Build phases with failures")
        for name in failures:
            ui.error(name)
        ui.info("The dev grid can still start; those services will compile on")
        ui.info("  their own critical path (and may exhaust a readiness probe).")
        return 1
    ui.ok("Fleet prebuilt — `quarkus dev` starts from compiled state.")
    return 0


def gradle_repos(ws: Workspace) -> list[Repo]:
    """Repos that phase 2 should prebuild.

    Excludes the build_first seeds (already built), non-gradle data repos, and
    anything with no ``gradlew`` on disk.

    :param ws: the loaded workspace manifest
    :return: repos to prebuild, in manifest order
    """
    out: list[Repo] = []
    for r in ws.repos:
        if r.build_first:
            continue
        if r.name in _NON_GRADLE_NAMES:
            continue
        if any(r.path.partition("/")[2].startswith(p) for p in _NON_GRADLE_PATH_PREFIXES):
            continue
        out.append(r)
    return out


def _prebuild_fleet(ws: Workspace) -> list[str]:
    repos = gradle_repos(ws)
    present = [r for r in repos if (r.dest(ws.root) / "gradlew").exists()]
    missing = [r for r in repos if r not in present]

    ui.header("Fleet prebuild")
    ui.info(f"Gradle task:  {_PREBUILD_TASK}")
    ui.info(f"Repos:        {len(present)} of {len(repos)} on disk")
    if missing:
        ui.warn(f"not cloned yet (skipping): {', '.join(r.name for r in missing)}")
    ui.plain("")

    failures: list[str] = []
    for repo in present:
        if _gradle(repo, ws, _PREBUILD_TASK) != 0:
            failures.append(repo.name)
    return failures


def _build_frontend(ws: Workspace) -> list[str]:
    fe = ws.repo_named(FRONTEND_REPO)
    if fe is None:
        ui.warn(f"{FRONTEND_REPO} missing from manifest — skipping the frontend build.")
        return []
    dest = fe.dest(ws.root)
    if not dest.exists():
        ui.warn(f"{fe.relative_dest()} not cloned yet — skipping the frontend build.")
        return []

    ui.header("Frontend build")
    ui.info(f"cwd: {dest}")

    if not shutil.which("pnpm"):
        ui.error("pnpm not on PATH — run `./bootstrap.sh check` first.")
        return [FRONTEND_REPO]

    env = dict(os.environ)
    steps: list[tuple[str, list[str]]] = [
        ("pnpm install", ["pnpm", "install", "--frozen-lockfile"]),
    ]

    # `pnpm build` already runs the protobuf codegen (packages/protobuf-forms'
    # own `build` is `proto:build && tsup`). The only question is where the
    # .proto files come from, and the committed default is a git clone of
    # pipestream-protos — which is PRIVATE, so a bare bootstrap would stop and
    # ask for a token.
    #
    # `bootstrap clone` already put a checkout of pipestream-protos on disk, so
    # point the codegen at it: PROTO_LOCAL_DIR is the documented no-network
    # source and it takes precedence over the git URL. Nothing to authenticate,
    # nothing to download, and the frontend generates against exactly the protos
    # this workspace is building against.
    protos = _protos_checkout(ws)
    if protos:
        env["PROTO_LOCAL_DIR"] = str(protos)
        ui.info(f"protobuf codegen source: {protos} (local checkout, no network)")
    else:
        ui.warn("pipestream-protos not on disk — codegen falls back to")
        ui.warn("  packages/protobuf-forms/proto-source.env (a git clone of a")
        ui.warn("  private repo; export PROTO_GIT_TOKEN, or fetch the published")
        ui.warn("  tarball with `pnpm -C packages/protobuf-forms proto:sync:tgz`).")

    steps.append(("pnpm build", ["pnpm", "build"]))

    for label, cmd in steps:
        ui.info(f"-- {label} --")
        if subprocess.run(cmd, cwd=str(dest), env=env).returncode != 0:
            ui.error(f"frontend: `{label}` failed")
            return [f"{FRONTEND_REPO} ({label})"]

    ui.ok("frontend: install + protobuf codegen + build done")
    return []


def _protos_checkout(ws: Workspace) -> Path | None:
    """The on-disk pipestream-protos checkout, when the manifest has one.

    :param ws: the loaded workspace manifest
    :return: the checkout path, or None when it is not cloned
    """
    repo = ws.repo_named("pipestream-protos")
    if repo is None:
        return None
    dest = repo.dest(ws.root)
    return dest if dest.is_dir() else None


def _resolve_java_home() -> Path | None:
    """Use the sdkman-managed current Java if available, else fall back to
    whatever gradle would auto-detect.

    :return: a JAVA_HOME path, or None when nothing is pinned
    """
    candidate = Path.home() / ".sdkman" / "candidates" / "java" / "current"
    if candidate.exists():
        return candidate
    if "JAVA_HOME" in os.environ:
        p = Path(os.environ["JAVA_HOME"])
        if p.exists():
            return p
    return None


def _m2_hint(ws: Workspace) -> None:
    if ws.m2_repo == Path.home() / ".m2" / "repository":
        return
    ui.plain("")
    ui.info("To make IDEs / manual `mvn` / `gradle` use this same location,")
    ui.info("add to ~/.m2/settings.xml:")
    ui.info(f"  <settings><localRepository>{ws.m2_repo}</localRepository></settings>")


def _gradle(repo: Repo, ws: Workspace, task: str) -> int:
    dest = repo.dest(ws.root)
    if not dest.exists():
        ui.error(f"{repo.relative_dest()} missing — run `./bootstrap.sh clone` first")
        return 1

    gradlew = dest / "gradlew"
    if not gradlew.exists():
        ui.error(f"{repo.relative_dest()} has no gradlew script")
        return 1

    ui.header(f"{task}: {repo.name}")
    ui.info(f"cwd: {dest}")

    env = dict(os.environ)
    java_home = _resolve_java_home()
    if java_home:
        env["JAVA_HOME"] = str(java_home)
        env["PATH"] = f"{java_home}/bin:{env.get('PATH', '')}"

    res = subprocess.run(
        ["./gradlew", task, "--no-daemon", f"-Dmaven.repo.local={ws.m2_repo}"],
        cwd=str(dest),
        env=env,
    )
    if res.returncode != 0:
        ui.error(f"{repo.name}: {task} failed (exit {res.returncode})")
        return res.returncode

    ui.ok(f"{repo.name}: {task} done")
    return 0
