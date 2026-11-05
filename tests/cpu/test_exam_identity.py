"""H2 deploy precheck: a release never changes a door's exam silently (scripts/dev/release/exam_identity.py)."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[2] / "scripts/dev/release/exam_identity.py"


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("exam_identity_tool", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo, files, message):
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    base = _commit(
        root,
        {
            "carbon/reconstruction/worker/build_inputs.txt": "carbon/reconstruction/worker/run.py\n",
            "carbon/reconstruction/worker/run.py": "RUN = 1\n",
            "carbon/scoring/pool_grader.py": "MARGIN = 1\n",
            "docs/notes.md": "a\n",
        },
        "base",
    )
    return root, base


def test_a_change_outside_the_grading_paths_is_the_same_exam(tool, repo):
    root, base = repo
    new = _commit(root, {"docs/notes.md": "b\n", "scripts/x.sh": "echo\n"}, "docs")
    out = tool.check(root, base, new)
    assert out["state"] == tool.SAME and tool.EXIT[out["state"]] == 0
    assert out["grading_paths_changed"] == [] and out["build_inputs_moved"] is False
    assert out["old_grading_digest"] == out["new_grading_digest"]


def test_the_digest_follows_file_contents_never_the_commit(tool, repo):
    root, base = repo
    again = _commit(root, {}, "an empty commit: new id, same files")
    assert tool.grading_digest(root, base) == tool.grading_digest(root, again)
    moved = _commit(root, {"carbon/scoring/pool_grader.py": "MARGIN = 2\n"}, "grading")
    assert tool.grading_digest(root, moved) != tool.grading_digest(root, base)


def test_a_grading_path_change_is_refused_unless_declared(tool, repo):
    root, base = repo
    new = _commit(root, {"carbon/scoring/pool_grader.py": "MARGIN = 2\n"}, "grading")
    out = tool.check(root, base, new)
    assert out["state"] == tool.CHANGE and tool.EXIT[out["state"]] == 2
    assert out["grading_paths_changed"] == ["carbon/scoring/pool_grader.py"]
    declared = tool.check(root, base, new, declared="new exam version 1.8")
    assert declared["state"] == tool.DECLARED and tool.EXIT[declared["state"]] == 0
    assert declared["declared"] == "new exam version 1.8"


def test_a_build_input_change_is_an_exam_change(tool, repo):
    root, base = repo
    new = _commit(root, {"carbon/reconstruction/worker/run.py": "RUN = 2\n"}, "image")
    out = tool.check(root, base, new)
    assert out["state"] == tool.CHANGE and out["build_inputs_moved"] is True


def test_a_pack_change_alone_is_an_exam_change(tool, repo):
    root, base = repo
    new = _commit(root, {"docs/notes.md": "c\n"}, "docs")
    same = tool.check(root, base, new, old_pack="a" * 64, new_pack="a" * 64)
    assert same["state"] == tool.SAME and same["pack_compared"] is True
    out = tool.check(root, base, new, old_pack="a" * 64, new_pack="b" * 64)
    assert out["state"] == tool.CHANGE and out["pack_changed"] is True
    with pytest.raises(ValueError):
        tool.check(root, base, new, old_pack="a" * 64)


def test_an_unknown_revision_refuses(tool, repo):
    root, base = repo
    out = tool.check(root, base, "0" * 40)
    assert out["state"] == tool.UNKNOWN and tool.EXIT[out["state"]] == 3


def test_the_cli_exit_codes(tool, repo, capsys):
    root, base = repo
    new = _commit(root, {"carbon/scoring/pool_grader.py": "MARGIN = 3\n"}, "grading")
    assert tool.main(["check", "--repo", str(root), "--old", base, "--new", new]) == 2
    assert (
        tool.main(
            [
                "check",
                "--repo",
                str(root),
                "--old",
                base,
                "--new",
                new,
                "--declared-exam-change",
                "ruled: new versions only",
            ]
        )
        == 0
    )
    with pytest.raises(SystemExit):
        tool.main(
            [
                "check",
                "--repo",
                str(root),
                "--old",
                base,
                "--new",
                new,
                "--declared-exam-change",
                " ",
            ]
        )
    assert tool.main(["digest", "--repo", str(root), "--rev", base]) == 0
    assert "sha256:" in capsys.readouterr().out
