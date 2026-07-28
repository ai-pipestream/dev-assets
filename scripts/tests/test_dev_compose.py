"""dev-up's port preflight: the grid must not launch over its own orphans.

When a grid is killed instead of torn down, the service JVMs survive on the
ports process-compose.yaml declares. The next `dev-up` then half-fails: the new
processes die on "address already in use" while the ORPHANS keep answering
readiness probes, so dev-grid-health.sh goes green against ghosts running stale
config (a zombie module-embedder with pre-fix routing served zero models on a
"healthy" grid). These tests pin the refusal, the offender table's contents, and
the escape hatch.

The held-port tests open a REAL listening socket rather than mocking the
kernel: the whole point of the preflight is that it agrees with what a service
would find when it tries to bind.
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap  # noqa: E402
from lib import dev_compose  # noqa: E402

YAML = """\
version: "0.5"

processes:

  # a comment that must not be parsed as anything
  pipestream-engine:
    command: quarkus dev
    readiness_probe:
      http_get:
        host: localhost
        port: ${PIPESTREAM_ENGINE_HTTP_PORT:-18100}
        path: /q/health/ready
      period_seconds: 5
    availability:
      restart: "no"

  module-echo:
    command: quarkus dev
    environment:
      - SOME_PORT=${NOT_A_PROBE_PORT:-19999}
    readiness_probe:
      http_get:
        host: localhost
        port: ${MODULE_ECHO_HTTP_PORT:-19100}
        path: /q/health/ready
      failure_threshold: 60

  dev-services:
    command: dev-services up
    readiness_probe:
      exec:
        command: check-infra-healthy.sh
      period_seconds: 3
"""


@pytest.fixture()
def grid(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    """A seeded-looking process-compose.yaml plus its .env.

    The ambient environment is cleared of the names the fixture yaml
    references: process-compose expands them from the .env, and a developer
    who happens to export one must not change what these tests assert.
    """
    for name in ("PC_PORT_NUM", "PIPESTREAM_ENGINE_HTTP_PORT",
                 "MODULE_ECHO_HTTP_PORT", "NOT_A_PROBE_PORT"):
        monkeypatch.delenv(name, raising=False)
    yaml = tmp_path / "process-compose.yaml"
    yaml.write_text(YAML)
    env = tmp_path / ".env"
    env.write_text("# generated\nPC_PORT_NUM=8765\n")
    return yaml, env


@pytest.fixture()
def listening() -> socket.socket:
    """A real listening socket on a kernel-assigned localhost port.

    No SO_REUSEADDR anywhere: the question the preflight answers is "could a
    service take this port", and reusing the address would answer a different
    one.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    yield sock
    sock.close()


def _declare(yaml: Path, port: int) -> None:
    """Point the fixture yaml's engine probe at a literal port."""
    yaml.write_text(YAML.replace("${PIPESTREAM_ENGINE_HTTP_PORT:-18100}", str(port)))


def _free_port() -> int:
    """A port nothing is listening on (bound to learn it, then released)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ── what the yaml declares ───────────────────────────────────────────────────

def test_declared_ports_uses_the_template_default_when_the_env_is_silent(grid):
    yaml, env = grid
    ports = dev_compose.declared_ports(yaml, env)
    assert ports[18100] == ["pipestream-engine"]
    assert ports[19100] == ["module-echo"]


def test_declared_ports_prefers_the_env_over_the_template_default(grid):
    """process-compose expands ${VAR:-default} against this .env, so a machine
    that moved a service must be preflighted on the port it actually uses."""
    yaml, env = grid
    env.write_text("PC_PORT_NUM=8765\nPIPESTREAM_ENGINE_HTTP_PORT=28100\n")
    ports = dev_compose.declared_ports(yaml, env)
    assert 28100 in ports
    assert 18100 not in ports, "the template default must not be checked as well"


def test_an_empty_env_value_falls_back_to_the_default(grid):
    """`${VAR:-default}` treats empty as unset — the preflight must agree, or a
    blank line in the .env would silently skip a port."""
    yaml, env = grid
    env.write_text("PIPESTREAM_ENGINE_HTTP_PORT=\n")
    assert 18100 in dev_compose.declared_ports(yaml, env)


def test_the_process_compose_api_port_is_checked_too(grid):
    """PC_PORT_NUM is not in any probe, and it is the port a leftover
    supervisor holds — the case that makes `dev-up` look like it worked."""
    yaml, env = grid
    env.write_text("PC_PORT_NUM=9911\n")
    ports = dev_compose.declared_ports(yaml, env)
    assert ports[9911] == ["process-compose API"]


def test_only_readiness_probe_http_ports_are_collected(grid):
    yaml, env = grid
    ports = dev_compose.declared_ports(yaml, env)
    assert 19999 not in ports, "an environment: entry is not a declared port"
    assert sorted(ports) == [8765, 18100, 19100], "exec probes declare no port"


def test_a_missing_yaml_leaves_only_the_api_port(tmp_path):
    ports = dev_compose.declared_ports(tmp_path / "absent.yaml", tmp_path / "absent")
    assert sorted(ports) == [8765]


# ── who holds them ───────────────────────────────────────────────────────────

def test_a_real_listening_socket_is_reported_with_pid_and_argv(grid, listening):
    yaml, env = grid
    port = listening.getsockname()[1]
    _declare(yaml, port)

    offenders = dev_compose.held_ports(yaml, env)

    held = [o for o in offenders if o.port == port]
    assert len(held) == 1, f"expected {port} held, got {offenders}"
    assert held[0].declared_by == "pipestream-engine"
    assert held[0].pid == os.getpid(), "the test process holds it"
    assert "python" in held[0].argv.lower() or "pytest" in held[0].argv.lower()


def test_a_free_port_is_not_reported(grid):
    """Asserted on the one port this test controls: the fixture's other ports
    are the real grid's, which may legitimately be up on the machine running
    the suite."""
    yaml, env = grid
    free = _free_port()
    _declare(yaml, free)
    assert free not in [o.port for o in dev_compose.held_ports(yaml, env)]


def test_the_bind_probe_finds_the_holder_when_proc_is_unreadable(
        grid, listening, monkeypatch, tmp_path):
    """macOS has no /proc. The fallback asks the kernel the only other way it
    can — by trying to take the port — and still refuses, just without a pid."""
    yaml, env = grid
    port = listening.getsockname()[1]
    _declare(yaml, port)
    monkeypatch.setattr(dev_compose, "PROC", tmp_path / "no-proc-here")

    offenders = dev_compose.held_ports(yaml, env)

    held = [o for o in offenders if o.port == port]
    assert len(held) == 1
    assert held[0].pid is None
    assert "/proc" in held[0].argv


# ── the refusal, and the way out of it ───────────────────────────────────────

@pytest.fixture()
def launcher(monkeypatch):
    """dev_compose.up() with its prerequisites satisfied and the spawn recorded.

    Returns the list of process-compose argv lists that up() actually ran.
    """
    spawned: list[list[str]] = []

    class Result:
        returncode = 0

    monkeypatch.setattr(dev_compose, "_ensure_seeded", lambda: True)
    monkeypatch.setattr(dev_compose, "_ensure_env", lambda: True)
    monkeypatch.setattr(dev_compose.shutil, "which", lambda _: "/usr/bin/process-compose")
    monkeypatch.setattr(dev_compose.subprocess, "run",
                        lambda cmd, **_kw: spawned.append(cmd) or Result())
    return spawned


def _hold(monkeypatch, *offenders: dev_compose.Offender) -> None:
    monkeypatch.setattr(dev_compose, "held_ports", lambda *_a, **_k: list(offenders))


ORPHAN = dev_compose.Offender(19103, "module-embedder", 4242,
                              "/usr/bin/java -jar module-embedder-dev.jar")


def test_up_refuses_to_launch_when_a_declared_port_is_held(launcher, monkeypatch):
    _hold(monkeypatch, ORPHAN)
    assert dev_compose.up() == dev_compose.HELD_PORTS_EXIT
    assert launcher == [], "process-compose must not be spawned over an orphan"


def test_the_refusal_names_the_port_the_pid_and_the_command(
        launcher, monkeypatch, capsys):
    """An offender table you cannot act on is just a different silent failure."""
    _hold(monkeypatch, ORPHAN)
    dev_compose.up()
    out = capsys.readouterr()
    printed = out.out + out.err
    assert "19103" in printed
    assert "4242" in printed
    assert "module-embedder" in printed
    assert "module-embedder-dev.jar" in printed


def test_up_launches_when_every_declared_port_is_free(launcher, monkeypatch):
    _hold(monkeypatch)
    assert dev_compose.up() == 0
    assert len(launcher) == 1
    assert launcher[0][:2] == ["process-compose", "up"]


def test_ignore_held_ports_launches_anyway(launcher, monkeypatch, capsys):
    _hold(monkeypatch, ORPHAN)
    assert dev_compose.up(ignore_held_ports=True) == 0
    assert len(launcher) == 1, "the escape hatch must still start the grid"
    printed = capsys.readouterr()
    assert "19103" in printed.out + printed.err, "and must still print the table"


def test_the_preflight_runs_before_the_launch_not_after(launcher, monkeypatch):
    """Ordering is the whole feature: a check after `process-compose up` would
    report ports held by the processes it just started."""
    order: list[str] = []

    def held(*_a, **_k):
        order.append("preflight")
        return []

    monkeypatch.setattr(dev_compose, "held_ports", held)
    monkeypatch.setattr(dev_compose.subprocess, "run",
                        lambda cmd, **_kw: order.append("spawn") or type(
                            "R", (), {"returncode": 0})())
    dev_compose.up()
    assert order == ["preflight", "spawn"]


def test_dev_up_has_an_escape_hatch_flag_wired_to_the_launcher(monkeypatch):
    """The flag has to survive the argparse -> cmd_dev_up -> up() trip; a
    parser-only flag would silently keep refusing."""
    seen: dict[str, object] = {}
    monkeypatch.setattr(bootstrap.dev_compose, "up",
                        lambda **kwargs: seen.update(kwargs) or 0)

    args = bootstrap.build_parser().parse_args(["dev-up", "--ignore-held-ports"])
    assert args.func(args) == 0
    assert seen == {"detached": True, "ignore_held_ports": True}


def test_dev_up_defaults_to_refusing(monkeypatch):
    seen: dict[str, object] = {}
    monkeypatch.setattr(bootstrap.dev_compose, "up",
                        lambda **kwargs: seen.update(kwargs) or 0)

    args = bootstrap.build_parser().parse_args(["dev-up"])
    args.func(args)
    assert seen["ignore_held_ports"] is False
