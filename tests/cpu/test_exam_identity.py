"""H2 deploy precheck: a release never changes a door's exam silently (scripts/dev/release/exam_identity.py)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts/dev/release/exam_identity.py"
PACK_A, PACK_B = "a" * 64, "sha256:" + "b" * 64
RULE = """import re
GRADING_PATHS = (
    "carbon/reconstruction/",
    "carbon/scoring/",
)
_GRADING_MODULE = re.compile(r"carbon/challenge_validator/[a-z0-9_]+_hidden\\.py")
"""


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


def _commit(repo, files, message, *, remove=()):
    for rel in remove:
        _git(repo, "rm", "-q", rel)
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


BASE_FILES = {
    "carbon/challenge_validator/direct_receiver.py": RULE,
    "carbon/challenge_validator/exam_cap.py": "CAP = 1\n",
    "carbon/challenge_validator/f02_hidden.py": "SIDES = 1\n",
    "carbon/reconstruction/worker/build_inputs.txt": "pyproject.toml\ncarbon/reconstruction/worker/run.py\n",
    "carbon/reconstruction/worker/run.py": "RUN = 1\n",
    "carbon/scoring/pool_grader.py": "MARGIN = 1\n",
    "pyproject.toml": "[project]\n",
    "docs/notes.md": "a\n",
}


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    return root, _commit(root, BASE_FILES, "base")


def _check(tool, root, old, new, **kw):
    kw.setdefault("old_pack", PACK_A)
    kw.setdefault("new_pack", PACK_A)
    return tool.check(root, old, new, **kw)


def test_a_change_outside_the_grading_paths_is_the_same_exam(tool, repo):
    root, base = repo
    new = _commit(root, {"docs/notes.md": "b\n", "scripts/x.sh": "echo\n"}, "docs")
    out = _check(tool, root, base, new)
    assert out["state"] == tool.SAME and tool.EXIT[out["state"]] == 0
    assert out["grading_paths_changed"] == [] and out["build_inputs_moved"] is False
    assert out["grading_rule_changed"] is False and out["grading_rule_absent_at"] == []
    assert out["old_grading_digest"] == out["new_grading_digest"]
    assert (out["old"], out["new"]) == (base, new)


def test_the_digest_follows_file_contents_never_the_commit(tool, repo):
    root, base = repo
    again = _commit(root, {}, "an empty commit: new id, same files")
    assert tool.grading_digest(root, base) == tool.grading_digest(root, again)
    moved = _commit(root, {"carbon/scoring/pool_grader.py": "MARGIN = 2\n"}, "grading")
    assert tool.grading_digest(root, moved) != tool.grading_digest(root, base)


def test_a_grading_path_change_is_refused_unless_declared(tool, repo):
    root, base = repo
    new = _commit(root, {"carbon/scoring/pool_grader.py": "MARGIN = 2\n"}, "grading")
    out = _check(tool, root, base, new)
    assert out["state"] == tool.CHANGE and tool.EXIT[out["state"]] == 3
    assert out["grading_paths_changed"] == ["carbon/scoring/pool_grader.py"]
    declared = _check(tool, root, base, new, declared="new exam version 1.8")
    assert declared["state"] == tool.DECLARED and tool.EXIT[declared["state"]] == 0
    assert declared["declared"] == "new exam version 1.8"


def test_a_build_input_alone_is_an_exam_change(tool, repo):
    root, base = repo
    new = _commit(root, {"pyproject.toml": "[project]\nname = 'x'\n"}, "image input")
    out = _check(tool, root, base, new)
    assert out["state"] == tool.CHANGE
    assert out["build_inputs_moved"] is True and out["grading_paths_changed"] == []


def test_a_file_named_only_by_the_module_pattern_is_seen(tool, repo):
    root, base = repo
    new = _commit(
        root, {"carbon/challenge_validator/f02_hidden.py": "SIDES = 2\n"}, "hidden"
    )
    out = _check(tool, root, base, new)
    assert out["state"] == tool.CHANGE
    assert out["grading_paths_changed"] == ["carbon/challenge_validator/f02_hidden.py"]


@pytest.mark.parametrize("kind", ["delete", "rename_out", "mode_only"])
def test_deletes_renames_and_mode_changes_are_seen(tool, repo, kind):
    root, base = repo
    path = "carbon/scoring/pool_grader.py"
    if kind == "delete":
        new = _commit(root, {}, "delete", remove=[path])
    elif kind == "rename_out":
        _git(root, "mv", path, "docs/pool_grader.py")
        new = _commit(root, {}, "rename")
    else:
        _git(root, "update-index", "--chmod=+x", path)
        _git(root, "commit", "-q", "-m", "mode")
        new = _git(root, "rev-parse", "HEAD")
    out = _check(tool, root, base, new)
    assert out["state"] == tool.CHANGE and path in out["grading_paths_changed"]


def test_new_editing_the_rule_is_an_exam_change(tool, repo):
    root, base = repo
    widened = RULE.replace(
        '"carbon/scoring/",',
        '"carbon/scoring/",\n    "carbon/challenge_validator/exam_cap.py",',
    )
    new = _commit(
        root,
        {
            "carbon/challenge_validator/direct_receiver.py": widened,
            "carbon/challenge_validator/exam_cap.py": "CAP = 2\n",
        },
        "exam_cap becomes a grading path and changes",
    )
    out = _check(tool, root, base, new)
    assert out["state"] == tool.CHANGE and out["grading_rule_changed"] is True
    assert "carbon/challenge_validator/exam_cap.py" in out["grading_paths_changed"]


def test_a_revision_before_the_rule_is_judged_by_the_other_sides(tool, repo):
    root, _ = repo
    pre = _commit(
        root, {"carbon/challenge_validator/direct_receiver.py": "X = 1\n"}, "pre-M2"
    )
    post = _commit(
        root, {"carbon/challenge_validator/direct_receiver.py": RULE}, "M2 lands"
    )
    out = _check(tool, root, pre, post)
    assert out["state"] == tool.SAME and out["grading_rule_absent_at"] == ["old"]
    changed = _commit(
        root, {"carbon/scoring/pool_grader.py": "MARGIN = 5\n"}, "grading"
    )
    assert _check(tool, root, pre, changed)["state"] == tool.CHANGE
    gone = _commit(
        root, {"carbon/challenge_validator/direct_receiver.py": "X = 2\n"}, "no rule"
    )
    assert _check(tool, root, pre, gone)["state"] == tool.UNKNOWN


def test_packs_are_required_and_compared(tool, repo):
    root, base = repo
    new = _commit(root, {"docs/notes.md": "c\n"}, "docs")
    out = _check(tool, root, base, new, old_pack=PACK_A, new_pack=PACK_B)
    assert out["state"] == tool.CHANGE and out["pack_changed"] is True
    assert out["new_pack"] == "b" * 64
    for bad in (None, "", "xyz", "A" * 64):
        with pytest.raises(ValueError):
            _check(tool, root, base, new, new_pack=bad)
    with pytest.raises(SystemExit) as usage:
        tool.main(["check", "--repo", str(root), "--old", base, "--new", new])
    assert usage.value.code == 2


def test_symbolic_refs_resolve_and_are_never_cached(tool, repo):
    root, base = repo
    _git(root, "branch", "old", base)
    _git(root, "branch", "new", base)
    first = _check(tool, root, "old", "new")
    assert (
        first["state"] == tool.SAME
        and first["new"] == base
        and first["new_ref"] == "new"
    )
    moved = _commit(root, {"carbon/scoring/pool_grader.py": "MARGIN = 9\n"}, "grading")
    _git(root, "branch", "-f", "new", moved)
    second = _check(tool, root, "old", "new")
    assert second["state"] == tool.CHANGE and second["new"] == moved


@pytest.mark.parametrize("rev", ["0" * 40, "--output=/tmp/x", "no-such-branch"])
def test_an_unknown_revision_refuses(tool, repo, rev):
    root, base = repo
    out = _check(tool, root, base, rev)
    assert out["state"] == tool.UNKNOWN and tool.EXIT[out["state"]] == 4


@pytest.mark.skipif(os.name == "nt", reason="symlinks need Linux here")
def test_a_symlink_under_a_grading_path_refuses(tool, repo):
    root, base = repo
    os.symlink("../../docs/notes.md", root / "carbon/scoring/linked.py")
    new = _commit(root, {}, "link")
    out = _check(tool, root, base, new)
    assert (
        out["state"] == tool.UNKNOWN and out["reason"] == "symlink_under_grading_path"
    )


def test_the_parsed_rule_is_the_receivers_own(tool):
    """The ast read of this checkout's rule equals what direct_receiver.grading_path uses."""
    from carbon.challenge_validator import direct_receiver

    paths, pattern = tool.parse_rule((ROOT / tool.RULE_FILE).read_bytes())
    assert paths == direct_receiver.GRADING_PATHS
    assert pattern == direct_receiver._GRADING_MODULE.pattern


def test_the_cli_exit_codes_and_json(tool, repo, capsys):
    root, base = repo
    new = _commit(root, {"carbon/scoring/pool_grader.py": "MARGIN = 3\n"}, "grading")
    packs = ["--old-pack", PACK_A, "--new-pack", PACK_A]
    assert (
        tool.main(["check", "--repo", str(root), "--old", base, "--new", new, *packs])
        == 3
    )
    assert json.loads(capsys.readouterr().out)["state"] == tool.CHANGE
    declared = ["--declared-exam-change", "ruled: new versions only"]
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
                *packs,
                *declared,
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["declared"] == "ruled: new versions only"
    assert (
        tool.main(
            ["check", "--repo", str(root), "--old", base, "--new", "0" * 40, *packs]
        )
        == 4
    )
    assert json.loads(capsys.readouterr().out)["state"] == tool.UNKNOWN
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
                *packs,
                "--declared-exam-change",
                " ",
            ]
        )
    assert tool.main(["digest", "--repo", str(root), "--rev", base]) == 0
    assert json.loads(capsys.readouterr().out)["grading_digest"].startswith("sha256:")
    assert (
        tool.main(["digest", "--repo", str(tmp := root / "nope"), "--rev", "HEAD"]) == 4
    )
    assert not tmp.exists()
