"""Each grade records which code graded it (the installed checkout's commit), write-once, in its private record."""

from __future__ import annotations

import subprocess
from pathlib import Path

from carbon.challenge_validator import lean_recipe_retention as retention

ROOT = Path(__file__).resolve().parents[2]


def _git_out(*args):
    done = subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=False
    )
    return done.stdout.strip() if done.returncode == 0 else None


def test_the_record_names_the_installed_commit_tree_and_build_inputs_digest():
    retention._installed_commit.cache_clear()
    record = retention._installed_commit()
    assert record["schema"] == retention.INSTALLED_COMMIT_SCHEMA
    head = _git_out("rev-parse", "HEAD")
    if head is None:
        assert record["commit"] is None and "not a readable git" in record["reason"]
        return
    assert (record["commit"], record["tree"]) == (
        head,
        _git_out("rev-parse", "HEAD^{tree}"),
    )
    assert record["build_inputs_digest"].startswith("sha256:")


def test_an_install_that_is_not_a_checkout_records_null_and_why_never_a_guess(
    monkeypatch,
):
    def refuse(*args, **kwargs):
        raise OSError("no git")

    monkeypatch.setattr(retention.subprocess, "check_output", refuse)
    retention._installed_commit.cache_clear()
    try:
        record = retention._installed_commit()
    finally:
        retention._installed_commit.cache_clear()
    assert record["commit"] is None and record["tree"] is None
    assert record["build_inputs_digest"] is None and record["reason"]


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
