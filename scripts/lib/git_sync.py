"""Parallel git clone / update against the workspace manifest."""
from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from . import ui
from .manifest import Repo, Workspace


@dataclass(frozen=True)
class Result:
    repo: Repo
    action: str    # cloned, updated, skipped, would-clone, would-update, failed
    detail: str = ""


def _is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def _clone(repo: Repo, dest: Path, url: str) -> Result:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", "--branch", repo.branch, url, str(dest)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        return Result(repo, "cloned")
    err = (res.stderr or "").strip()
    # branch missing on remote? retry with default
    if "Remote branch" in err or "not found" in err.lower():
        retry = subprocess.run(
            ["git", "clone", url, str(dest)],
            capture_output=True, text=True,
        )
        if retry.returncode == 0:
            return Result(repo, "cloned", "(remote default branch)")
        return Result(repo, "failed", _last_line(retry.stderr) or "clone failed")
    return Result(repo, "failed", _last_line(err) or "clone failed")


def _update(repo: Repo, dest: Path) -> Result:
    fetch = subprocess.run(
        ["git", "-C", str(dest), "fetch", "--all", "--prune"],
        capture_output=True, text=True,
    )
    if fetch.returncode != 0:
        return Result(repo, "failed", "fetch failed: " + _last_line(fetch.stderr))
    pull = subprocess.run(
        ["git", "-C", str(dest), "pull", "--ff-only"],
        capture_output=True, text=True,
    )
    if pull.returncode != 0:
        return Result(repo, "skipped", "ff-only pull declined (local changes?)")
    if "Already up to date" in (pull.stdout + pull.stderr):
        return Result(repo, "updated", "already up-to-date")
    return Result(repo, "updated")


def _last_line(s: str) -> str:
    lines = [l for l in (s or "").splitlines() if l.strip()]
    return lines[-1] if lines else ""


def _process_one(repo: Repo, ws: Workspace, mode: str) -> Result:
    dest = repo.dest(ws.root)
    url = repo.clone_url(ws.clone_protocol, ws.github_org)

    if _is_git_repo(dest):
        if mode == "list":
            return Result(repo, "would-update" if mode == "update" else "skipped",
                          "exists")
        if mode == "update":
            return _update(repo, dest)
        return Result(repo, "skipped", "exists")

    if mode == "list":
        return Result(repo, "would-clone", url)

    return _clone(repo, dest, url)


def sync(ws: Workspace, mode: str = "clone") -> int:
    """Sync all repos in the manifest.

    mode:
      'clone'  — clone missing only, leave existing alone
      'update' — clone missing + ff-pull existing
      'list'   — dry run, no changes on disk
    """
    if not ws.repos:
        ui.error("No repos in manifest.")
        return 1

    ui.header(f"Workspace sync ({mode})")
    ui.info(f"Workspace root:  {ws.root}")
    ui.info(f"Github org:      {ws.github_org}")
    ui.info(f"Protocol:        {ws.clone_protocol}")
    ui.info(f"Parallelism:     {ws.parallelism}")
    ui.info(f"Repos:           {len(ws.repos)}")
    ui.plain("")

    results: list[Result] = []
    with ThreadPoolExecutor(max_workers=ws.parallelism) as ex:
        futures = {ex.submit(_process_one, r, ws, mode): r for r in ws.repos}
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            _print_result(res, ws.root)

    ui.plain("")
    ui.header("Summary")
    counts: dict[str, int] = {}
    for r in results:
        counts[r.action] = counts.get(r.action, 0) + 1
    for action in ("cloned", "updated", "skipped", "would-clone", "would-update", "failed"):
        n = counts.get(action, 0)
        if n:
            ui.plain(f"  {action:14s} {n}")

    if counts.get("failed", 0):
        ui.plain("")
        ui.error("Some operations failed:")
        for r in results:
            if r.action == "failed":
                ui.error(f"  {r.repo.relative_dest()}: {r.detail}")
        return 1
    return 0


def _print_result(r: Result, root: Path) -> None:
    rel = r.repo.relative_dest()
    if r.action == "cloned":
        ui.ok(f"cloned   {rel}{('  ' + r.detail) if r.detail else ''}")
    elif r.action == "updated":
        ui.ok(f"updated  {rel}{('  ' + r.detail) if r.detail else ''}")
    elif r.action == "skipped":
        ui.info(f"skipped  {rel}{('  ' + r.detail) if r.detail else ''}")
    elif r.action == "would-clone":
        ui.plain(f"        would-clone   {rel}")
    elif r.action == "would-update":
        ui.plain(f"        would-update  {rel}")
    elif r.action == "failed":
        ui.error(f"failed   {rel}  {r.detail}")


def maybe_dev_assets_relocation_notice(ws: Workspace) -> None:
    """If dev-assets is now at its expected location AND we're running from
    a different on-disk dev-assets, print a notice about the duplicate.
    """
    dev_assets = ws.repo_named("dev-assets")
    if not dev_assets:
        return
    target = dev_assets.dest(ws.root).resolve()
    if not (target / ".git").exists():
        return

    # The bootstrap script lives at <dev-assets-root>/bootstrap.sh.
    # __file__ is <dev-assets-root>/scripts/lib/git_sync.py, so root is parents[2].
    running_from = Path(__file__).resolve().parents[2]
    if running_from == target:
        return

    ui.plain("")
    ui.header("dev-assets relocation notice")
    ui.warn(f"You are running bootstrap from: {running_from}")
    ui.warn(f"The canonical location is now:  {target}")
    ui.plain("")
    ui.plain("Both copies are git checkouts of dev-assets. The one you")
    ui.plain("ran from is the older copy. To clean it up when ready:")
    ui.plain("")
    ui.plain(f"  rm -rf {running_from}")
    ui.plain("")
    ui.plain("Then run all future bootstrap commands from the new location:")
    ui.plain(f"  cd {target}")
