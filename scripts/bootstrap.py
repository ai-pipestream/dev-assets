#!/usr/bin/env python3
"""ai-pipestream workspace bootstrap.

Subcommands implemented:
  check    Detect prereqs and offer to install missing ones.

Subcommands planned:
  clone           Clone all platform repos per config/workspace.toml.
  build           Build pipestream-platform -> ~/.m2 (publishToMavenLocal).
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
from lib import prereqs, ui


def cmd_check(args: argparse.Namespace) -> int:
    return prereqs.run_check(
        interactive=not args.yes,
        skip_install=args.skip_install,
    )


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

    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        ui.error("\nInterrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
