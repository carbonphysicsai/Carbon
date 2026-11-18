"""Live 116, 18 Nov 2026: the first advance round after every restart read every finished task the door ever took
(`get_research_result` verifies a SUCCEEDED task's evidence from disk), ~25 min before the first build. A task whose
view, held by its owner's already-open provider, is not QUEUED is skipped before the owner check and the read."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.research import DirectTaskStateV3

DONE, WAITING, UNKNOWN = ("rtsk_" + c * 64 for c in "abc")
OWNER = "5" + "1" * 47


def _adapter(views, *, opened=True):
    adapter = LeanRecipeAdapter.__new__(LeanRecipeAdapter)
    adapter.contract_digest = "sha256:" + "c" * 64
    adapter.ledger = SimpleNamespace(
        submitted_outcomes=lambda contract: [DONE, WAITING, UNKNOWN],
        owned_outcome=lambda contract, task: OWNER,
    )
    provider = SimpleNamespace(
        _views={task: SimpleNamespace(state=state) for task, state in views.items()}
    )
    adapter.provider_for = SimpleNamespace(
        _providers={OWNER: provider} if opened else None
    )
    seen = []

    def active_owner(task):
        seen.append(task)
        return None  # stop here: the test reads which tasks reached the owner check

    adapter._active_owner = active_owner
    return adapter, seen


def test_a_finished_task_is_skipped_before_the_owner_check_and_the_read():
    adapter, seen = _adapter(
        {DONE: DirectTaskStateV3.SUCCEEDED, WAITING: DirectTaskStateV3.QUEUED}
    )
    assert adapter.advance() == 0
    # the SUCCEEDED one never reaches the owner check; the QUEUED one and the one with no view do, as before
    assert seen == [WAITING, UNKNOWN]


def test_without_open_providers_every_task_is_read_as_before():
    adapter, seen = _adapter({DONE: DirectTaskStateV3.SUCCEEDED}, opened=False)
    assert adapter.advance() == 0
    assert seen == [DONE, WAITING, UNKNOWN]


def test_the_skip_reads_no_ledger():
    """The skip's index comes from the open providers' views alone: no per-task ledger read queues on the write lock
    beside the grades (live 116 stacks, 18 Nov 2026: 17 threads on `AttemptLedger._db`).
    """
    adapter, seen = _adapter(
        {DONE: DirectTaskStateV3.SUCCEEDED, WAITING: DirectTaskStateV3.QUEUED}
    )

    def no_read(*args):
        raise AssertionError("the skip read the ledger")

    adapter.ledger.owned_outcome = no_read
    assert adapter.advance() == 0
    assert seen == [WAITING, UNKNOWN]


def test_a_source_file_is_hashed_again_only_when_its_stat_moves(
    tmp_path, monkeypatch
):
    """Live 116 (18 Nov 2026): `_source_identity` hashed every served source file on every owner check, ~84 GB read
    at one start. A file is re-read only when its stat (inode, size, mtime, ctime) moves: a changed source is still
    seen (`served_recipe_source_changed`), an unchanged one costs one stat."""
    import os

    from carbon.challenge_validator import lean_recipe

    monkeypatch.setattr(lean_recipe, "_SOURCE_HASHES", {})
    path = tmp_path / "module.py"
    path.write_bytes(b"one")
    reads = []
    real = type(path).read_bytes

    def counted(self):
        reads.append(str(self))
        return real(self)

    monkeypatch.setattr(type(path), "read_bytes", counted)
    first = lean_recipe._file_sha256(path)
    assert lean_recipe._file_sha256(path) == first
    assert reads == [str(path)]  # the second call read nothing
    path.write_bytes(b"two!")
    stat = os.stat(path)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))
    assert lean_recipe._file_sha256(path) != first
    assert len(reads) == 2
    link = tmp_path / "link.py"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="served recipe source unavailable"):
        lean_recipe._file_sha256(link)
