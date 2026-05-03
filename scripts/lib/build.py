"""Serialized seed build for build_first repos.

The first repo to compile in a fresh tree warms ~/.m2 with the platform's
transitive dependencies. If multiple gradle builds run in parallel the
first time and all try to download/write the same artifacts simultaneously,
they race and intermittently corrupt the maven local cache.

This module runs `./gradlew publishToMavenLocal` SERIALLY on every
build_first=true repo before any parallel build is attempted.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from . import ui
from .manifest import Repo, Workspace

_GRADLE_TASK = "publishToMavenLocal"


def build_seed(ws: Workspace) -> int:
    seeds = [r for r in ws.repos if r.build_first]
    if not seeds:
        ui.warn("No build_first repos in manifest — nothing to seed.")
        return 0

    ws.m2_repo.mkdir(parents=True, exist_ok=True)

    ui.header("Maven local seed build")
    ui.info(f"Gradle task:  {_GRADLE_TASK}")
    ui.info(f"Seed repos:   {len(seeds)} ({', '.join(r.name for r in seeds)})")
    ui.info(f"JAVA_HOME:    {_resolve_java_home() or '(not pinned)'}")
    ui.info(f"Maven local:  {ws.m2_repo}")
    ui.plain("")

    for repo in seeds:
        rc = _build_one(repo, ws)
        if rc != 0:
            return rc

    ui.plain("")
    ui.ok(f"All {len(seeds)} seed build(s) published to {ws.m2_repo}.")
    if ws.m2_repo != Path.home() / ".m2" / "repository":
        ui.plain("")
        ui.info("To make IDEs / manual `mvn` / `gradle` use this same location,")
        ui.info("add to ~/.m2/settings.xml:")
        ui.info(f"  <settings><localRepository>{ws.m2_repo}</localRepository></settings>")
    return 0


def _resolve_java_home() -> Path | None:
    """Use the sdkman-managed current Java if available, else fall back to
    whatever gradle would auto-detect.
    """
    candidate = Path.home() / ".sdkman" / "candidates" / "java" / "current"
    if candidate.exists():
        return candidate
    if "JAVA_HOME" in os.environ:
        p = Path(os.environ["JAVA_HOME"])
        if p.exists():
            return p
    return None


def _build_one(repo: Repo, ws: Workspace) -> int:
    dest = repo.dest(ws.root)
    if not dest.exists():
        ui.error(f"{repo.relative_dest()} missing — run `./bootstrap.sh clone` first")
        return 1

    gradlew = dest / "gradlew"
    if not gradlew.exists():
        ui.error(f"{repo.relative_dest()} has no gradlew script")
        return 1

    ui.header(f"Building {repo.name}")
    ui.info(f"cwd: {dest}")

    env = dict(os.environ)
    java_home = _resolve_java_home()
    if java_home:
        env["JAVA_HOME"] = str(java_home)
        env["PATH"] = f"{java_home}/bin:{env.get('PATH', '')}"

    res = subprocess.run(
        ["./gradlew", _GRADLE_TASK, "--no-daemon",
         f"-Dmaven.repo.local={ws.m2_repo}"],
        cwd=str(dest),
        env=env,
    )
    if res.returncode != 0:
        ui.error(f"{repo.name} build failed (exit {res.returncode})")
        return res.returncode

    ui.ok(f"{repo.name}: {_GRADLE_TASK} done")
    return 0
