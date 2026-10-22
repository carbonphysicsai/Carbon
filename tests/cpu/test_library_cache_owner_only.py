"""Every level of a staged bundle's cache is owner-only under a normal umask
(Graphite Test executor, V2 catalog install, 2026-10-21): mkdir's `parents=True`
gave `<cache>/<bundle_digest>` the umask's 0755, which the cache then refused
("cache parent is not owner-only"), so receivers and miners needed UMask=0077."""

from __future__ import annotations

import os
import stat

import pytest
from test_library_bundles import fixture

from carbon.development_session.library_bundles import prepare_offline_context

POSIX = pytest.mark.skipif(os.name != "posix", reason="POSIX modes and owners")
PARENT = "sha256:" + "b" * 64


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture
def cache(tmp_path):
    root = tmp_path / "cache"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return root


@POSIX
def test_both_levels_are_owner_only_under_a_022_umask(cache):
    previous = os.umask(0o022)
    try:
        root, _, _ = prepare_offline_context(cache, *fixture(), PARENT)
    finally:
        os.umask(previous)
    assert _mode(root.parent) == 0o700
    assert _mode(root) == 0o700


@POSIX
def test_a_level_left_0755_by_an_earlier_install_is_repaired(cache):
    args = fixture()
    first, _, _ = prepare_offline_context(cache, *args, PARENT)
    first.parent.chmod(0o755)
    first.chmod(0o755)
    again, _, _ = prepare_offline_context(cache, *args, PARENT)
    assert again == first
    assert _mode(again.parent) == 0o700 and _mode(again) == 0o700


@POSIX
def test_a_linked_level_is_refused(cache, tmp_path):
    args = fixture()
    first, _, _ = prepare_offline_context(cache, *args, PARENT)
    elsewhere = tmp_path / "elsewhere"
    first.rename(elsewhere)
    first.symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        prepare_offline_context(cache, *args, PARENT)
