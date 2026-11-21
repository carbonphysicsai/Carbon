"""Over-broad rules audit S7 L3 (case-procs, 21 Nov 2026): narrowed retention refusals, each keeping its protection.

- 190: a retention directory THIS user owns that has group/other bits is made 0700 and kept (it ends owner-only, as the
  check requires); another owner, a link or a non-directory still refuses.
- 196: a crown decision that raised before it was made is filed PAUSED for the crown sweep (write-once), never dropped;
  nothing retained to decide from files nothing; a failing filing never changes the refusal.
Synthetic fixtures only.
"""

from __future__ import annotations

import os
import stat
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import lean_recipe_retention as retention

posix = pytest.mark.skipif(os.name != "posix", reason="POSIX modes")
DIGEST = "sha256:" + "a" * 64


@posix
def test_an_owned_directory_with_group_or_other_bits_is_made_owner_only_and_kept(
    tmp_path,
):
    directory = tmp_path / "artifacts"
    directory.mkdir()
    directory.chmod(0o755)
    assert retention._owner_directory(directory, "artifact_directory") == directory
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700


@posix
def test_an_owner_only_directory_is_untouched(tmp_path):
    directory = tmp_path / "entries"
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    before = directory.stat().st_mtime_ns
    assert retention._owner_directory(directory, "entry_directory") == directory
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert directory.stat().st_mtime_ns == before


@posix
def test_a_link_or_a_file_still_refuses(tmp_path):
    target = tmp_path / "real"
    target.mkdir(mode=0o755)
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(
        retention.RetentionUnavailable, match="task_artifacts_unavailable"
    ):
        retention._owner_directory(link, "task_artifacts")
    assert (
        stat.S_IMODE(target.stat().st_mode) == 0o755
    )  # never chmod'ed through the link
    plain = tmp_path / "file"
    plain.write_text("x")
    with pytest.raises(
        retention.RetentionUnavailable, match="task_artifacts_unavailable"
    ):
        retention._owner_directory(plain, "task_artifacts")


@posix
def test_another_owners_directory_still_refuses(tmp_path, monkeypatch):
    directory = tmp_path / "theirs"
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    monkeypatch.setattr(os, "getuid", lambda: os.stat(directory).st_uid + 1)
    with pytest.raises(
        retention.RetentionUnavailable, match="artifact_directory_not_owner_only"
    ):
        retention._owner_directory(directory, "artifact_directory")


class _Store:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def record_crown_paused(self, submission_id, key, **kw):
        if self.fail:
            raise OSError("disk")
        self.calls.append((submission_id, key, kw))


def test_a_decision_that_raised_before_it_was_made_is_filed_for_the_sweep():
    store = _Store()
    repeat = SimpleNamespace(entry_id=DIGEST)
    filed = retention._file_unmade_decision(
        store, "rtsk_x", DIGEST, lambda: DIGEST, repeat, DIGEST
    )
    assert filed is True
    ((sid, key, kw),) = store.calls
    assert (sid, key) == ("rtsk_x", DIGEST)
    assert kw == {"kind": "pack", "exam": DIGEST, "entry_id": DIGEST, "pin": DIGEST}
    assert "state" not in kw  # PAUSED (the sweep decides it), never PENDING_CONTENTION


def test_nothing_retained_files_nothing_and_a_failing_filing_changes_nothing():
    store = _Store()
    assert (
        retention._file_unmade_decision(
            store, "rtsk_x", DIGEST, DIGEST, SimpleNamespace(entry_id=None), DIGEST
        )
        is False
    )
    assert store.calls == []
    assert (
        retention._file_unmade_decision(
            _Store(fail=True),
            "rtsk_x",
            DIGEST,
            DIGEST,
            SimpleNamespace(entry_id=DIGEST),
            DIGEST,
        )
        is False
    )
