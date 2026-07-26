"""Prereq registry coverage.

The registry is the contract for what a fresh machine needs. Two tools the dev
grid cannot start without were missing from it: `bun` (the frontend BFF process
is literally `bun --watch src/index.ts`) and `buf` (the frontend's protobuf
codegen).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib import prereqs  # noqa: E402


def _names():
    return [p.name for p in prereqs.get_prereqs()]


def test_bun_is_checked():
    assert "bun" in _names()


def test_buf_is_checked():
    assert "buf" in _names()


def test_every_prereq_has_a_detector():
    for p in prereqs.get_prereqs():
        assert callable(p.detect), f"{p.name} has no detector"


def test_every_prereq_has_a_hint():
    for p in prereqs.get_prereqs():
        assert p.install_hint, f"{p.name} has no install hint"


def test_hard_stops_explain_themselves():
    """A prereq with no installer must say what the human should do instead."""
    for p in prereqs.get_prereqs():
        if p.install is None:
            assert p.notes, f"{p.name} is a hard stop with no guidance"


def test_prereq_names_are_unique():
    names = _names()
    assert len(names) == len(set(names))


def test_bun_detector_finds_a_non_path_install(monkeypatch, tmp_path):
    """bun installs to ~/.bun/bin, which is not on PATH until a new shell."""
    monkeypatch.setattr(prereqs, "_cmd_exists", lambda _c: False)
    monkeypatch.setattr(prereqs.Path, "home", staticmethod(lambda: tmp_path))
    assert prereqs.detect_bun() is False

    bun = tmp_path / ".bun" / "bin" / "bun"
    bun.parent.mkdir(parents=True)
    bun.write_text("")
    assert prereqs.detect_bun() is True


def test_buf_detector_finds_a_non_path_install(monkeypatch, tmp_path):
    monkeypatch.setattr(prereqs, "_cmd_exists", lambda _c: False)
    monkeypatch.setattr(prereqs.Path, "home", staticmethod(lambda: tmp_path))
    assert prereqs.detect_buf() is False

    buf = tmp_path / ".local" / "bin" / "buf"
    buf.parent.mkdir(parents=True)
    buf.write_text("")
    assert prereqs.detect_buf() is True
