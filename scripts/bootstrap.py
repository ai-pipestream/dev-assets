#!/usr/bin/env python3
"""ai-pipestream workspace bootstrap.

Subcommands implemented:
  check    Detect prereqs and offer to install missing ones.
  clone    Clone all platform repos per config/workspace.toml.
  build    Build seed repos (publishToMavenLocal) to warm ~/.m2.

Subcommands planned:
  dev-up          Start the process-compose dev stack.
  dev-down        Stop the process-compose dev stack.
  reference-sync  Clone/update the reference-code repos.
  all             Run check -> clone -> build -> dev-up smoke test.

Run `./bootstrap.sh <subcommand> --help` for per-subcommand options.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import build, git_sync, manifest, prereqs, ui


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

    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        ui.error("\nInterrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
