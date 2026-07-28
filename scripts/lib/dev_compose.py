"""Wrap process-compose for the dev stack."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import ui
from .seed import PIPELINE_DEV_DIR

PROCESS_COMPOSE_YAML = PIPELINE_DEV_DIR / "process-compose.yaml"
ENV_FILE = PIPELINE_DEV_DIR / ".env"


def pc_port(env_file: Path = ENV_FILE) -> str:
    """The process-compose API port the grid is expected on.

    PC_PORT_NUM in ~/.pipeline/dev/.env is read by process-compose only for
    yaml template substitution — it does NOT set the server's own API port,
    so a bare `process-compose up` serves on its built-in default (8080)
    while the health gate polls the .env's 8765 and reports a dead grid.
    The port must be passed explicitly; every launcher and poller goes
    through this one reader.
    """
    try:
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("PC_PORT_NUM="):
                value = line.split("=", 1)[1].strip()
                if value:
                    return value
    except OSError:
        pass
    return "8765"


def up(detached: bool = True) -> int:
    if not _ensure_seeded():
        return 1
    if not _ensure_env():
        return 1
    if not shutil.which("process-compose"):
        ui.error("process-compose not on PATH — run `./bootstrap.sh check` first.")
        return 1
    cmd = ["process-compose", "up", "-f", str(PROCESS_COMPOSE_YAML),
           "--port", pc_port()]
    if detached:
        cmd.append("--detached")
    ui.info(f"cwd: {PIPELINE_DEV_DIR}")
    ui.info(f"running: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(PIPELINE_DEV_DIR)).returncode


def down() -> int:
    if not shutil.which("process-compose"):
        ui.error("process-compose not on PATH")
        return 1
    cmd = ["process-compose", "down", "-f", str(PROCESS_COMPOSE_YAML),
           "--port", pc_port()]
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


def e2e_smoke(ws) -> int:
    """Run the two proving E2E scenarios against the local dev grid.

    goldenPath (file connector demo pipeline: deploy -> upload -> repository
    -> traces -> teardown) and demoJdbcSeed (CDC seed -> replication slot
    lifecycle on the demo database). Both run the frontend regression suite's
    live leg against this machine's BFF, so a pass proves the grid end to
    end: module catalog, embedding backends, engine, repository, OpenSearch,
    the demo database seed and the jdbc connector's CDC path.

    :param ws: the loaded workspace (locates the frontend checkout)
    :return: 0 when both scenarios pass
    """
    fe_dir = ws.root / ws.tree / "frontend" / "pipestream-frontend"
    app_dir = fe_dir / "apps" / "pipestream-frontend"
    if not (app_dir / "package.json").exists():
        ui.error(f"frontend checkout missing: {app_dir}")
        return 1
    if not shutil.which("pnpm"):
        ui.error("pnpm not on PATH — run `./bootstrap.sh check` first.")
        return 1
    env = dict(os.environ,
               FE_BASE_URL="http://localhost:38106",
               REGRESSION_LEG="live")
    ui.header("E2E smoke (goldenPath + demoJdbcSeed, live leg)")
    rc = 0
    for scenario in ("goldenPath", "demoJdbcSeed"):
        cmd = ["pnpm", "-C", str(app_dir), "test:regression", scenario]
        ui.info(f"running: {' '.join(cmd)}")
        r = subprocess.run(cmd, cwd=str(fe_dir), env=env).returncode
        if r != 0:
            ui.error(f"{scenario} FAILED (exit {r})")
            rc = 1
        else:
            ui.info(f"{scenario} passed")
    return rc
