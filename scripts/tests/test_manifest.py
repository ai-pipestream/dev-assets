"""The repo manifest has to reproduce this workspace, not most of it.

A clone that silently omits the compose stack, the release train or the court
fixtures produces a tree that looks fine and cannot bring up the docker stack,
cut a release, or run the e2e battery.
"""
from __future__ import annotations

import dataclasses
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
    ws = _ws()
    dests = {r.relative_dest() for r in ws.repos}
    assert f"{ws.tree}/deploy/compose-stack" in dests
    assert f"{ws.tree}/deploy/release" in dests


def test_workspace_tree_relocates_the_whole_layout(tmp_path, monkeypatch):
    """workspace.tree swaps the first path segment for every repo and
    reference repo: an integration box clones the same manifest under
    /work/integration instead of /work/main, nothing else moves."""
    base = _ws()
    override_dir = tmp_path / "ai-pipestream"
    override_dir.mkdir()
    (override_dir / "workspace.toml").write_text('[workspace]\ntree = "integration"\n')
    monkeypatch.setattr(manifest, "_USER_OVERRIDE_PATH", override_dir / "workspace.toml")
    ws = manifest.load()
    assert ws.tree == "integration"
    assert all(r.path.split("/", 1)[0] == "integration" for r in ws.repos)
    assert all(r.ref_path == "integration/reference-code" for r in ws.ref_repos)
    # the tail of every path is untouched
    assert {r.path.partition("/")[2] for r in ws.repos} == \
        {r.path.partition("/")[2] for r in base.repos}


def test_build_conventions_is_in_the_manifest():
    names = {r.name for r in _ws().repos}
    assert "pipestream-build-conventions" in names


def test_court_fixture_repos_are_in_the_manifest():
    """The e2e suite consumes these per-stage corpora; there is no single
    test-docs repo, so each stage repo needs its own entry."""
    ws = _ws()
    dests = {r.relative_dest() for r in ws.repos}
    for stage in ("chunker-input-court", "embedder-input-court",
                  "opensearch-sink-input-court", "semantic-graph-input-court",
                  "pipedocs-court-1000"):
        assert f"{ws.tree}/core-services/test-docs/{stage}" in dests, f"missing {stage}"


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
        # Repos carrying an explicit url live outside the Forgejo org by
        # design (the GitHub-hosted grpc-services), so they are exempt. Without
        # this the assertion has failed for every one of them since the
        # grpc-services category was added.
        if r.url:
            continue
        url = r.clone_url(ws.clone_protocol, ws.forgejo_org, ws.git_host)
        assert manifest.FORGEJO_HOST in url, f"{r.name} does not clone from Forgejo"
        assert "github.com" not in url, f"{r.name} still points at the GitHub mirror"


def test_git_host_override_redirects_only_forgejo_repos():
    ws = dataclasses.replace(_ws(), git_host="github.com")
    for r in ws.repos:
        url = r.clone_url(ws.clone_protocol, ws.forgejo_org, ws.git_host)
        if r.url:
            assert url == r.url, f"{r.name}'s explicit url was rewritten"
        else:
            assert "github.com" in url, f"{r.name} ignored the git_host override"
