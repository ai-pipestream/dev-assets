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


FORGEJO_HOST = "git.rokkon.com"


@dataclass(frozen=True)
class Repo:
    path: str            # e.g. "main/core-services"
    name: str            # e.g. "pipestream-platform" — the Forgejo repo name
    dir_name: str = ""   # on-disk directory name, if different from `name`
                          # (e.g. a repo renamed upstream but the checkout
                          # stays put since other config points there)
    branch: str = "main"
    build_first: bool = False

    def dest(self, root: Path) -> Path:
        return root / self.path / (self.dir_name or self.name)

    def relative_dest(self) -> str:
        return f"{self.path}/{self.dir_name or self.name}"

    def clone_url(self, protocol: str, org: str) -> str:
        if protocol == "ssh":
            return f"git@{FORGEJO_HOST}:{org}/{self.name}.git"
        return f"https://{FORGEJO_HOST}/{org}/{self.name}.git"


@dataclass(frozen=True)
class RefRepo:
    """An OSS reference repo — full git URL, never built, lives at
    <root>/<tree>/reference-code/<name>. Vendored for grep / upstream-patch
    workflows; not part of any platform build.
    """
    name: str
    url: str
    branch: str = ""    # "" = remote default branch
    ref_path: str = "main/reference-code"

    def dest(self, root: Path) -> Path:
        return root / self.ref_path / self.name

    def relative_dest(self) -> str:
        return f"{self.ref_path}/{self.name}"


@dataclass(frozen=True)
class Workspace:
    root: Path
    tree: str            # first path segment under root ("main", "integration")
    m2_repo: Path
    jdk: str
    clone_protocol: str
    parallelism: int
    forgejo_org: str
    repos: tuple[Repo, ...]
    ref_repos: tuple[RefRepo, ...]

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
    tree = str(ws.get("tree", "main")).strip().strip("/") or "main"

    m2_str = str(ws.get("m2_repo", "")).strip()
    if m2_str:
        m2_repo = Path(m2_str).expanduser()
    else:
        # default: <home>/.m2/repository (the maven convention)
        m2_repo = Path.home() / ".m2" / "repository"

    # Manifest paths are written against the canonical "main" tree; a
    # different workspace.tree (e.g. "integration") relocates the whole
    # layout by swapping that first segment. Only the leading segment is
    # rewritten — nothing inside a repo path ever changes.
    def _retree(path: str) -> str:
        head, _, tail = path.partition("/")
        if head == "main" and tree != "main":
            return f"{tree}/{tail}" if tail else tree
        return path

    repos = tuple(
        Repo(
            path=_retree(r["path"]),
            name=r["name"],
            dir_name=r.get("dir_name", ""),
            branch=r.get("branch", "main"),
            build_first=r.get("build_first", False),
        )
        for r in cfg.get("repo", [])
    )

    ref_repos = tuple(
        RefRepo(
            name=r["name"],
            url=r["url"],
            branch=r.get("branch", ""),
            ref_path=f"{tree}/reference-code",
        )
        for r in cfg.get("ref_repo", [])
    )

    return Workspace(
        root=root,
        tree=tree,
        m2_repo=m2_repo,
        jdk=str(ws.get("jdk", "25-tem")),
        clone_protocol=str(ws.get("clone_protocol", "https")),
        parallelism=int(ws.get("parallelism", 8)),
        forgejo_org=str(ws.get("forgejo_org", "ai-pipestream")),
        repos=repos,
        ref_repos=ref_repos,
    )
