#!/usr/bin/env python3
"""ai-pipestream workspace bootstrap.

Subcommands implemented:
  check           Detect prereqs and offer to install missing ones.
  clone           Clone all platform repos per config/workspace.toml.
  build           Build seed repos (publishToMavenLocal) to warm ~/.m2.
  seed            Seed ~/.pipeline/ from the platform extension's resources.
  dev-up          Start the process-compose dev stack.
  dev-down        Stop the process-compose dev stack.
  reference-sync  Clone/update the reference-code repos (OSS upstreams).

Subcommands planned:
  all             Run check -> clone -> build -> seed -> dev-up smoke test.

Run `./bootstrap.sh <subcommand> --help` for per-subcommand options.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import build, dev_compose, git_sync, manifest, prereqs, seed, ui


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
    return build.build_seed(ws)


def cmd_seed(args: argparse.Namespace) -> int:
    ws = manifest.load()
    return seed.seed(ws, dry_run=args.dry_run)


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
        help="Build seed repos (publishToMavenLocal) to warm ~/.m2",
        description="Run `./gradlew publishToMavenLocal` SERIALLY on every "
                    "build_first=true repo in the manifest. This warms "
                    "~/.m2 so subsequent parallel gradle builds in other "
                    "services don't race writing the same dependencies.",
    )
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
    p_seed.set_defaults(func=cmd_seed)

    p_up = sub.add_parser(
        "dev-up",
        help="Start the process-compose dev stack",
        description="Run `process-compose up` against ~/.pipeline/dev/process-compose.yaml.",
    )
    p_up.add_argument("--attach", action="store_true",
                      help="Run process-compose in foreground (default: detached)")
    p_up.set_defaults(func=cmd_dev_up)

    p_down = sub.add_parser(
        "dev-down",
        help="Stop the process-compose dev stack",
    )
    p_down.set_defaults(func=cmd_dev_down)

    p_ref = sub.add_parser(
        "reference-sync",
        help="Clone/update reference-code repos (OSS upstreams)",
        description="Clone every [[ref_repo]] from config/workspace.toml into "
                    "<workspace.root>/main/reference-code/<name>. These are "
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
