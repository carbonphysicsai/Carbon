"""A branch candidate is exact local DEVELOPMENT source, never a main release."""

from __future__ import annotations

import hashlib
import subprocess

import pytest

from carbon.development_session import research_campaign


def _git(repo, *args, text=True):
    return subprocess.check_output(
        ["git", *args], cwd=repo, text=text, timeout=10
    ).strip()


def _candidate(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Carbon Test")
    _git(repo, "config", "user.email", "carbon-test@example.invalid")
    (repo / ".gitignore").write_text("*.pyc\nbuild/\ndist/\n.venv/\n.pytest_cache/\n")
    (repo / "source.txt").write_text("main\n")
    _git(repo, "add", ".gitignore", "source.txt")
    _git(repo, "commit", "-qm", "base")
    _git(
        repo, "update-ref", "refs/remotes/origin/main", _git(repo, "rev-parse", "HEAD")
    )
    _git(repo, "checkout", "-qb", "development-candidate")
    (repo / "source.txt").write_text("candidate\n")
    _git(repo, "add", "source.txt")
    _git(repo, "commit", "-qm", "candidate")
    revision = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    archive = subprocess.check_output(
        ["git", "archive", "--format=tar", "HEAD"], cwd=repo, timeout=10
    )
    source_digest = "sha256:" + hashlib.sha256(archive).hexdigest()
    return repo, revision, tree, source_digest


def _checked(repo, revision, tree, source_digest):
    return research_campaign.development_candidate_implementation(
        revision,
        expected_tree=tree,
        expected_source_tree_digest=source_digest,
        repository=repo,
    )


def test_exact_clean_non_main_candidate_is_explicitly_development(
    tmp_path, monkeypatch
):
    repo, revision, tree, source_digest = _candidate(tmp_path)
    assert _checked(repo, revision, tree, source_digest) == {
        "revision": revision,
        "tree": tree,
        "source_tree_digest": source_digest,
        "source_authority": "DEVELOPMENT_CANDIDATE",
    }
    # The normal release caller still requires fetched main for this same
    # commit. Changing the helper must never make a branch an accepted release.
    monkeypatch.setattr(
        research_campaign,
        "__file__",
        repo / "carbon/development_session/research_campaign.py",
    )
    with pytest.raises(ValueError, match="not in fetched main"):
        research_campaign.accepted_implementation(revision)


@pytest.mark.parametrize("field", ["revision", "tree", "source_digest"])
def test_candidate_rejects_mismatched_identity(tmp_path, field):
    repo, revision, tree, source_digest = _candidate(tmp_path)
    values = {"revision": revision, "tree": tree, "source_digest": source_digest}
    original = values[field]
    values[field] = original[:-1] + ("0" if original[-1] != "0" else "1")
    message = {
        "revision": "exact clean revision",
        "tree": "tree differs",
        "source_digest": "source archive differs",
    }[field]
    with pytest.raises(ValueError, match=message):
        _checked(repo, values["revision"], values["tree"], values["source_digest"])


def test_candidate_rejects_tracked_and_untracked_drift(tmp_path):
    repo, revision, tree, source_digest = _candidate(tmp_path)
    (repo / "source.txt").write_text("changed after commit\n")
    with pytest.raises(ValueError, match="exact clean revision"):
        _checked(repo, revision, tree, source_digest)
    _git(repo, "restore", "source.txt")
    (repo / "untracked.py").write_text("print('extra source')\n")
    with pytest.raises(ValueError, match="exact clean revision"):
        _checked(repo, revision, tree, source_digest)


@pytest.mark.parametrize(
    "path",
    [
        "carbon/hidden.pyc",
        "carbon/build/extension.so",
        "scripts/dist/override.py",
        "build/extension.so",
        "dist/override.py",
    ],
)
def test_candidate_rejects_ignored_runtime_bytes(tmp_path, path):
    repo, revision, tree, source_digest = _candidate(tmp_path)
    ignored = repo / path
    ignored.parent.mkdir(parents=True)
    ignored.write_bytes(b"untracked runtime bytes")
    assert not _git(repo, "status", "--porcelain", "--untracked-files=all")
    with pytest.raises(ValueError, match="ignored runtime source"):
        _checked(repo, revision, tree, source_digest)


def test_candidate_allows_only_isolated_environment_and_cache(tmp_path):
    repo, revision, tree, source_digest = _candidate(tmp_path)
    for name in (".venv/lib/dependency.py", ".pytest_cache/v/cache/nodeids"):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("isolated tool state\n")
    assert _checked(repo, revision, tree, source_digest)["revision"] == revision


def test_candidate_rejects_malformed_identity_before_git(tmp_path):
    with pytest.raises(ValueError, match="identity is malformed"):
        _checked(tmp_path, "A" * 40, "b" * 40, "sha256:" + "c" * 64)
