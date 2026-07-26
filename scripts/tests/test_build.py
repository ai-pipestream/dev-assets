"""Prebuild ordering and repo selection.

The point of the prebuild phase is that the seed repo is built first and alone,
and that nothing which is not a gradle build is ever handed to ./gradlew.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib import build, manifest  # noqa: E402


def _ws():
    return manifest.load()


def test_seed_repo_is_excluded_from_the_prebuild():
    """It was already built with publishToMavenLocal in phase 1; building it
    again with `classes` would be wasted time on the critical path."""
    names = {r.name for r in build.gradle_repos(_ws())}
    assert "pipestream-platform" not in names


def test_frontend_is_not_handed_to_gradle():
    ws = _ws()
    names = {r.name for r in build.gradle_repos(ws)}
    assert build.FRONTEND_REPO not in names


def test_data_repos_are_not_handed_to_gradle():
    """Court fixtures, corpora and the deploy trees have no gradlew that the
    prebuild should drive (compose-stack's gradle build publishes a resources
    jar and is not part of warming the dev grid)."""
    repos = build.gradle_repos(_ws())
    for r in repos:
        assert not r.path.startswith("main/core-services/test-docs"), r.name
        assert not r.path.startswith("main/deploy"), r.name
        assert r.name not in ("dev-assets", "corpus-data", "sample-documents"), r.name


def test_prebuild_covers_the_services_the_grid_runs():
    """Every `quarkus dev` process in the dev grid must be prebuilt, or its cold
    compile lands back on the readiness-probe critical path."""
    names = {r.name for r in build.gradle_repos(_ws())}
    for svc in ("pipestream-engine", "repository-service", "account-service",
                "connector-admin", "connector-intake-service",
                "platform-registration-service", "pipestream-opensearch",
                "module-echo", "module-parser", "module-chunker",
                "pipestream-embedder", "module-opensearch-sink",
                "module-semantic-graph", "module-quality",
                "module-testing-sidecar", "jdbc-connector", "s3-connector"):
        assert svc in names, f"{svc} runs in the dev grid but is never prebuilt"


def test_prebuild_task_is_not_a_full_build():
    """`classes` compiles and resolves without building jars or running tests —
    the cheapest task that takes `quarkus dev` off a cold start."""
    assert build._PREBUILD_TASK == "classes"


def test_protos_checkout_resolution(tmp_path, monkeypatch):
    """The frontend's protobuf codegen should use the workspace checkout when
    it exists, so a bare bootstrap needs no token for the private protos repo."""
    ws = _ws()
    repo = ws.repo_named("pipestream-protos")
    assert repo is not None, "pipestream-protos must stay in the manifest"

    import dataclasses
    missing = dataclasses.replace(ws, root=tmp_path)
    assert build._protos_checkout(missing) is None

    (tmp_path / repo.path).mkdir(parents=True)
    (tmp_path / repo.relative_dest()).mkdir()
    assert build._protos_checkout(missing) == tmp_path / repo.relative_dest()
