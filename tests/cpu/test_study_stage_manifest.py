"""The staged-revision gate that replaced `git rev-parse` inside the pinned image.

The worker image has no `git`, so the study's checkout arrives on a mounted
volume and its identity is established by recomputing a digest of the tree. That
makes `verify` a refusal path rather than a convenience: if it passes on a tree
that is not the named revision, every result the session produces is attributed
to code that did not run. These cases are the ways that could happen.
"""

from pathlib import Path

import pytest

from scripts.dev.gpu_determinism_study.stage_manifest import (
    MANIFEST,
    tree_digest,
    verify,
    write,
)

REVISION = "a9315b99c18188db4953bce0c16a310d99fdfb0b"


@pytest.fixture
def staged(tmp_path: Path) -> Path:
    repo = tmp_path / "carbon"
    (repo / "carbon").mkdir(parents=True)
    (repo / "carbon" / "service.py").write_text("def reconstruct(): ...\n")
    (repo / "README.md").write_text("carbon\n")
    write(repo, REVISION)
    return repo


def test_a_staged_tree_verifies_against_its_own_revision(staged: Path) -> None:
    assert verify(staged, REVISION) == []


def test_a_different_revision_is_refused(staged: Path) -> None:
    problems = verify(staged, "deadbeef")
    assert problems
    assert "staged revision" in problems[0]


def test_an_edited_file_moves_the_digest(staged: Path) -> None:
    (staged / "carbon" / "service.py").write_text("def reconstruct(): return 1\n")
    problems = verify(staged, REVISION)
    assert any("tree digest" in problem for problem in problems)


def test_an_added_file_moves_the_digest(staged: Path) -> None:
    (staged / "carbon" / "extra.py").write_text("")
    assert any("tree digest" in problem for problem in verify(staged, REVISION))


def test_a_deleted_file_moves_the_digest(staged: Path) -> None:
    (staged / "README.md").unlink()
    assert any("tree digest" in problem for problem in verify(staged, REVISION))


def test_a_renamed_file_moves_the_digest_though_its_contents_did_not(
    staged: Path,
) -> None:
    """Path is hashed with content, so relocating code is a change."""
    (staged / "carbon" / "service.py").rename(staged / "carbon" / "reconstruct.py")
    assert any("tree digest" in problem for problem in verify(staged, REVISION))


def test_a_missing_manifest_is_refused_rather_than_assumed_absent_means_clean(
    staged: Path,
) -> None:
    (staged.parent / MANIFEST).unlink()
    problems = verify(staged, REVISION)
    assert problems
    assert "no staged revision manifest" in problems[0]


def test_an_unreadable_manifest_is_refused(staged: Path) -> None:
    (staged.parent / MANIFEST).write_text("{not json")
    assert any("not readable JSON" in problem for problem in verify(staged, REVISION))


def test_a_manifest_from_another_schema_is_refused(staged: Path) -> None:
    path = staged.parent / MANIFEST
    path.write_text(path.read_text().replace("carbon.study.staged-revision.v1", "v0"))
    assert any("schema" in problem for problem in verify(staged, REVISION))


def test_skipped_directories_do_not_enter_the_digest(staged: Path) -> None:
    """`.git` and build caches differ between clones while the source does not.

    A shallow clone and a full one of the same revision must verify identically,
    so their contents are excluded - otherwise the gate would refuse correct
    checkouts, which is the failure that gets a guard disabled.
    """
    before = tree_digest(staged)
    (staged / ".git").mkdir()
    (staged / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (staged / "carbon" / "__pycache__").mkdir()
    (staged / "carbon" / "__pycache__" / "service.pyc").write_bytes(b"\x00")
    assert tree_digest(staged) == before
    assert verify(staged, REVISION) == []


def test_a_symlink_is_recorded_by_target_rather_than_followed(staged: Path) -> None:
    """A link that points somewhere new is a change even where the file is not."""
    link = staged / "current.py"
    link.symlink_to("carbon/service.py")
    write(staged, REVISION)
    link.unlink()
    link.symlink_to("README.md")
    assert any("tree digest" in problem for problem in verify(staged, REVISION))
