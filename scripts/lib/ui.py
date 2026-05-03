"""Terminal UI helpers — colored output, prompts, headers.

ASCII-only markers (no emoji). Honours NO_COLOR and non-tty stdout.
"""
from __future__ import annotations

import os
import sys

_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str) -> str:
    return code if _USE_COLOR else ""


RESET = _c("\033[0m")
BOLD = _c("\033[1m")
DIM = _c("\033[2m")
RED = _c("\033[31m")
GREEN = _c("\033[32m")
YELLOW = _c("\033[33m")
BLUE = _c("\033[34m")
CYAN = _c("\033[36m")


def header(msg: str) -> None:
    print(f"\n{BOLD}{CYAN}== {msg} =={RESET}")


def ok(msg: str) -> None:
    print(f"{GREEN}[ OK ]{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{RESET} {msg}")


def error(msg: str) -> None:
    print(f"{RED}[ERR ]{RESET} {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"{DIM}[ .. ]{RESET} {msg}")


def plain(msg: str) -> None:
    print(msg)


def confirm(prompt: str, default: bool = True) -> bool:
    suffix = " [Y/n] " if default else " [y/N] "
    while True:
        try:
            ans = input(f"{BOLD}{prompt}{RESET}{suffix}").strip().lower()
        except EOFError:
            return default
        if not ans:
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("  Please answer y or n.")
