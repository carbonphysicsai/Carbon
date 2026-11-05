"""A receiver state is bound to its DOOR, not to one code release (MAINNET_UPDATE_ARCHITECTURE s1.3 (a)).

The "alternating start" property: release N (the receiver as it was, which writes ``receiver-binding.json`` once with
`data.write_once`) and release N+1 (`state_binding.bind`) both start on one state directory, in either order and
repeatedly, while any change of the door (network, hotkey, Challenge, measure query, pack) still refuses.
"""

from __future__ import annotations

import os

import pytest

from carbon.challenge_validator import state_binding
from carbon.challenge_validator.state_binding import (
    DOOR_NAME,
    LEGACY_NAME,
    RELEASES_DIR,
    StateBindingRefused,
    bind,
    retained_pack_digest,
)
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical

PACK = "sha256:" + "a" * 64


def _binding(revision="1" * 40, **changes):
    binding = {
        "schema": "carbon.construction.direct-receiver.v1",
        "implementation": {"revision": revision},
        "parent": {"image_id": "sha256:" + "b" * 64},
        "context": {"network": "test", "netuid": 567},
        "receiver_hotkey": "5Receiver",
        "challenge": {"id": "f02", "version": "2.5"},
        "measure_query": True,
        "evaluation_pack_digest": PACK,
    }
    binding.update(changes)
    return binding


@pytest.fixture
def root(tmp_path):
    path = tmp_path / "state"
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    return path


def _old_release_start(root, binding):
    """What release N did at its start (direct_receiver before this change)."""
    write_once(root / LEGACY_NAME, canonical(binding))


def _files(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_a_fresh_state_gets_the_door_the_release_and_the_legacy_file(root):
    n1 = _binding()
    done = bind(root, n1)
    assert done["legacy_written"] is True
    assert (root / LEGACY_NAME).read_bytes() == canonical(n1)
    assert (root / done["release_binding"]).read_bytes() == canonical(n1)
    door = state_binding.door_of(n1)
    assert (root / DOOR_NAME).read_bytes() == canonical(door)
    assert "implementation" not in door
    assert door["parent"] == n1["parent"] and door["receiver_schema"] == n1["schema"]
    assert set(door) == (set(n1) - {"implementation"}) | {"receiver_schema"}


def test_a_restart_of_the_same_release_changes_nothing(root):
    bind(root, _binding())
    before = _files(root)
    again = bind(root, _binding())
    assert _files(root) == before
    assert again["legacy_written"] is False and again["legacy_is_this_release"] is True


def test_old_then_new_then_old_again_all_start_on_one_state(root):
    """Forward and rollback on one state: the old receiver's own file is never rewritten."""
    old, new = _binding("1" * 40), _binding("2" * 40)
    _old_release_start(root, old)
    legacy = (root / LEGACY_NAME).read_bytes()
    done = bind(root, new)
    assert done["legacy_written"] is False and done["legacy_is_this_release"] is False
    assert (root / LEGACY_NAME).read_bytes() == legacy
    _old_release_start(root, old)  # rollback: release N starts again
    bind(root, new)  # and forward again
    assert (root / LEGACY_NAME).read_bytes() == legacy
    assert sorted(p.name for p in (root / RELEASES_DIR).iterdir()) == sorted(
        [state_binding.release_name(new)]
    )


def test_releases_n1_n2_and_back_to_n1_each_add_their_binding(root):
    n1, n2 = _binding("1" * 40), _binding("2" * 40)
    bind(root, n1)
    bind(root, n2)
    bind(root, n1)
    names = sorted(p.name for p in (root / RELEASES_DIR).iterdir())
    assert names == sorted(state_binding.release_name(b) for b in (n1, n2))
    assert (root / LEGACY_NAME).read_bytes() == canonical(n1)  # the FIRST release


@pytest.mark.parametrize(
    "change",
    [
        {"context": {"network": "finney", "netuid": 567}},
        {"receiver_hotkey": "5Other"},
        {"challenge": {"id": "f02", "version": "3.0"}},
        {"measure_query": False},
        {"evaluation_pack_digest": "sha256:" + "c" * 64},
        {"parent": {"image_id": "sha256:" + "e" * 64}},
        {"graph_gpu_image": {"image_id": "sha256:" + "f" * 64}},
        {"gpu_construction_device": {"kind": "cuda", "record": "x"}},
        {"material_cache_bytes": 1},
    ],
    ids=[
        "network",
        "hotkey",
        "challenge",
        "measure_query",
        "pack",
        "cpu_image",
        "graph_gpu_image",
        "gpu_device",
        "cache_size",
    ],
)
def test_another_door_is_refused_and_nothing_is_written(root, change):
    bind(root, _binding())
    before = _files(root)
    with pytest.raises(StateBindingRefused, match="retained door binding differs"):
        bind(root, _binding("2" * 40, **change))
    assert _files(root) == before


@pytest.mark.parametrize("key", ["evaluation_pack_digest", "challenge"])
def test_another_door_is_refused_on_an_older_state_by_its_legacy_file(root, key):
    _old_release_start(root, _binding())
    before = _files(root)
    other = {
        "evaluation_pack_digest": "sha256:" + "c" * 64,
        "challenge": {"id": "f08", "version": "1.7"},
    }[key]
    with pytest.raises(StateBindingRefused, match="retained door binding differs"):
        bind(root, _binding("2" * 40, **{key: other}))
    assert _files(root) == before


def test_a_door_without_a_pack_stays_one_without_a_pack(root):
    no_pack = _binding()
    del no_pack["evaluation_pack_digest"]
    bind(root, no_pack)
    with pytest.raises(StateBindingRefused):
        bind(root, _binding("2" * 40))
    assert retained_pack_digest(root) is None


def test_the_retained_pack_digest_comes_from_either_record(root, tmp_path):
    assert retained_pack_digest(root) is None
    _old_release_start(root, _binding())
    assert retained_pack_digest(root) == PACK  # an older state: the legacy file only
    bind(root, _binding("2" * 40))
    assert retained_pack_digest(root) == PACK


def test_disagreeing_records_are_refused(root):
    bind(root, _binding())
    (root / LEGACY_NAME).unlink()
    _old_release_start(root, _binding(evaluation_pack_digest="sha256:" + "d" * 64))
    with pytest.raises(StateBindingRefused, match="pack digest differs"):
        retained_pack_digest(root)


def test_binding_links_are_refused(root, tmp_path):
    target = tmp_path / "elsewhere.json"
    target.write_bytes(canonical(_binding()))
    os.symlink(target, root / LEGACY_NAME)
    with pytest.raises(StateBindingRefused, match="link refused"):
        bind(root, _binding())
    with pytest.raises(StateBindingRefused, match="link refused"):
        retained_pack_digest(root)


def test_only_the_code_revision_may_move_on_one_state(root):
    """The Validator's M3 rule at the state level: implementation is the one field a release may change."""
    assert state_binding.RELEASE_KEYS == ("implementation",)
    bind(root, _binding("1" * 40))
    bind(root, _binding("2" * 40, implementation={"revision": "2" * 40, "tree": "t"}))


#: The only places that may name the legacy file as a path (Validator 17:32 condition 1): the binding module itself,
#: and the snapshot tool's write-once class list (it never reads the content). Every other reader goes through
#: `state_binding.read_door` / `retained_pack_digest`, which return door fields only.
LEGACY_PATH_USERS = {
    "carbon/challenge_validator/state_binding.py": "the one reader and writer",
    "scripts/dev/release/state_snapshot.py": "hard-link class list; content never read",
}


def test_no_code_reads_the_legacy_binding_file_directly():
    import ast
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    found = set()
    for top in ("carbon", "scripts"):
        for path in (repo / top).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if LEGACY_NAME not in text:
                continue
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, ast.Constant) and node.value == LEGACY_NAME:
                    found.add(path.relative_to(repo).as_posix())
    assert found == set(LEGACY_PATH_USERS)


def test_read_door_gives_door_fields_only_whichever_release_wrote_the_file(root):
    _old_release_start(root, _binding("1" * 40))
    door = state_binding.read_door(root)
    assert "implementation" not in door and door["challenge"] == _binding()["challenge"]
    bind(root, _binding("2" * 40))
    assert state_binding.read_door(root) == door
    with pytest.raises(StateBindingRefused, match="missing"):
        state_binding.read_door(root.parent / "empty")


def _carry(old, new):
    """What today's copy-based switch does (REV5 state_carry): everything but the top-level legacy file."""
    import shutil

    shutil.copytree(
        old, new, ignore=lambda d, names: [LEGACY_NAME] if d == str(old) else []
    )
    os.chmod(new, 0o700)


def test_a_carried_state_starts_when_its_door_matches_and_refuses_when_it_differs(
    root, tmp_path
):
    """Validator 17:32 condition 2: the copy-based switch carries door-binding.json and bindings/."""
    bind(root, _binding("1" * 40))
    same = tmp_path / "carried-same"
    _carry(root, same)
    assert not (same / LEGACY_NAME).exists() and (same / DOOR_NAME).exists()
    done = bind(same, _binding("2" * 40))
    assert (
        done["legacy_written"] is True
    )  # the new root's legacy file names the new release
    assert (
        len(list((same / RELEASES_DIR).iterdir())) == 2
    )  # history carried + this release
    other = tmp_path / "carried-other"
    _carry(root, other)
    with pytest.raises(StateBindingRefused, match="retained door binding differs"):
        bind(other, _binding("2" * 40, challenge={"id": "f02", "version": "3.0"}))
    assert not (other / LEGACY_NAME).exists()


def test_a_carried_pre_h1_state_has_no_door_record_to_check(root, tmp_path):
    """Stated limit: a state written only by a receiver from before this change carries no door record (its legacy
    file is excluded by the switch), so the first release after the carry binds it fresh, as every switch did before.
    """
    _old_release_start(root, _binding("1" * 40))
    carried = tmp_path / "carried"
    _carry(root, carried)
    assert sorted(p.name for p in carried.iterdir()) == []
    bind(carried, _binding("2" * 40))
    assert state_binding.read_door(carried) == state_binding.door_of(_binding("2" * 40))
