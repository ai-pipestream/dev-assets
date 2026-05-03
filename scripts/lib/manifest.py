"""Workspace + manifest config loading.

Reads `config/workspace.toml` shipped with this repo and merges in
optional per-machine overrides from `~/.config/ai-pipestream/workspace.toml`
(or `$XDG_CONFIG_HOME/ai-pipestream/workspace.toml`).
"""
from __future__ import annotations

import dataclasses
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

# Path to defaults shipped in this repo.
_DEFAULTS_PATH = Path(__file__).resolve().parents[2] / "config" / "workspace.toml"

# Per-machine override location.
_USER_OVERRIDE_PATH = (
    Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    / "ai-pipestream" / "workspace.toml"
)


@dataclass(frozen=True)
class Repo:
    path: str            # e.g. "main/core-services"
    name: str            # e.g. "pipestream-platform"
    branch: str = "main"
    build_first: bool = False

    def dest(self, root: Path) -> Path:
        return root / self.path / self.name

    def relative_dest(self) -> str:
        return f"{self.path}/{self.name}"

    def clone_url(self, protocol: str, org: str) -> str:
        if protocol == "ssh":
            return f"git@github.com:{org}/{self.name}.git"
        return f"https://github.com/{org}/{self.name}.git"


@dataclass(frozen=True)
class Workspace:
    root: Path
    m2_repo: Path
    jdk: str
    clone_protocol: str
    parallelism: int
    github_org: str
    repos: tuple[Repo, ...]

    def repo_named(self, name: str) -> Repo | None:
        for r in self.repos:
            if r.name == name:
                return r
        return None

    def with_protocol(self, protocol: str) -> "Workspace":
        return dataclasses.replace(self, clone_protocol=protocol)


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        elif isinstance(v, list) and isinstance(out.get(k), list):
            # For arrays-of-tables (e.g. [[repo]]), override fully replaces.
            out[k] = v
        else:
            out[k] = v
    return out


def defaults_path() -> Path:
    return _DEFAULTS_PATH


def user_override_path() -> Path:
    return _USER_OVERRIDE_PATH


def load() -> Workspace:
    if not _DEFAULTS_PATH.exists():
        raise FileNotFoundError(
            f"Defaults config missing: {_DEFAULTS_PATH}"
        )

    defaults = _load_toml(_DEFAULTS_PATH)
    overrides = _load_toml(_USER_OVERRIDE_PATH)
    cfg = _merge(defaults, overrides)

    ws = cfg.get("workspace", {})
    root = Path(str(ws.get("root", "/work"))).expanduser()

    m2_str = str(ws.get("m2_repo", "")).strip()
    if m2_str:
        m2_repo = Path(m2_str).expanduser()
    else:
        # default: <home>/.m2/repository (the maven convention)
        m2_repo = Path.home() / ".m2" / "repository"

    repos = tuple(
        Repo(
            path=r["path"],
            name=r["name"],
            branch=r.get("branch", "main"),
            build_first=r.get("build_first", False),
        )
        for r in cfg.get("repo", [])
    )

    return Workspace(
        root=root,
        m2_repo=m2_repo,
        jdk=str(ws.get("jdk", "25-tem")),
        clone_protocol=str(ws.get("clone_protocol", "https")),
        parallelism=int(ws.get("parallelism", 8)),
        github_org=str(ws.get("github_org", "ai-pipestream")),
        repos=repos,
    )
