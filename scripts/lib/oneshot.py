"""`bootstrap all` — the whole bring-up as one command that proves itself.

check -> clone -> build -> seed -> dev-up -> dev-grid-health.sh

The last step is the point. Every earlier step can succeed while the grid is
still unusable: process-compose returns as soon as it has launched things, and
it stops probing a process once its readiness budget is spent, so a service that
died stays parked in `Running`. Without a gate at the end, "the bootstrap works"
is an opinion. With one, it is an exit code.

Each phase is skippable so a partially-completed run can be resumed
(``--skip clone,build``), and ``--no-dev-up`` stops after seeding for machines
that only want the workspace.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import build, dev_compose, git_sync, prereqs, seed, ui
from .manifest import Workspace

# Phase names accepted by --skip, in execution order.
PHASES = ("check", "clone", "build", "seed", "dev-up", "health")

# The gate lives with the process-compose.yaml it reads, and `seed` installs it.
HEALTH_GATE = seed.PIPELINE_DEV_DIR / "dev-grid-health.sh"

# How long to let the grid converge before declaring it broken. A cold start
# compiles 19 Quarkus applications; the readiness probes in process-compose.yaml
# already budget ~450s each for that, so a shorter deadline here would just
# report a failure that had not happened yet.
DEFAULT_HEALTH_WAIT = 900


def run_all(
    ws: Workspace,
    skip: frozenset[str] = frozenset(),
    yes: bool = False,
    dev_up: bool = True,
    health_wait: int = DEFAULT_HEALTH_WAIT,
) -> int:
    """Run every bootstrap phase in order, stopping at the first failure.

    :param ws: the loaded workspace manifest
    :param skip: phase names to skip
    :param yes: auto-confirm prereq installs
    :param dev_up: when False, stop after seed (no grid, no health gate)
    :param health_wait: seconds to let the grid converge before failing
    :return: 0 when every phase that ran succeeded
    """
    unknown = skip - set(PHASES)
    if unknown:
        ui.error(f"unknown phase(s) to skip: {', '.join(sorted(unknown))}")
        ui.info(f"known phases: {', '.join(PHASES)}")
        return 64

    if not dev_up:
        skip = skip | {"dev-up", "health"}

    planned = [p for p in PHASES if p not in skip]
    ui.header("bootstrap all")
    ui.info(f"workspace root: {ws.root}")
    ui.info(f"phases:         {' -> '.join(planned)}")
    if skip:
        ui.warn(f"skipping:       {', '.join(p for p in PHASES if p in skip)}")
    ui.plain("")

    for phase in planned:
        rc = _run_phase(phase, ws, yes=yes, health_wait=health_wait)
        if rc != 0:
            ui.plain("")
            ui.error(f"bootstrap all stopped in phase '{phase}' (exit {rc}).")
            ui.info(f"Fix it, then resume with: ./bootstrap.sh all "
                    f"--skip {','.join(p for p in planned[:planned.index(phase)]) or 'none'}")
            return rc

    ui.plain("")
    if "health" in skip:
        ui.ok("bootstrap all complete (health gate not run).")
    else:
        ui.ok("bootstrap all complete — the dev grid is up and healthy.")
    return 0


def _run_phase(phase: str, ws: Workspace, yes: bool, health_wait: int) -> int:
    if phase == "check":
        # Exit 2 means "installed, but this shell has a stale PATH". That is a
        # real stop: the later phases shell out to gradle/pnpm/process-compose
        # and would fail with a confusing "command not found" instead.
        rc = prereqs.run_check(interactive=not yes, skip_install=False)
        if rc == 2:
            ui.error("Prereqs were installed but are not on this shell's PATH.")
            ui.info("Open a new terminal and re-run: ./bootstrap.sh all")
        return rc

    if phase == "clone":
        return git_sync.sync(ws, mode="clone")

    if phase == "build":
        return build.build_all(ws)

    if phase == "seed":
        return seed.seed(ws)

    if phase == "dev-up":
        return dev_compose.up(detached=True)

    if phase == "health":
        return _health_gate(health_wait)

    ui.error(f"no implementation for phase '{phase}'")
    return 70


def _health_gate(wait_seconds: int) -> int:
    """Run the seeded dev-grid-health.sh and return its exit code.

    :param wait_seconds: how long the gate may poll before giving up
    :return: 0 when the grid is healthy, else the offender count
    """
    ui.header("Dev grid health gate")
    if not HEALTH_GATE.exists():
        ui.error(f"{HEALTH_GATE} missing — `seed` should have installed it.")
        ui.info("Re-run `./bootstrap.sh seed`, or pull pipestream-platform.")
        return 70
    if not shutil.which("bash"):
        ui.error("bash not on PATH — cannot run the health gate.")
        return 70

    cmd = ["bash", str(HEALTH_GATE), "--wait", str(wait_seconds)]
    ui.info(f"running: {' '.join(cmd)}")
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        ui.error(f"Dev grid is NOT healthy ({rc} problem(s) above).")
        ui.info("Per-service logs: ~/.pipeline/dev/logs/<process>.log")
    return rc


def run_drift(ws: Workspace) -> int:
    """Report seed-managed files whose live copy differs from its source.

    ``seed`` replaces those files, backing up anything it would clobber. This
    answers the question BEFORE the copy happens, which is when a hand-edit to
    the running rig can still be reconciled into git instead of turning into a
    ``.bak`` nobody reads.

    :param ws: the loaded workspace manifest
    :return: 0 when nothing differs, 1 otherwise
    """
    ui.header("Seed drift")
    diffs = seed.diff_report(ws)
    if not diffs:
        ui.ok("No drift — every seeded file matches its source in git.")
        return 0

    ui.warn(f"{len(diffs)} seeded file(s) differ from their source in git:")
    ui.plain("")
    for src, dst in diffs:
        ui.plain(f"  {_short(dst)}")
        ui.plain(f"      source: {src}")
    ui.plain("")
    ui.info("These are hand-edits to the live rig. Decide each one:")
    ui.info("  - keep it     -> port the change into the repo, commit, re-seed")
    ui.info("  - drop it     -> ./bootstrap.sh seed (backs the local copy up first)")
    ui.info("  - inspect it  -> diff <source> <live copy>")
    return 1


def _short(p: Path) -> str:
    try:
        return "~/" + str(p.relative_to(Path.home()))
    except ValueError:
        return str(p)
