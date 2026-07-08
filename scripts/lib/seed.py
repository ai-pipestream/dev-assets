"""Seed ~/.pipeline/ from pipestream-platform's bundled extension resources.

Mirrors the layout krick uses:
  ~/.pipeline/compose-devservices.yml      -> platform extension src
  ~/.pipeline/init-postgres.sql            -> platform extension src
  ~/.pipeline/seaweedfs-s3-config.json     -> platform extension src

  ~/.pipeline/dev/process-compose.yaml     -> platform extension src
  ~/.pipeline/dev/check-*.sh               -> platform extension src
  ~/.pipeline/dev/start-dev-djl.sh         -> platform extension src
  ~/.pipeline/dev/register-dev-djl-models.sh
  ~/.pipeline/dev/nvidia-gpu-setup.sh
  ~/.pipeline/dev/process-compose.env.example -> platform extension src
  ~/.pipeline/dev/.env                     -> auto-generated if missing
  ~/.local/bin/dev-services                -> dev-assets/assets/dev-services
  ~/.gradle/init.gradle                    -> dev-assets/assets/gradle-init.gradle

All entries are real COPIES taken at seed time, not symlinks: the source
lives inside a git checkout (pipestream-platform for most of these, this
repo for the dev-services wrapper and the Gradle init script) and copying is
what "run the installer after everything is checked out" is supposed to
mean — ~/.pipeline/ should not keep pointing back into a workspace checkout
that can move, get rebuilt, or disappear. Re-run `seed` (or `bootstrap.sh
check`) after pulling platform changes to refresh the copies. The
auto-generated .env is unrelated to this copy step — it's hand-edited by the
user and never overwritten once present.

~/.gradle/init.gradle carries no secrets — it only reads FORGEJO_ACTOR/
FORGEJO_TOKEN from the environment or forgejoUser/forgejoToken from
~/.gradle/gradle.properties, and Forgejo package reads are anonymous, so a
fresh machine (or a public/CI runner) builds fine with none of that set. The
installer never writes credentials into gradle.properties itself.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from . import ui
from .manifest import Workspace

PIPELINE_DIR = Path.home() / ".pipeline"
PIPELINE_DEV_DIR = PIPELINE_DIR / "dev"
LOCAL_BIN = Path.home() / ".local" / "bin"
GRADLE_DIR = Path.home() / ".gradle"

# Files at ~/.pipeline/<file>
_ROOT_FILES = [
    "compose-devservices.yml",
    "init-postgres.sql",
    "seaweedfs-s3-config.json",
]

# Subdirs copied at ~/.pipeline/<dir> (none today; consul-config died with
# the consul retirement — the frontend resolves via platform-registration).
_ROOT_SUBDIRS: list[str] = []

# Files at ~/.pipeline/dev/<file>
_DEV_FILES = [
    "process-compose.yaml",
    "process-compose.env.example",
    "check-infra-healthy.sh",
    "check-djl-healthy.sh",
    "start-dev-djl.sh",
    "register-dev-djl-models.sh",
    "nvidia-gpu-setup.sh",
]


def _platform_resources_dir(ws: Workspace) -> Path | None:
    pp = ws.repo_named("pipestream-platform")
    if not pp:
        return None
    return (pp.dest(ws.root) / "pipestream-quarkus-devservices"
            / "runtime" / "src" / "main" / "resources")


def seed(ws: Workspace, dry_run: bool = False) -> int:
    src_root = _platform_resources_dir(ws)
    if src_root is None:
        ui.error("pipestream-platform missing from manifest")
        return 1
    if not src_root.exists():
        ui.error(f"Platform extension resources not on disk: {src_root}")
        ui.info("Run `./bootstrap.sh clone` first.")
        return 1

    ui.header("Seeding ~/.pipeline/")
    ui.info(f"Source:        {src_root}")
    ui.info(f"Pipeline dir:  {PIPELINE_DIR}")
    ui.info(f"Dev dir:       {PIPELINE_DEV_DIR}")
    ui.info(f"Wrapper bin:   {LOCAL_BIN}/dev-services")
    if dry_run:
        ui.warn("Dry run — no files will be created or modified")
    ui.plain("")

    if not dry_run:
        for d in (PIPELINE_DIR, PIPELINE_DEV_DIR, LOCAL_BIN, GRADLE_DIR):
            d.mkdir(parents=True, exist_ok=True)

    failed = 0
    for fname in _ROOT_FILES:
        if not _copy(src_root / fname, PIPELINE_DIR / fname, dry_run):
            failed += 1

    for d in _ROOT_SUBDIRS:
        if not _copy(src_root / d, PIPELINE_DIR / d, dry_run):
            failed += 1

    for fname in _DEV_FILES:
        if not _copy(src_root / fname, PIPELINE_DEV_DIR / fname, dry_run):
            failed += 1

    # dev-services wrapper + Gradle init script, both from dev-assets (this repo)
    dev_assets_root = Path(__file__).resolve().parents[2]
    wrapper = dev_assets_root / "assets" / "dev-services"
    if not _copy(wrapper, LOCAL_BIN / "dev-services", dry_run):
        failed += 1

    gradle_init = dev_assets_root / "assets" / "gradle-init.gradle"
    if not _copy(gradle_init, GRADLE_DIR / "init.gradle", dry_run):
        failed += 1
    ui.plain("")
    if (GRADLE_DIR / "gradle.properties").exists():
        ui.info("~/.gradle/gradle.properties already exists — leaving alone")
    else:
        ui.info("No ~/.gradle/gradle.properties — builds work anonymously against")
        ui.info("  Forgejo (reads only). For authenticated access set forgejoUser/")
        ui.info("  forgejoToken there, or export FORGEJO_ACTOR/FORGEJO_TOKEN.")

    # .env generation
    env_file = PIPELINE_DEV_DIR / ".env"
    ui.plain("")
    if env_file.exists() and not env_file.is_symlink():
        ui.ok(f"~/.pipeline/dev/.env already exists — leaving alone")
    else:
        _write_default_env(env_file, ws, dry_run)

    ui.plain("")
    if failed:
        ui.error(f"{failed} copy(ies) failed.")
        return 1
    ui.ok("Seed complete.")
    return 0


def _copy(src: Path, dst: Path, dry_run: bool) -> bool:
    """Copy src to dst, replacing whatever was there. Returns True on success.

    - A leftover symlink at dst (from a pre-copy-mode seed) is removed first.
    - A real file/dir at dst is overwritten — these are seed-managed outputs,
      not user-edited files, so clobbering on re-seed is intended.
    - If src does not exist: warn and skip (returns True — not a hard fail).
    """
    if not src.exists():
        ui.warn(f"source missing in extension: {src.name} (skipping)")
        return True

    short_dst = _shorten(dst)

    if dst.is_symlink() or dst.exists():
        if not dry_run:
            if dst.is_dir() and not dst.is_symlink():
                shutil.rmtree(dst)
            else:
                dst.unlink()

    if not dry_run:
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    ui.ok(f"copied: {short_dst} <- {src}")
    return True


def _render_gid() -> int | None:
    """This host's `render` group gid, or None when the group doesn't exist."""
    try:
        import grp
        return grp.getgrnam("render").gr_gid
    except (ImportError, KeyError):
        return None


def _shorten(p: Path) -> str:
    try:
        return "~/" + str(p.relative_to(Path.home()))
    except ValueError:
        return str(p)


def _write_default_env(env_file: Path, ws: Workspace, dry_run: bool) -> None:
    """Generate a sensible default .env from the workspace layout.

    Sets CORE_SERVICES_DIR, MODULES_DIR, plus per-service overrides where
    the manifest layout differs from the process-compose.yaml defaults
    (jdbc-connector and s3-connector live under <root>/main/connectors/
    instead of under core-services).
    """
    core = ws.root / "main" / "core-services"
    modules = ws.root / "main" / "modules"
    connectors = ws.root / "main" / "connectors"

    content = f"""# Auto-generated by ./bootstrap.sh seed.
# Edit freely — the seed step will not overwrite an existing .env.
# To regenerate from scratch, delete this file and re-run seed.

CORE_SERVICES_DIR={core}
MODULES_DIR={modules}
PC_PORT_NUM=8765

# Dev wiring — process-compose exports these to every service.
# Registration runs grpc-mode with no discovery fallback, so services need the
# local platform-registration host+port (the %localdocker container profile
# overrides these to the container name in its own compose env).
PIPESTREAM_REGISTRATION_REGISTRATION_SERVICE_HOST=localhost
PIPESTREAM_REGISTRATION_REGISTRATION_SERVICE_PORT=18101
# Silence JDK 25 native-access warnings (Netty / AWS SDK) on every forked dev JVM.
JDK_JAVA_OPTIONS=--enable-native-access=ALL-UNNAMED

# Connectors moved out of core-services in the new layout — point at them
# explicitly so process-compose.yaml's defaults pick up the right paths.
JDBC_CONNECTOR_DIR={connectors}/jdbc-connector
S3_CONNECTOR_DIR={connectors}/s3-connector
"""
    render_gid = _render_gid()
    if render_gid is not None:
        content += f"""
# GPU render-node group for containerized backends (OVMS on Intel GPUs).
# Detected from this host's `render` group at seed time — the compose default
# (993) silently breaks GPU access on hosts where the gid differs (e.g. 990),
# and every model then fails with "Cannot compile model into target device".
OVMS_RENDER_GID={render_gid}
"""
    short = _shorten(env_file)
    if dry_run:
        ui.warn(f"would write: {short}")
        return
    env_file.write_text(content)
    ui.ok(f"wrote default .env: {short}")
    ui.info("  edit to add per-service worktree overrides as needed")
