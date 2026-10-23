"""The miner's GPU overlay cache is bounded by their own disk (M1 S5).

On M1, staging the catalog's GPU twins filled the receiver's fixed 192 MiB
overlay cache bound, so every catalog GPU build was refused "operator
material and overlay cache capacity exceeded" and practice fell back to CPU
with 56 GB free. The miner's cache is on the miner's own disk: its bound is
everything it holds plus the free space less a reserve, and never less than
the receiver's. The receiver's own bound is unchanged.
"""

from __future__ import annotations

import shutil
from collections import namedtuple

import pytest

from carbon.development_session import gpu_practice

MiB, GiB = 1024**2, 1024**3
Usage = namedtuple("Usage", "total used free")


@pytest.fixture
def cache(tmp_path):
    root = tmp_path / "cache"
    (root / "materials").mkdir(parents=True, mode=0o700)
    # A staged GPU twin's material, larger than the receiver's whole bound
    # (sparse: its size counts, its blocks need not exist).
    with (root / "materials" / "twin.whl").open("wb") as twin:
        twin.truncate(200 * MiB)
    return root


def test_the_bound_is_the_miner_s_disk_less_a_reserve(cache, monkeypatch):
    monkeypatch.setattr(shutil, "disk_usage", lambda _p: Usage(0, 0, 56 * GiB))
    bound = gpu_practice.miner_overlay_cache_bytes(cache)
    assert bound == 200 * MiB + 56 * GiB - gpu_practice.MINER_CACHE_RESERVE_BYTES
    # Room for a whole overlay beside what is held, where 192 MiB had none.
    assert bound - 200 * MiB >= 128 * MiB
    assert gpu_practice.MINER_OVERLAY_CACHE_BYTES < 200 * MiB


def test_a_nearly_full_disk_keeps_its_reserve_and_never_drops_below_the_receiver(
    cache, monkeypatch
):
    monkeypatch.setattr(shutil, "disk_usage", lambda _p: Usage(0, 0, 1 * GiB))
    # Nothing beyond what is held: a new overlay is refused, the reserve kept.
    assert gpu_practice.miner_overlay_cache_bytes(cache) == 200 * MiB
    empty = cache.parent / "empty"
    empty.mkdir(mode=0o700)
    assert (
        gpu_practice.miner_overlay_cache_bytes(empty)
        == gpu_practice.MINER_OVERLAY_CACHE_BYTES
    )


def test_an_unreadable_disk_falls_back_to_the_receiver_s_bound(cache, monkeypatch):
    def unreadable(_path):
        raise OSError("no")

    monkeypatch.setattr(shutil, "disk_usage", unreadable)
    assert (
        gpu_practice.miner_overlay_cache_bytes(cache)
        == gpu_practice.MINER_OVERLAY_CACHE_BYTES
    )


def test_the_receiver_s_own_bound_is_unchanged():
    from carbon.challenge_validator import receiver_setup

    assert receiver_setup.MATERIAL_CACHE_BYTES == 192 * MiB
