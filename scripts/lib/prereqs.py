"""Prereq detection and (optional) installation.

Detects all the developer tools we need on a fresh ai-pipestream machine.
Hard-stops on docker + git (per-developer setup; we don't automate them).
Offers a single confirm-then-install-everything flow for the rest.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import ui


# ---- Constants ---------------------------------------------------------

SDKMAN_DIR = Path.home() / ".sdkman"
SDKMAN_INIT = SDKMAN_DIR / "bin" / "sdkman-init.sh"

# JVM distribution we install via sdkman. Configurable via workspace.toml later;
# pinned here to keep Phase 1 self-contained.
JAVA_VERSION = "25-tem"
NODE_VERSION = "22"

# fnm puts its binary in one of these (depending on installer flags / OS)
FNM_CANDIDATE_PATHS = [
    Path.home() / ".local" / "share" / "fnm" / "fnm",
    Path.home() / ".fnm" / "fnm",
]


# ---- Subprocess helpers ------------------------------------------------

def _run_shell(script: str) -> None:
    """Run a bash script string, raising on failure."""
    subprocess.run(["bash", "-c", script], check=True)


def _silent_ok(cmd: list[str] | str) -> bool:
    """Run a command, return True iff exit 0. Silences stdout/stderr."""
    if isinstance(cmd, str):
        return subprocess.run(cmd, shell=True, capture_output=True).returncode == 0
    return subprocess.run(cmd, capture_output=True).returncode == 0


def _cmd_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def _is_linux() -> bool:
    return platform.system() == "Linux"


def _find_fnm() -> Path | None:
    for p in FNM_CANDIDATE_PATHS:
        if p.exists():
            return p
    if _cmd_exists("fnm"):
        return Path(shutil.which("fnm"))
    return None


# ---- Detection ---------------------------------------------------------

def detect_docker() -> bool:
    return _cmd_exists("docker") and _silent_ok(["docker", "info"])


def detect_git() -> bool:
    return _cmd_exists("git")


def detect_uv() -> bool:
    # uv installs to ~/.local/bin which may not be on PATH yet
    return _cmd_exists("uv") or (Path.home() / ".local" / "bin" / "uv").exists()


def detect_sdkman() -> bool:
    return SDKMAN_INIT.exists()


def detect_java() -> bool:
    """Java is considered installed if `java -version` succeeds (any version).

    Pinning to JAVA_VERSION is sdkman's job — we trust whatever it set as
    default. Bootstrap re-runs after a shell refresh will pick up the
    sdkman-managed PATH.
    """
    if not _cmd_exists("java"):
        # Maybe sdkman installed it but PATH isn't refreshed yet — check
        # the sdkman candidates dir directly.
        candidates = SDKMAN_DIR / "candidates" / "java" / "current" / "bin" / "java"
        return candidates.exists()
    return _silent_ok(["java", "-version"])


def detect_quarkus_cli() -> bool:
    if _cmd_exists("quarkus"):
        return True
    return (SDKMAN_DIR / "candidates" / "quarkus" / "current" / "bin" / "quarkus").exists()


def detect_node() -> bool:
    """Require node >= 20 (we target 22 LTS)."""
    node = shutil.which("node")
    if not node:
        # Maybe fnm-managed node isn't on PATH yet
        fnm_versions = Path.home() / ".local" / "share" / "fnm" / "node-versions"
        if fnm_versions.exists() and any(fnm_versions.iterdir()):
            return True
        return False
    try:
        out = subprocess.run([node, "--version"], capture_output=True, text=True)
        if out.returncode != 0:
            return False
        major = int(out.stdout.strip().lstrip("v").split(".")[0])
        return major >= 20
    except (ValueError, IndexError):
        return False


def detect_pnpm() -> bool:
    return _cmd_exists("pnpm")


def detect_process_compose() -> bool:
    if _cmd_exists("process-compose"):
        return True
    return (Path.home() / ".local" / "bin" / "process-compose").exists()


def detect_gh() -> bool:
    return _cmd_exists("gh")


def detect_gh_auth() -> bool:
    return _cmd_exists("gh") and _silent_ok(["gh", "auth", "status"])


# ---- Installers --------------------------------------------------------

def install_uv() -> None:
    ui.info("Running: curl -LsSf https://astral.sh/uv/install.sh | sh")
    _run_shell("curl -LsSf https://astral.sh/uv/install.sh | sh")
    ui.ok("uv installer finished (binary at ~/.local/bin/uv)")


def install_sdkman() -> None:
    ui.info("Running: curl -s https://get.sdkman.io | bash")
    _run_shell("curl -s https://get.sdkman.io | bash")
    ui.ok("sdkman installed (~/.sdkman)")


def install_java() -> None:
    if not SDKMAN_INIT.exists():
        raise RuntimeError("sdkman not installed; cannot install Java")
    ui.info(f"Running: sdk install java {JAVA_VERSION}")
    _run_shell(
        f'source "{SDKMAN_INIT}" && '
        f'sdk install java {JAVA_VERSION} < /dev/null'
    )
    ui.ok(f"Java {JAVA_VERSION} installed via sdkman")


def install_quarkus() -> None:
    if not SDKMAN_INIT.exists():
        raise RuntimeError("sdkman not installed; cannot install Quarkus CLI")
    ui.info("Running: sdk install quarkus")
    _run_shell(
        f'source "{SDKMAN_INIT}" && '
        f'sdk install quarkus < /dev/null'
    )
    ui.ok("Quarkus CLI installed via sdkman")


def install_node_and_pnpm() -> None:
    """Install fnm, then Node 22 LTS, then enable pnpm via corepack — all in
    one shell so we don't depend on PATH refresh between steps.
    """
    ui.info("Installing fnm + Node + pnpm in a single shell pass...")
    script = f'''
        set -e
        # Install fnm if not already present
        if ! command -v fnm >/dev/null 2>&1 && \\
           [ ! -f "$HOME/.local/share/fnm/fnm" ] && \\
           [ ! -f "$HOME/.fnm/fnm" ]; then
            echo ">> Installing fnm..."
            curl -fsSL https://fnm.vercel.app/install | bash -s -- --skip-shell
        fi
        # Locate fnm binary
        FNM_BIN=""
        for c in "$HOME/.local/share/fnm/fnm" "$HOME/.fnm/fnm"; do
            if [ -f "$c" ]; then FNM_BIN="$c"; break; fi
        done
        if [ -z "$FNM_BIN" ] && command -v fnm >/dev/null 2>&1; then
            FNM_BIN="$(command -v fnm)"
        fi
        if [ -z "$FNM_BIN" ]; then
            echo "ERROR: fnm not found after install" >&2
            exit 1
        fi
        export PATH="$(dirname "$FNM_BIN"):$PATH"
        eval "$($FNM_BIN env --shell bash)"

        echo ">> Installing Node {NODE_VERSION} LTS..."
        fnm install {NODE_VERSION}
        fnm use {NODE_VERSION}

        echo ">> Enabling pnpm via corepack..."
        corepack enable
        corepack prepare pnpm@latest --activate

        echo "node: $(node --version)"
        echo "pnpm: $(pnpm --version)"
    '''
    _run_shell(script)
    ui.ok(f"Node {NODE_VERSION} LTS + pnpm installed via fnm")


def install_pnpm_only() -> None:
    """If node already exists but pnpm doesn't — enable via corepack."""
    ui.info("Enabling pnpm via corepack on existing node install...")
    _run_shell("corepack enable && corepack prepare pnpm@latest --activate")
    ui.ok("pnpm enabled")


def install_process_compose() -> None:
    target_dir = Path.home() / ".local" / "bin"
    target_dir.mkdir(parents=True, exist_ok=True)
    ui.info(f"Installing process-compose to {target_dir} via official installer...")
    _run_shell(
        f'curl -fsSL '
        f'https://raw.githubusercontent.com/F1bonacc1/process-compose/main/scripts/get-pc.sh '
        f'| sh -s -- -d "{target_dir}"'
    )
    ui.ok(f"process-compose installed at {target_dir}/process-compose")


def install_gh() -> None:
    if _is_macos():
        if not _cmd_exists("brew"):
            raise RuntimeError(
                "Homebrew not found — install Homebrew (https://brew.sh) "
                "or install gh manually before re-running."
            )
        ui.info("Running: brew install gh")
        _run_shell("brew install gh")
    elif _is_linux():
        if _cmd_exists("apt"):
            ui.info("Installing gh via apt with the GitHub CLI repo...")
            # Per https://github.com/cli/cli/blob/trunk/docs/install_linux.md
            _run_shell('''
                set -e
                type -p curl >/dev/null || sudo apt install -y curl
                curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \\
                    | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
                sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
                echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \\
                    | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
                sudo apt update
                sudo apt install -y gh
            ''')
        elif _cmd_exists("dnf"):
            ui.info("Installing gh via dnf with the GitHub CLI repo...")
            _run_shell('''
                set -e
                sudo dnf install -y dnf-plugins-core
                sudo dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo
                sudo dnf install -y gh
            ''')
        else:
            raise RuntimeError("No supported package manager (apt/dnf) found on this Linux host.")
    else:
        raise RuntimeError(f"Unsupported platform: {platform.system()}")
    ui.ok("gh installed")


def install_gh_auth() -> None:
    if not _cmd_exists("gh"):
        raise RuntimeError("gh not on PATH — install gh first, then re-run.")
    ui.info("Launching `gh auth login` (interactive)...")
    subprocess.run(["gh", "auth", "login"])  # interactive; do not capture
    if not detect_gh_auth():
        raise RuntimeError(
            "gh auth still not active after the interactive flow. "
            "Run `gh auth login` manually and re-run check."
        )


# ---- Prereq registry ---------------------------------------------------

@dataclass
class Prereq:
    name: str
    detect: Callable[[], bool]
    install: Callable[[], None] | None  # None => hard stop, no auto-install
    install_hint: str
    notes: str = ""
    needs_shell_refresh: bool = False  # If True, we expect re-check after install
                                       # to fail until user opens a new shell.


def get_prereqs() -> list[Prereq]:
    return [
        # ---- Hard stops ----
        Prereq(
            name="docker",
            detect=detect_docker,
            install=None,
            install_hint="(no auto-install — Docker setup is per-developer)",
            notes="Install Docker Desktop / Engine before re-running.",
        ),
        Prereq(
            name="git",
            detect=detect_git,
            install=None,
            install_hint="(no auto-install — should be present on any dev machine)",
            notes="Install git via your OS package manager.",
        ),
        # ---- Auto-installable ----
        Prereq(
            name="uv",
            detect=detect_uv,
            install=install_uv,
            install_hint="uv (Python package manager) via astral.sh installer",
            needs_shell_refresh=True,
        ),
        Prereq(
            name="sdkman",
            detect=detect_sdkman,
            install=install_sdkman,
            install_hint="sdkman (JVM toolchain manager) via get.sdkman.io",
            needs_shell_refresh=True,
        ),
        Prereq(
            name="java",
            detect=detect_java,
            install=install_java,
            install_hint=f"Java {JAVA_VERSION} via sdkman",
            needs_shell_refresh=True,
        ),
        Prereq(
            name="quarkus-cli",
            detect=detect_quarkus_cli,
            install=install_quarkus,
            install_hint="Quarkus CLI via sdkman",
            needs_shell_refresh=True,
        ),
        Prereq(
            name="node+pnpm",
            detect=lambda: detect_node() and detect_pnpm(),
            install=install_node_and_pnpm,
            install_hint=f"fnm + Node {NODE_VERSION} LTS + pnpm (via corepack)",
            needs_shell_refresh=True,
        ),
        Prereq(
            name="process-compose",
            detect=detect_process_compose,
            install=install_process_compose,
            install_hint="process-compose binary into ~/.local/bin",
            needs_shell_refresh=True,
        ),
        Prereq(
            name="gh",
            detect=detect_gh,
            install=install_gh,
            install_hint="GitHub CLI via your OS package manager (apt/dnf/brew)",
        ),
        Prereq(
            name="gh-auth",
            detect=detect_gh_auth,
            install=install_gh_auth,
            install_hint="Interactive `gh auth login` (browser or device flow)",
            notes="Required for HTTPS git operations and private-repo access.",
        ),
    ]


# ---- Main flow ---------------------------------------------------------

def run_check(interactive: bool = True, skip_install: bool = False) -> int:
    ui.header("Prerequisite check")

    prereqs = get_prereqs()
    missing_hardstop: list[Prereq] = []
    missing_installable: list[Prereq] = []

    for p in prereqs:
        if p.detect():
            ui.ok(p.name)
        elif p.install is None:
            missing_hardstop.append(p)
            ui.error(f"{p.name} -- MISSING (hard stop)")
            if p.notes:
                ui.plain(f"        {p.notes}")
        else:
            missing_installable.append(p)
            ui.warn(f"{p.name} -- missing")
            ui.plain(f"        would install: {p.install_hint}")

    if missing_hardstop:
        ui.header("Cannot proceed")
        for p in missing_hardstop:
            ui.error(f"{p.name}: {p.notes or 'install manually'}")
        return 1

    if not missing_installable:
        ui.plain("")
        ui.ok("All prereqs satisfied.")
        return 0

    if skip_install:
        ui.plain("")
        ui.warn(f"{len(missing_installable)} prereq(s) missing; --skip-install set.")
        return 1

    ui.header("The following will be installed")
    for p in missing_installable:
        ui.plain(f"  - {p.name}: {p.install_hint}")
    ui.plain("")

    if interactive:
        if not ui.confirm("Proceed with installation?", default=True):
            ui.warn("Skipped. Install missing tools manually then re-run.")
            return 1

    ui.header("Installing")
    failed: list[str] = []
    for p in missing_installable:
        ui.plain("")
        ui.info(f"-- {p.name} --")
        try:
            p.install()
        except subprocess.CalledProcessError as e:
            ui.error(f"Install of {p.name} failed (exit {e.returncode})")
            failed.append(p.name)
        except Exception as e:
            ui.error(f"Install of {p.name} failed: {e}")
            failed.append(p.name)

    if failed:
        ui.header("Some installs failed")
        for n in failed:
            ui.error(n)
        return 1

    ui.header("Re-checking")
    needs_refresh: list[str] = []
    still_missing: list[str] = []
    for p in missing_installable:
        if p.detect():
            ui.ok(p.name)
        elif p.needs_shell_refresh:
            needs_refresh.append(p.name)
            ui.warn(f"{p.name}: needs shell refresh to detect (PATH not yet exported)")
        else:
            still_missing.append(p.name)
            ui.error(f"{p.name}: still not detected after install")

    if still_missing:
        ui.header("Some prereqs still missing after install")
        for n in still_missing:
            ui.error(n)
        return 1

    if needs_refresh:
        ui.header("Open a new shell and re-run")
        ui.plain("These prereqs were installed but their PATH/init scripts")
        ui.plain("have not been sourced into this shell:")
        for n in needs_refresh:
            ui.plain(f"  - {n}")
        ui.plain("")
        ui.plain("Open a new terminal (so ~/.bashrc / ~/.zshrc re-source)")
        ui.plain("and run:  ./bootstrap.sh check")
        return 2  # non-zero to signal "more work needed"

    ui.plain("")
    ui.ok("All prereqs installed and detected.")
    return 0
