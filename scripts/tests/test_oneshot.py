"""`bootstrap all` phase ordering, skipping, and the final gate.

The health gate is the reason this command exists, so the tests here care most
about it running last and its exit code being the command's exit code.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib import manifest, oneshot  # noqa: E402


@pytest.fixture()
def recorded(monkeypatch):
    """Replace every phase with a recorder; returns the list of phases run."""
    calls: list[str] = []

    def phase(name, rc=0):
        def run(*_args, **_kwargs):
            calls.append(name)
            return rc
        return run

    monkeypatch.setattr(oneshot.prereqs, "run_check", phase("check"))
    monkeypatch.setattr(oneshot.git_sync, "sync", phase("clone"))
    monkeypatch.setattr(oneshot.build, "build_all", phase("build"))
    monkeypatch.setattr(oneshot.seed, "seed", phase("seed"))
    monkeypatch.setattr(oneshot.dev_compose, "up", phase("dev-up"))
    monkeypatch.setattr(oneshot, "_health_gate", phase("health"))
    return calls


def test_all_runs_every_phase_in_order(recorded):
    rc = oneshot.run_all(manifest.load())
    assert rc == 0
    assert recorded == ["check", "clone", "build", "seed", "dev-up", "health"]


def test_health_gate_runs_last(recorded):
    oneshot.run_all(manifest.load())
    assert recorded[-1] == "health", "the gate must run after the grid is up"


def test_skip_removes_only_the_named_phases(recorded):
    oneshot.run_all(manifest.load(), skip=frozenset({"check", "clone"}))
    assert recorded == ["build", "seed", "dev-up", "health"]


def test_no_dev_up_also_skips_the_gate(recorded):
    """There is nothing to gate on when the grid was never started; running the
    gate anyway would report a failure that is not one."""
    oneshot.run_all(manifest.load(), dev_up=False)
    assert recorded == ["check", "clone", "build", "seed"]


def test_unknown_skip_phase_is_rejected(recorded):
    rc = oneshot.run_all(manifest.load(), skip=frozenset({"compile"}))
    assert rc == 64
    assert recorded == [], "nothing should run when the arguments are wrong"


def test_a_failing_phase_stops_the_run(monkeypatch):
    calls: list[str] = []

    def ok(name):
        def run(*_a, **_k):
            calls.append(name)
            return 0
        return run

    def fails(*_a, **_k):
        calls.append("build")
        return 7

    monkeypatch.setattr(oneshot.prereqs, "run_check", ok("check"))
    monkeypatch.setattr(oneshot.git_sync, "sync", ok("clone"))
    monkeypatch.setattr(oneshot.build, "build_all", fails)
    monkeypatch.setattr(oneshot.seed, "seed", ok("seed"))
    monkeypatch.setattr(oneshot.dev_compose, "up", ok("dev-up"))
    monkeypatch.setattr(oneshot, "_health_gate", ok("health"))

    rc = oneshot.run_all(manifest.load())
    assert rc == 7, "the failing phase's exit code is the command's exit code"
    assert calls == ["check", "clone", "build"], "later phases must not run"


def test_stale_path_after_prereq_install_stops_the_run(monkeypatch):
    """run_check returns 2 for 'installed but not on this shell's PATH'. Every
    later phase shells out to those tools, so continuing would fail confusingly."""
    calls: list[str] = []
    monkeypatch.setattr(oneshot.prereqs, "run_check", lambda **_k: 2)
    monkeypatch.setattr(oneshot.git_sync, "sync",
                        lambda *_a, **_k: calls.append("clone") or 0)

    rc = oneshot.run_all(manifest.load())
    assert rc == 2
    assert calls == []


def test_health_gate_fails_loudly_when_not_seeded(monkeypatch, tmp_path):
    monkeypatch.setattr(oneshot, "HEALTH_GATE", tmp_path / "dev-grid-health.sh")
    assert oneshot._health_gate(0) == 70


def test_health_gate_exit_code_is_passed_through(monkeypatch, tmp_path):
    gate = tmp_path / "dev-grid-health.sh"
    gate.write_text("#!/usr/bin/env bash\nexit 3\n")
    gate.chmod(0o755)
    monkeypatch.setattr(oneshot, "HEALTH_GATE", gate)
    assert oneshot._health_gate(0) == 3


def test_health_gate_passes_the_wait_deadline(monkeypatch, tmp_path):
    gate = tmp_path / "dev-grid-health.sh"
    gate.write_text('#!/usr/bin/env bash\n[ "$1" = "--wait" ] && [ "$2" = "42" ]\n')
    gate.chmod(0o755)
    monkeypatch.setattr(oneshot, "HEALTH_GATE", gate)
    assert oneshot._health_gate(42) == 0


def test_phase_names_match_the_documented_order():
    assert oneshot.PHASES == ("check", "clone", "build", "seed", "dev-up", "health")


def test_pc_port_comes_from_the_env_file(tmp_path):
    """PC_PORT_NUM in the .env only feeds yaml templating — process-compose
    itself defaults to 8080 unless the port is passed explicitly, which made
    dev-up serve on 8080 while the health gate polled 8765 and declared a
    running grid dead. The launcher and the gate both read this value."""
    from lib import dev_compose

    env = tmp_path / ".env"
    env.write_text("FOO=bar\nPC_PORT_NUM=9911\n")
    assert dev_compose.pc_port(env) == "9911"
    # missing file or missing key falls back to the seeded default
    assert dev_compose.pc_port(tmp_path / "absent") == "8765"
    env.write_text("PC_PORT_NUM=\n")
    assert dev_compose.pc_port(env) == "8765"
