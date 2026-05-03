"""Wrap process-compose for the dev stack."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import ui
from .seed import PIPELINE_DEV_DIR

PROCESS_COMPOSE_YAML = PIPELINE_DEV_DIR / "process-compose.yaml"
ENV_FILE = PIPELINE_DEV_DIR / ".env"


def up(detached: bool = True) -> int:
    if not _ensure_seeded():
        return 1
    if not _ensure_env():
        return 1
    if not shutil.which("process-compose"):
        ui.error("process-compose not on PATH — run `./bootstrap.sh check` first.")
        return 1
    cmd = ["process-compose", "up", "-f", str(PROCESS_COMPOSE_YAML)]
    if detached:
        cmd.append("--detached")
    ui.info(f"cwd: {PIPELINE_DEV_DIR}")
    ui.info(f"running: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(PIPELINE_DEV_DIR)).returncode


def down() -> int:
    if not shutil.which("process-compose"):
        ui.error("process-compose not on PATH")
        return 1
    cmd = ["process-compose", "down", "-f", str(PROCESS_COMPOSE_YAML)]
    ui.info(f"cwd: {PIPELINE_DEV_DIR}")
    ui.info(f"running: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(PIPELINE_DEV_DIR)).returncode


def _ensure_seeded() -> bool:
    if PROCESS_COMPOSE_YAML.exists():
        return True
    ui.error(f"{PROCESS_COMPOSE_YAML} not found.")
    ui.info("Run `./bootstrap.sh seed` first.")
    return False


def _ensure_env() -> bool:
    if ENV_FILE.exists():
        return True
    example = PIPELINE_DEV_DIR / "process-compose.env.example"
    ui.error(f"{ENV_FILE} does not exist.")
    if example.exists():
        ui.info(f"Copy and edit the template: cp {example} {ENV_FILE}")
    else:
        ui.info("Run `./bootstrap.sh seed` to generate a default .env")
    return False
