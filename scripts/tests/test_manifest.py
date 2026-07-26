"""The repo manifest has to reproduce this workspace, not most of it.

A clone that silently omits the compose stack, the release train or the court
fixtures produces a tree that looks fine and cannot bring up the docker stack,
cut a release, or run the e2e battery.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib import manifest  # noqa: E402


def _ws():
    return manifest.load()


def test_manifest_loads():
    ws = _ws()
    assert ws.repos, "manifest has no repos"
    assert ws.ref_repos, "manifest has no reference repos"


def test_repo_destinations_are_unique():
    dests = [r.relative_dest() for r in _ws().repos]
    dupes = {d for d in dests if dests.count(d) > 1}
    assert not dupes, f"two manifest entries clone into the same directory: {dupes}"


def test_deploy_repos_are_in_the_manifest():
    """Without these a fresh clone cannot bring up the stack or cut a release."""
    dests = {r.relative_dest() for r in _ws().repos}
    assert "main/deploy/compose-stack" in dests
    assert "main/deploy/release" in dests


def test_build_conventions_is_in_the_manifest():
    names = {r.name for r in _ws().repos}
    assert "pipestream-build-conventions" in names


def test_court_fixture_repos_are_in_the_manifest():
    """The e2e suite consumes these per-stage corpora; there is no single
    test-docs repo, so each stage repo needs its own entry."""
    dests = {r.relative_dest() for r in _ws().repos}
    for stage in ("chunker-input-court", "embedder-input-court",
                  "opensearch-sink-input-court", "semantic-graph-input-court",
                  "pipedocs-court-1000"):
        assert f"main/core-services/test-docs/{stage}" in dests, f"missing {stage}"


def test_dead_proto_tools_entry_is_gone():
    """pipestream-proto-tools was deleted from Forgejo; leaving the entry made
    `bootstrap clone` fail on a 404 for every fresh machine."""
    assert "pipestream-proto-tools" not in {r.name for r in _ws().repos}


def test_exactly_one_build_first_repo():
    """The seed build is serial on purpose. More than one build_first repo is
    fine mechanically but is almost always an accident."""
    seeds = [r.name for r in _ws().repos if r.build_first]
    assert seeds == ["pipestream-platform"], seeds


def test_clone_urls_point_at_forgejo():
    ws = _ws()
    for r in ws.repos:
        url = r.clone_url(ws.clone_protocol, ws.forgejo_org)
        assert manifest.FORGEJO_HOST in url, f"{r.name} does not clone from Forgejo"
        assert "github.com" not in url, f"{r.name} still points at the GitHub mirror"
