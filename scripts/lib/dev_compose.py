"""Wrap process-compose for the dev stack."""
from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
from pathlib import Path
from typing import NamedTuple

from . import ui
from .seed import PIPELINE_DEV_DIR

PROCESS_COMPOSE_YAML = PIPELINE_DEV_DIR / "process-compose.yaml"
ENV_FILE = PIPELINE_DEV_DIR / ".env"

# /proc is the whole dependency budget for "who holds this port": no ss, no
# lsof, no psutil. The two files list every TCP socket (v4 and v6); state 0A
# is TCP_LISTEN, and the inode column ties a socket to the /proc/<pid>/fd
# symlink that owns it.
PROC = Path("/proc")
PROC_NET_TCP = ("net/tcp", "net/tcp6")
_TCP_LISTEN = "0A"

# sysexits.h EX_UNAVAILABLE — the machine is not in a state where the grid can
# start. Distinct from 1 (setup missing) and 64 (bad arguments) so a caller can
# tell "ports are held" from "you never seeded".
HELD_PORTS_EXIT = 69


def pc_port(env_file: Path = ENV_FILE) -> str:
    """The process-compose API port the grid is expected on.

    PC_PORT_NUM in ~/.pipeline/dev/.env is read by process-compose only for
    yaml template substitution — it does NOT set the server's own API port,
    so a bare `process-compose up` serves on its built-in default (8080)
    while the health gate polls the .env's 8765 and reports a dead grid.
    The port must be passed explicitly; every launcher and poller goes
    through this one reader.
    """
    try:
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("PC_PORT_NUM="):
                value = line.split("=", 1)[1].strip()
                if value:
                    return value
    except OSError:
        pass
    return "8765"


class Offender(NamedTuple):
    """One declared grid port that something is already listening on."""

    port: int
    declared_by: str
    pid: int | None
    argv: str


def declared_ports(yaml_path: Path = PROCESS_COMPOSE_YAML,
                   env_file: Path = ENV_FILE) -> dict[int, list[str]]:
    """Every TCP port the seeded grid will try to own, resolved.

    That is each readiness_probe.http_get port in the yaml plus the
    process-compose API port, with ``${VAR:-default}`` expanded against the
    same .env process-compose itself loads (file wins over the ambient
    environment, matching `set -a; . .env`).

    Deliberately a regex pass and not PyYAML: python3 is a hard bootstrap
    dependency, PyYAML is not, and a preflight that cannot run because a
    library is missing is worse than no preflight.

    :param yaml_path: the seeded process-compose.yaml
    :param env_file: the .env whose values expand the yaml's port references
    :return: port -> the names that declared it, ascending
    """
    env = dict(os.environ)
    env.update(_env_values(env_file))
    ports: dict[int, list[str]] = {}
    for name, expr in _probe_port_exprs(yaml_path) + [("process-compose API",
                                                       pc_port(env_file))]:
        resolved = _expand(expr, env)
        try:
            port = int(resolved)
        except ValueError:
            ui.warn(f"{name}: unresolvable port {expr!r} -> {resolved!r} (not checked)")
            continue
        ports.setdefault(port, []).append(name)
    return dict(sorted(ports.items()))


def held_ports(yaml_path: Path = PROCESS_COMPOSE_YAML,
               env_file: Path = ENV_FILE) -> list[Offender]:
    """The declared grid ports something is already listening on.

    :param yaml_path: the seeded process-compose.yaml
    :param env_file: the .env whose values expand the yaml's port references
    :return: one Offender per held port, ascending by port (empty = all free)
    """
    wanted = declared_ports(yaml_path, env_file)
    if not wanted:
        return []
    listening = _listening_inodes()
    offenders: list[Offender] = []
    for port, names in wanted.items():
        declared_by = ", ".join(names)
        if listening is None:
            # No readable /proc (macOS): fall back to asking the kernel the
            # only other way, by trying to take the port ourselves.
            if _bind_probe_held(port):
                offenders.append(Offender(port, declared_by, None,
                                          "(no /proc on this platform)"))
            continue
        inode = listening.get(port)
        if inode is None:
            continue
        pid = _pid_for_inode(inode)
        offenders.append(Offender(port, declared_by, pid, _argv(pid)))
    return offenders


def up(detached: bool = True, ignore_held_ports: bool = False) -> int:
    """Start the grid, refusing when its ports are already held.

    A half-torn-down grid (supervisor killed instead of `process-compose down`)
    leaves orphaned JVMs on the ports the yaml declares. Launching over them is
    the worst possible outcome: the new processes die on "address already in
    use" while the ORPHANS keep answering readiness probes, so the health gate
    goes green against ghosts running stale config. The preflight turns that
    silent ghost-grid into an offender table and a nonzero exit.

    :param detached: run process-compose in the background (default)
    :param ignore_held_ports: launch anyway, held ports and all
    :return: 0 on success, HELD_PORTS_EXIT when ports are held
    """
    if not _ensure_seeded():
        return 1
    if not _ensure_env():
        return 1
    if not shutil.which("process-compose"):
        ui.error("process-compose not on PATH — run `./bootstrap.sh check` first.")
        return 1
    offenders = held_ports()
    if offenders:
        _report_held_ports(offenders)
        if not ignore_held_ports:
            ui.error("Refusing to launch: the grid's ports are not free.")
            ui.info("Recovery: `./bootstrap.sh dev-down` (or `process-compose down`),")
            ui.info("then re-run dev-up — it re-checks. Kill any pid above that")
            ui.info("survives the teardown; those are orphans from a previous grid.")
            ui.info("Override (you will get a mixed grid): dev-up --ignore-held-ports")
            return HELD_PORTS_EXIT
        ui.warn("--ignore-held-ports given: launching over the holders above.")
    cmd = ["process-compose", "up", "-f", str(PROCESS_COMPOSE_YAML),
           "--port", pc_port()]
    if detached:
        cmd.append("--detached")
    ui.info(f"cwd: {PIPELINE_DEV_DIR}")
    ui.info(f"running: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(PIPELINE_DEV_DIR)).returncode


def down() -> int:
    if not shutil.which("process-compose"):
        ui.error("process-compose not on PATH")
        return 1
    cmd = ["process-compose", "down", "-f", str(PROCESS_COMPOSE_YAML),
           "--port", pc_port()]
    ui.info(f"cwd: {PIPELINE_DEV_DIR}")
    ui.info(f"running: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(PIPELINE_DEV_DIR)).returncode


def _report_held_ports(offenders: list[Offender]) -> None:
    """Print the offender table: what is held, by whom, running what."""
    ui.error(f"{len(offenders)} dev-grid port(s) already held:")
    ui.plain("")
    ui.plain(f"  {'PORT':<7}{'PID':<9}{'DECLARED BY':<26}COMMAND")
    for o in offenders:
        pid = str(o.pid) if o.pid is not None else "?"
        ui.plain(f"  {o.port:<7}{pid:<9}{o.declared_by[:25]:<26}{_trim(o.argv)}")
    ui.plain("")


def _trim(argv: str, width: int = 96) -> str:
    return argv if len(argv) <= width else argv[: width - 3] + "..."


# A process header sits at exactly two spaces: "  name:". The shape is fixed by
# process-compose's own schema, and dev-grid-health.sh reads the same one.
_PROCESS_HEADER = re.compile(r"^([A-Za-z0-9_.-]+):$")
_HTTP_FIELD = re.compile(r"^(host|port|path):\s*(.+)$")
# ${VAR}, ${VAR:-default} and bare $VAR — the only shell syntax the yaml uses.
_VAR_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^{}]*))?\}"
                      r"|\$([A-Za-z_][A-Za-z0-9_]*)")


def _probe_port_exprs(yaml_path: Path) -> list[tuple[str, str]]:
    """Every readiness_probe.http_get port in the yaml, unexpanded.

    :param yaml_path: the seeded process-compose.yaml
    :return: (process name, raw port expression) in file order
    """
    try:
        lines = Path(yaml_path).read_text().splitlines()
    except OSError:
        return []
    out: list[tuple[str, str]] = []
    proc: str | None = None
    in_probe = in_http = False
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        header = _PROCESS_HEADER.match(stripped)
        if header and indent == 2:
            proc, in_probe, in_http = header.group(1), False, False
            continue
        if indent <= 2:
            continue
        if stripped == "readiness_probe:":
            in_probe, in_http = True, False
            continue
        if in_probe and stripped == "http_get:":
            in_http = True
            continue
        if in_probe and stripped.endswith(":") and indent <= 4:
            # another key at readiness_probe's level ends the probe block
            in_probe = in_http = False
            continue
        if in_http:
            field = _HTTP_FIELD.match(stripped)
            if field:
                if field.group(1) == "port" and proc:
                    out.append((proc, field.group(2).strip().strip('"').strip("'")))
            elif indent <= 6 and stripped.endswith(":"):
                in_http = False
    return out


def _env_values(env_file: Path) -> dict[str, str]:
    """KEY=VALUE pairs from the dev .env (comments and blanks skipped)."""
    values: dict[str, str] = {}
    try:
        text = Path(env_file).read_text()
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            values[key] = value.strip().strip('"').strip("'")
    return values


def _expand(expr: str, env: dict[str, str]) -> str:
    """Resolve ``${VAR:-default}`` / ``${VAR}`` / ``$VAR`` against env.

    An empty value counts as unset, exactly as ``:-`` does in the shell that
    process-compose expands these with.
    """

    def one(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(3)
        value = env.get(name)
        if value:
            return value
        return match.group(2) or ""

    out = expr
    for _ in range(5):  # nested defaults; converges long before the bound
        expanded = _VAR_REF.sub(one, out)
        if expanded == out:
            break
        out = expanded
    return out.strip()


def _listening_inodes() -> dict[int, str] | None:
    """port -> socket inode for every TCP socket in LISTEN state.

    Any listening address counts: a service binding localhost:18100 collides
    with an orphan on 0.0.0.0:18100 just the same.

    :return: the map, or None when /proc/net/tcp* is unreadable (not Linux)
    """
    found: dict[int, str] = {}
    readable = False
    for name in PROC_NET_TCP:
        try:
            text = (PROC / name).read_text()
        except OSError:
            continue
        readable = True
        for line in text.splitlines()[1:]:
            fields = line.split()
            if len(fields) < 10 or fields[3] != _TCP_LISTEN:
                continue
            try:
                port = int(fields[1].rsplit(":", 1)[1], 16)
            except (IndexError, ValueError):
                continue
            found.setdefault(port, fields[9])
    return found if readable else None


def _pid_for_inode(inode: str) -> int | None:
    """The pid holding a socket inode, by walking /proc/<pid>/fd symlinks.

    :return: the pid, or None when no process we may read owns it (another
        user's process, or one that exited between the two reads)
    """
    target = f"socket:[{inode}]"
    for entry in _proc_pids():
        try:
            fds = list((PROC / entry / "fd").iterdir())
        except OSError:
            continue  # not ours, or gone
        for fd in fds:
            try:
                if os.readlink(fd) == target:
                    return int(entry)
            except OSError:
                continue
    return None


def _proc_pids() -> list[str]:
    try:
        return [p.name for p in PROC.iterdir() if p.name.isdigit()]
    except OSError:
        return []


def _argv(pid: int | None) -> str:
    """The holder's command line, so the table says WHAT is squatting."""
    if pid is None:
        return "(no readable owner in /proc)"
    try:
        raw = (PROC / str(pid) / "cmdline").read_bytes()
    except OSError:
        return "(exited)"
    argv = [a for a in raw.decode("utf-8", "replace").split("\0") if a]
    if argv:
        return " ".join(argv)
    try:  # kernel threads have an empty cmdline
        return "[" + (PROC / str(pid) / "comm").read_text().strip() + "]"
    except OSError:
        return "(unknown)"


def _bind_probe_held(port: int) -> bool:
    """Whether the port is taken, asked by trying to bind it.

    No SO_REUSEADDR: the question is "could a service take this port", and
    reusing the address would answer a different one.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        return False
    except OSError:
        return True
    finally:
        sock.close()


def _ensure_seeded() -> bool:
    if PROCESS_COMPOSE_YAML.exists():
        return True
    ui.error(f"{PROCESS_COMPOSE_YAML} not found.")
    ui.info("Run `./bootstrap.sh seed` first.")
    return False


def _ensure_env() -> bool:
    if ENV_FILE.exists():
        return True
    example = PIPELINE_DEV_DIR / "process-compose.env.example"
    ui.error(f"{ENV_FILE} does not exist.")
    if example.exists():
        ui.info(f"Copy and edit the template: cp {example} {ENV_FILE}")
    else:
        ui.info("Run `./bootstrap.sh seed` to generate a default .env")
    return False


def e2e_smoke(ws) -> int:
    """Run the two proving E2E scenarios against the local dev grid.

    goldenPath (file connector demo pipeline: deploy -> upload -> repository
    -> traces -> teardown) and demoJdbcSeed (CDC seed -> replication slot
    lifecycle on the demo database). Both run the frontend regression suite's
    live leg against this machine's BFF, so a pass proves the grid end to
    end: module catalog, embedding backends, engine, repository, OpenSearch,
    the demo database seed and the jdbc connector's CDC path.

    :param ws: the loaded workspace (locates the frontend checkout)
    :return: 0 when both scenarios pass
    """
    fe_dir = ws.root / ws.tree / "frontend" / "pipestream-frontend"
    app_dir = fe_dir / "apps" / "pipestream-frontend"
    if not (app_dir / "package.json").exists():
        ui.error(f"frontend checkout missing: {app_dir}")
        return 1
    if not shutil.which("pnpm"):
        ui.error("pnpm not on PATH — run `./bootstrap.sh check` first.")
        return 1
    env = dict(os.environ,
               FE_BASE_URL="http://localhost:38106",
               REGRESSION_LEG="live")
    ui.header("E2E smoke (goldenPath + demoJdbcSeed, live leg)")
    rc = 0
    for scenario in ("goldenPath", "demoJdbcSeed"):
        cmd = ["pnpm", "-C", str(app_dir), "test:regression", scenario]
        ui.info(f"running: {' '.join(cmd)}")
        r = subprocess.run(cmd, cwd=str(fe_dir), env=env).returncode
        if r != 0:
            ui.error(f"{scenario} FAILED (exit {r})")
            rc = 1
        else:
            ui.info(f"{scenario} passed")
    return rc
