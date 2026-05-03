"""Seed ~/.pipeline/ from pipestream-platform's bundled extension resources.

Mirrors the layout krick uses:
  ~/.pipeline/compose-devservices.yml      -> platform extension src
  ~/.pipeline/init-postgres.sql            -> platform extension src
  ~/.pipeline/seaweedfs-s3-config.json     -> platform extension src
  ~/.pipeline/consul-config/               -> platform extension src
  ~/.pipeline/dev/process-compose.yaml     -> platform extension src
  ~/.pipeline/dev/check-*.sh               -> platform extension src
  ~/.pipeline/dev/start-dev-djl.sh         -> platform extension src
  ~/.pipeline/dev/register-dev-djl-models.sh
  ~/.pipeline/dev/nvidia-gpu-setup.sh
  ~/.pipeline/dev/process-compose.env.example -> platform extension src
  ~/.pipeline/dev/.env                     -> auto-generated if missing
  ~/.local/bin/dev-services                -> dev-assets/assets/dev-services

All entries are SYMLINKS so updates to the platform extension's resources
propagate without a re-seed. The auto-generated .env is the only real file
(so the user can edit it without touching the symlink target).
"""
from __future__ import annotations

from pathlib import Path

from . import ui
from .manifest import Workspace

PIPELINE_DIR = Path.home() / ".pipeline"
PIPELINE_DEV_DIR = PIPELINE_DIR / "dev"
LOCAL_BIN = Path.home() / ".local" / "bin"

# Files at ~/.pipeline/<file>
_ROOT_FILES = [
    "compose-devservices.yml",
    "init-postgres.sql",
    "seaweedfs-s3-config.json",
]

# Subdirs symlinked at ~/.pipeline/<dir>
_ROOT_SUBDIRS = ["consul-config"]

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
        for d in (PIPELINE_DIR, PIPELINE_DEV_DIR, LOCAL_BIN):
            d.mkdir(parents=True, exist_ok=True)

    failed = 0
    for fname in _ROOT_FILES:
        if not _link(src_root / fname, PIPELINE_DIR / fname, dry_run):
            failed += 1

    for d in _ROOT_SUBDIRS:
        if not _link(src_root / d, PIPELINE_DIR / d, dry_run):
            failed += 1

    for fname in _DEV_FILES:
        if not _link(src_root / fname, PIPELINE_DEV_DIR / fname, dry_run):
            failed += 1

    # dev-services wrapper from dev-assets (this repo)
    dev_assets_root = Path(__file__).resolve().parents[2]
    wrapper = dev_assets_root / "assets" / "dev-services"
    if not _link(wrapper, LOCAL_BIN / "dev-services", dry_run):
        failed += 1

    # .env generation
    env_file = PIPELINE_DEV_DIR / ".env"
    ui.plain("")
    if env_file.exists() and not env_file.is_symlink():
        ui.ok(f"~/.pipeline/dev/.env already exists — leaving alone")
    else:
        _write_default_env(env_file, ws, dry_run)

    ui.plain("")
    if failed:
        ui.error(f"{failed} symlink(s) failed.")
        return 1
    ui.ok("Seed complete.")
    return 0


def _link(src: Path, dst: Path, dry_run: bool) -> bool:
    """Create dst as a symlink to src. Returns True on success.

    - If dst is already the right symlink: no-op.
    - If dst is a different symlink: replace.
    - If dst is a real file or dir: refuse, ask user to remove.
    - If src does not exist: warn and skip (returns True — not a hard fail).
    """
    if not src.exists():
        ui.warn(f"source missing in extension: {src.name} (skipping)")
        return True

    src_resolved = src.resolve()
    short_dst = _shorten(dst)

    if dst.is_symlink():
        if dst.resolve() == src_resolved:
            ui.info(f"already linked: {short_dst}")
            return True
        if not dry_run:
            dst.unlink()
        ui.warn(f"replaced existing link: {short_dst}")
    elif dst.exists():
        ui.error(f"{short_dst} exists and is NOT a symlink — remove it manually")
        return False

    if not dry_run:
        dst.symlink_to(src_resolved)
    ui.ok(f"linked: {short_dst} -> {src_resolved}")
    return True


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

# Connectors moved out of core-services in the new layout — point at them
# explicitly so process-compose.yaml's defaults pick up the right paths.
JDBC_CONNECTOR_DIR={connectors}/jdbc-connector
S3_CONNECTOR_DIR={connectors}/s3-connector
"""
    short = _shorten(env_file)
    if dry_run:
        ui.warn(f"would write: {short}")
        return
    env_file.write_text(content)
    ui.ok(f"wrote default .env: {short}")
    ui.info("  edit to add per-service worktree overrides as needed")
