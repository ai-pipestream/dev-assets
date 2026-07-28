#!/usr/bin/env python3
"""ai-pipestream workspace bootstrap.

Subcommands:
  all             check -> clone -> build -> seed -> dev-up -> health gate.
                  The one command a new machine needs.
  check           Detect prereqs and offer to install missing ones.
  clone           Clone all platform repos per config/workspace.toml.
  build           Warm the build caches: seed ~/.m2, prebuild the gradle fleet,
                  install + build the frontend.
  seed            Seed ~/.pipeline/ from the platform extension's resources.
  drift           Report seeded files whose live copy differs from git.
  dev-up          Start the process-compose dev stack.
  dev-health      Gate on the running dev grid (exits nonzero when it is wrong).
  dev-down        Stop the process-compose dev stack.
  reference-sync  Clone/update the reference-code repos (OSS upstreams).

Run `./bootstrap.sh <subcommand> --help` for per-subcommand options.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import build, dev_compose, git_sync, manifest, oneshot, prereqs, seed, ui


def cmd_check(args: argparse.Namespace) -> int:
    return prereqs.run_check(
        interactive=not args.yes,
        skip_install=args.skip_install,
    )


def cmd_clone(args: argparse.Namespace) -> int:
    ws = manifest.load()
    if args.ssh:
        ws = ws.with_protocol("ssh")
    elif args.https:
        ws = ws.with_protocol("https")

    if args.list:
        mode = "list"
    elif args.update:
        mode = "update"
    else:
        mode = "clone"

    rc = git_sync.sync(ws, mode=mode)
    if rc == 0 and mode in ("clone", "update"):
        git_sync.maybe_dev_assets_relocation_notice(ws)
    return rc


def cmd_build(args: argparse.Namespace) -> int:
    ws = manifest.load()
    if args.seed_only:
        return build.build_seed(ws)
    return build.build_all(ws, skip_frontend=args.no_frontend)


def cmd_seed(args: argparse.Namespace) -> int:
    ws = manifest.load()
    return seed.seed(ws, dry_run=args.dry_run, force=args.force)


def cmd_drift(args: argparse.Namespace) -> int:
    return oneshot.run_drift(manifest.load())


def cmd_dev_health(args: argparse.Namespace) -> int:
    return oneshot._health_gate(args.wait)


def cmd_all(args: argparse.Namespace) -> int:
    ws = manifest.load()
    skip = frozenset(
        p.strip() for p in (args.skip or "").split(",") if p.strip() and p.strip() != "none"
    )
    return oneshot.run_all(
        ws,
        skip=skip,
        yes=args.yes,
        dev_up=not args.no_dev_up,
        health_wait=args.wait,
    )


def cmd_dev_up(args: argparse.Namespace) -> int:
    return dev_compose.up(detached=not args.attach)


def cmd_dev_down(args: argparse.Namespace) -> int:
    return dev_compose.down()


def cmd_reference_sync(args: argparse.Namespace) -> int:
    ws = manifest.load()
    if args.list:
        mode = "list"
    elif args.update:
        mode = "update"
    else:
        mode = "clone"
    return git_sync.sync_refs(ws, mode=mode)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="bootstrap",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser(
        "check",
        help="Detect and install prereqs",
        description="Detect prereqs (docker, sdkman, java, etc.) and offer to install missing ones.",
    )
    p_check.add_argument("--yes", "-y", action="store_true",
                         help="Auto-confirm the install prompt (no interactive question)")
    p_check.add_argument("--skip-install", action="store_true",
                         help="Detect only — never install, just report status")
    p_check.set_defaults(func=cmd_check)

    p_clone = sub.add_parser(
        "clone",
        help="Clone platform repos per manifest",
        description="Clone every repo from config/workspace.toml into "
                    "<workspace.root>/<path>/<name>. Idempotent: existing "
                    "clones are skipped (or fast-forwarded with --update).",
    )
    p_clone.add_argument("--list", action="store_true",
                         help="Dry run — print what would happen, don't clone")
    p_clone.add_argument("--update", action="store_true",
                         help="Also fast-forward existing clones (default: skip existing)")
    proto = p_clone.add_mutually_exclusive_group()
    proto.add_argument("--ssh", action="store_true", help="Use SSH clone URLs")
    proto.add_argument("--https", action="store_true",
                       help="Use HTTPS clone URLs (default per workspace.toml)")
    p_clone.set_defaults(func=cmd_clone)

    p_build = sub.add_parser(
        "build",
        help="Warm the build caches (maven local, gradle fleet, frontend)",
        description="Three phases. (1) `./gradlew publishToMavenLocal` SERIALLY "
                    "on every build_first=true repo, warming ~/.m2 so parallel "
                    "gradle builds don't race writing the same dependencies. "
                    "(2) `./gradlew classes` on every other gradle repo, so 19 "
                    "cold `quarkus dev` compiles do not land on process-compose's "
                    "readiness-probe critical path. (3) pnpm install + protobuf "
                    "codegen + pnpm build for the frontend, without which the "
                    "grid's frontend-bff and frontend-ui cannot start at all.",
    )
    p_build.add_argument("--seed-only", action="store_true",
                         help="Phase 1 only — publishToMavenLocal on build_first repos")
    p_build.add_argument("--no-frontend", action="store_true",
                         help="Skip the frontend phase (gradle phases still run)")
    p_build.set_defaults(func=cmd_build)

    p_seed = sub.add_parser(
        "seed",
        help="Seed ~/.pipeline/ from pipestream-platform extension resources",
        description="Symlink compose/process-compose/scripts from "
                    "pipestream-platform/pipestream-quarkus-devservices/"
                    "runtime/src/main/resources/ into ~/.pipeline/ and "
                    "~/.pipeline/dev/. Also installs the dev-services "
                    "docker-compose wrapper to ~/.local/bin and generates "
                    "a default ~/.pipeline/dev/.env if missing.",
    )
    p_seed.add_argument("--dry-run", action="store_true",
                        help="Print what would happen without touching disk")
    p_seed.add_argument("--force", action="store_true",
                        help="Overwrite locally-modified files without backing "
                             "them up first (default: back up and say so)")
    p_seed.set_defaults(func=cmd_seed)

    p_drift = sub.add_parser(
        "drift",
        help="Report seeded files whose live copy differs from git",
        description="Compare every seed-managed file in ~/.pipeline, "
                    "~/.local/bin and ~/.gradle against the source it came "
                    "from. Exits nonzero when any differ. Run this BEFORE "
                    "`seed`: a difference is a hand-edit to the running rig, "
                    "and that is the moment to reconcile it into the repo "
                    "rather than let the next seed back it up and move on.",
    )
    p_drift.set_defaults(func=cmd_drift)

    p_up = sub.add_parser(
        "dev-up",
        help="Start the process-compose dev stack",
        description="Run `process-compose up` against ~/.pipeline/dev/process-compose.yaml.",
    )
    p_up.add_argument("--attach", action="store_true",
                      help="Run process-compose in foreground (default: detached)")
    p_up.set_defaults(func=cmd_dev_up)

    p_health = sub.add_parser(
        "dev-health",
        help="Gate on the running dev grid",
        description="Run ~/.pipeline/dev/dev-grid-health.sh: every process "
                    "Running and Ready, every /q/health/ready answering 200 on "
                    "an independent re-probe, and a non-empty module catalog. "
                    "Prints an offender table and exits with the offender "
                    "count. This is the check that makes 'the grid is up' a "
                    "fact rather than an opinion — process-compose stops "
                    "probing after failure_threshold, so its own view goes "
                    "stale.",
    )
    p_health.add_argument("--wait", type=int, default=0,
                          help="Seconds to poll before failing (default 0: "
                               "check once and report)")
    p_health.set_defaults(func=cmd_dev_health)

    p_down = sub.add_parser(
        "dev-down",
        help="Stop the process-compose dev stack",
    )
    p_down.set_defaults(func=cmd_dev_down)

    p_all = sub.add_parser(
        "all",
        help="check -> clone -> build -> seed -> dev-up -> health gate",
        description="The whole bring-up as one command, ending in a gate that "
                    "exits nonzero when the grid is not actually usable. This "
                    "is the command a machine that is not the architect's is "
                    "expected to run after cloning dev-assets.",
    )
    p_all.add_argument("--yes", "-y", action="store_true",
                       help="Auto-confirm the prereq install prompt")
    p_all.add_argument("--skip", metavar="PHASES",
                       help="Comma-separated phases to skip: "
                            + ",".join(oneshot.PHASES))
    p_all.add_argument("--no-dev-up", action="store_true",
                       help="Stop after seeding — set up the workspace, do not "
                            "start the grid")
    p_all.add_argument("--wait", type=int, default=oneshot.DEFAULT_HEALTH_WAIT,
                       help="Seconds to let the grid converge before the health "
                            f"gate fails (default {oneshot.DEFAULT_HEALTH_WAIT})")
    p_all.set_defaults(func=cmd_all)

    p_ref = sub.add_parser(
        "reference-sync",
        help="Clone/update reference-code repos (OSS upstreams)",
        description="Clone every [[ref_repo]] from config/workspace.toml into "
                    "<workspace.root>/<tree>/reference-code/<name>. These are "
                    "OSS upstreams (Quarkus, Vert.x, Tika, etc.) used for "
                    "grep / patch workflows; they're never built. Idempotent: "
                    "existing clones are skipped (or fast-forwarded with --update).",
    )
    p_ref.add_argument("--list", action="store_true",
                       help="Dry run — print what would happen, don't clone")
    p_ref.add_argument("--update", action="store_true",
                       help="Also fast-forward existing clones (default: skip existing)")
    p_ref.set_defaults(func=cmd_reference_sync)

    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        ui.error("\nInterrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
