"""Each grade records which code graded it (the installed checkout's commit), write-once, in its private record."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.reconstruction.worker import build_inputs

ROOT = Path(__file__).resolve().parents[2]


def _git(repo, *args):
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            *args,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture
def small_repo(tmp_path, monkeypatch):
    if shutil.which("git") is None:
        pytest.skip("needs git")
    monkeypatch.setattr(build_inputs, "digest", lambda repo: "sha256:" + "0" * 64)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "tracked.txt").write_text("a\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def test_a_clean_checkout_records_commit_tree_and_dirty_false(small_repo):
    record = retention.read_installed_commit(small_repo)
    assert record["schema"] == retention.INSTALLED_COMMIT_SCHEMA
    assert record["commit"] == _git(small_repo, "rev-parse", "HEAD")
    assert record["tree"] == _git(small_repo, "rev-parse", "HEAD^{tree}")
    assert record["dirty"] is False
    assert record["build_inputs_digest"] == "sha256:" + "0" * 64


def test_a_modified_tracked_file_is_dirty_but_an_untracked_file_is_not(small_repo):
    (small_repo / "untracked.txt").write_text("u\n")
    assert retention.read_installed_commit(small_repo)["dirty"] is False
    (small_repo / "tracked.txt").write_text("changed\n")
    record = retention.read_installed_commit(small_repo)
    assert record["dirty"] is True
    assert record["commit"] == _git(small_repo, "rev-parse", "HEAD")


def test_a_path_that_is_not_a_checkout_records_null_and_why_never_a_guess(tmp_path):
    record = retention.read_installed_commit(tmp_path / "missing")
    assert record["commit"] is None and record["tree"] is None
    assert record["dirty"] is None and record["build_inputs_digest"] is None
    assert record["reason"]


def test_the_record_is_read_once_at_module_load_not_at_the_first_grade(
    small_repo, monkeypatch
):
    loaded = retention._INSTALLED_COMMIT
    assert retention._installed_commit() is loaded
    # a checkout that moves after the process started does not change what the grade records
    monkeypatch.setattr(
        retention, "read_installed_commit", lambda repo: pytest.fail("re-read")
    )
    (small_repo / "tracked.txt").write_text("moved\n")
    _git(small_repo, "commit", "-q", "-am", "move")
    assert retention._installed_commit() is loaded


def test_the_sidecar_is_written_once_right_after_the_private_binding():
    source = (ROOT / "carbon/challenge_validator/lean_recipe_retention.py").read_text(
        encoding="utf-8"
    )
    binding = source.index("write_once(binding_path, _json(binding))")
    sidecar = source.index(
        "write_once(directory / INSTALLED_COMMIT_SIDECAR, _json(_installed_commit()))"
    )
    assert 0 < sidecar - binding < 200
    assert retention.INSTALLED_COMMIT_SIDECAR == "grade-installed-commit.json"


def test_the_receiver_loads_the_retention_module_at_its_start():
    """lean_recipe_retention is otherwise imported lazily (first grade); serve() imports it before anything else runs."""
    source = (ROOT / "carbon/challenge_validator/direct_receiver.py").read_text(
        encoding="utf-8"
    )
    start = source.index("def serve(")
    body = source[start:]
    loaded = body.index("from carbon.challenge_validator import lean_recipe_retention")
    assert body.index("cpu_pin.require()") < loaded
    assert loaded < body.index("cfg = load_config(config_path)")
