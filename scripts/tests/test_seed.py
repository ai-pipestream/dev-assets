"""Seed behaviour, with an emphasis on not destroying local work.

`seed` used to delete the destination before copying and protect only `.env`.
That meant a hand-edit to ~/.pipeline/dev/process-compose.yaml — the file the
running grid is actually driven by — disappeared on the next seed with no
warning and no copy. These tests pin the replacement behaviour.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib import seed  # noqa: E402


@pytest.fixture()
def files(tmp_path: Path) -> tuple[Path, Path]:
    """A source file and a destination path under a temp dir."""
    src = tmp_path / "src" / "process-compose.yaml"
    src.parent.mkdir()
    src.write_text("version: '0.5'\nprocesses: {}\n")
    dst = tmp_path / "dst" / "process-compose.yaml"
    dst.parent.mkdir()
    return src, dst


def test_copy_creates_missing_destination(files):
    src, dst = files
    assert seed._copy(src, dst, dry_run=False)
    assert dst.read_text() == src.read_text()


def test_copy_backs_up_a_locally_modified_destination(files):
    src, dst = files
    dst.write_text("version: '0.5'\n# my hand-edit that must survive\n")

    assert seed._copy(src, dst, dry_run=False)

    assert dst.read_text() == src.read_text(), "source should now be installed"
    backups = list(dst.parent.glob("process-compose.yaml.local-*.bak"))
    assert len(backups) == 1, f"expected exactly one backup, got {backups}"
    assert "my hand-edit that must survive" in backups[0].read_text()


def test_copy_does_not_back_up_an_identical_destination(files):
    src, dst = files
    dst.write_text(src.read_text())

    assert seed._copy(src, dst, dry_run=False)

    assert list(dst.parent.glob("*.bak")) == [], "identical content needs no backup"


def test_copy_force_skips_the_backup(files):
    src, dst = files
    dst.write_text("# local\n")

    assert seed._copy(src, dst, dry_run=False, force=True)

    assert dst.read_text() == src.read_text()
    assert list(dst.parent.glob("*.bak")) == []


def test_copy_dry_run_touches_nothing(files):
    src, dst = files
    dst.write_text("# local\n")

    assert seed._copy(src, dst, dry_run=True)

    assert dst.read_text() == "# local\n", "dry run must not overwrite"
    assert list(dst.parent.glob("*.bak")) == [], "dry run must not create backups"


def test_copy_replaces_a_leftover_symlink(files, tmp_path):
    src, dst = files
    other = tmp_path / "elsewhere.yaml"
    other.write_text("# symlink target\n")
    dst.symlink_to(other)

    assert seed._copy(src, dst, dry_run=False)

    assert not dst.is_symlink()
    assert dst.read_text() == src.read_text()
    assert other.read_text() == "# symlink target\n", "must not write through the link"


def test_copy_sets_the_executable_bit_on_scripts(tmp_path):
    src = tmp_path / "dev-grid-health.sh"
    src.write_text("#!/usr/bin/env bash\nexit 0\n")
    src.chmod(0o644)
    dst = tmp_path / "out" / "dev-grid-health.sh"
    dst.parent.mkdir()

    assert seed._copy(src, dst, dry_run=False)

    assert dst.stat().st_mode & 0o111, "a seeded .sh must be executable"


def test_missing_source_is_a_skip_not_a_failure(tmp_path):
    assert seed._copy(tmp_path / "nope.yml", tmp_path / "out.yml", dry_run=False)
    assert not (tmp_path / "out.yml").exists()


def test_backup_paths_do_not_collide(files):
    src, dst = files
    first = seed._backup_path(dst)
    first.write_text("x")
    second = seed._backup_path(dst)
    assert second != first


def test_seaweedfs_config_is_no_longer_seeded():
    """The S3-compat container is rustfs; the seaweedfs auth file is gone.

    Leaving it in the list would only produce a "source missing" warning on
    every seed, which trains people to ignore the warnings that matter.
    """
    assert "seaweedfs-s3-config.json" not in seed._ROOT_FILES


def test_health_gate_is_seeded():
    """`bootstrap all` runs ~/.pipeline/dev/dev-grid-health.sh, so seed must
    install it — otherwise the one-shot's final gate is missing on exactly the
    fresh machine it exists for."""
    assert "dev-grid-health.sh" in seed._DEV_FILES


def test_tmux_launchers_come_from_this_repo():
    """They lived only on one developer's disk until they were imported here."""
    assets = Path(__file__).resolve().parents[2] / "assets" / "dev"
    for name in seed._DEV_ASSET_FILES:
        assert (assets / name).is_file(), f"{name} missing from assets/dev/"
