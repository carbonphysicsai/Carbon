"""A DECLARED door migration (`state_binding`, M1-M5; owner, Mon 16 Nov 2026 in Deploy-B: "Get it working. Turn it
on." for the 116 graph GPU builds; Lead: one migration for the GPU build lane and the remote grade lane).

Claims: without the operator's request every door change still refuses, writing nothing; with it, exactly the worker
image keys and the graph GPU lane keys may change or be added (never dropped, never any other key), from exactly the
door the state holds to exactly the door the release brings; the original door file is never rewritten; each migration
is one write-once link, re-checked on every read; a replayed, stale or mismatched request refuses; an older release
(which reads only the original door) still starts with the original images; the pack digest never moves.
"""

from __future__ import annotations

import json
import os

import pytest

from carbon.challenge_validator import state_binding
from carbon.challenge_validator.state_binding import (
    DOOR_NAME,
    MIGRATION_REQUEST,
    MIGRATION_SCHEMA,
    MIGRATIONS_DIR,
    StateBindingRefused,
    bind,
    door_digest,
    door_of,
    read_door,
    retained_pack_digest,
)
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical

PACK = "sha256:" + "a" * 64
OLD_IMAGE = {"image_id": "sha256:" + "b" * 64}
NEW_IMAGE = {"image_id": "sha256:" + "c" * 64}
GPU = {
    "graph_gpu_image": {"image_id": "sha256:" + "d" * 64},
    "graph_gpu_ops_digest": "sha256:" + "e" * 64,
    "graph_gpu_device": {"kind": "nvidia-4090", "record": "sha256:" + "f" * 64},
}


def _binding(revision="1" * 40, **changes):
    binding = {
        "schema": "carbon.construction.direct-receiver.v1",
        "implementation": {"revision": revision},
        "parent": OLD_IMAGE,
        "construction_parents": [OLD_IMAGE],
        "context": {"network": "finney", "netuid": 116},
        "receiver_hotkey": "5Receiver",
        "challenge": {"id": "electric-motor-magnetics", "version": "1.8"},
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


def _request(root, old, new, index=1, **override):
    document = {
        "schema": MIGRATION_SCHEMA,
        "index": index,
        "from": door_digest(door_of(old)),
        "to": door_digest(door_of(new)),
        **override,
    }
    path = root / MIGRATION_REQUEST
    path.write_bytes(canonical(document))
    os.chmod(path, 0o600)
    return path


def _files(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _new(revision="2" * 40, **changes):
    """The migrated release: new worker images and the graph GPU lane added (``changes`` override)."""
    return _binding(
        revision=revision,
        **{
            "parent": NEW_IMAGE,
            "construction_parents": [NEW_IMAGE],
            **GPU,
            **changes,
        },
    )


def test_without_a_request_a_door_change_still_refuses_and_writes_nothing(root, capsys):
    old = _binding()
    bind(root, old)
    before = _files(root)
    with pytest.raises(StateBindingRefused, match="retained door binding differs"):
        bind(root, _new())
    assert _files(root) == before
    # the refusal names both digests and the differing keys (no value), for the operator's request
    event = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert event == {
        "event": "door_binding_differs",
        "from": door_digest(door_of(old)),
        "to": door_digest(door_of(_new())),
        "keys": [
            "construction_parents",
            "graph_gpu_device",
            "graph_gpu_image",
            "graph_gpu_ops_digest",
            "parent",
        ],
        "migratable": True,
    }


def test_the_declared_migration_moves_the_images_and_adds_the_gpu_lane(root):
    old, new = _binding(), _new()
    bind(root, old)
    original = (root / DOOR_NAME).read_bytes()
    _request(root, old, new)
    result = bind(root, new)
    assert result["migrated"] == 1
    assert (root / DOOR_NAME).read_bytes() == original  # never rewritten
    link = json.loads((root / MIGRATIONS_DIR / "0001.json").read_bytes())
    assert link["from"] == door_digest(door_of(old))
    assert link["to"] == door_digest(door_of(new)) and link["door"] == door_of(new)
    assert read_door(root) == door_of(new)
    assert retained_pack_digest(root) == PACK
    # a restart of the migrated release changes nothing; the stale request is not used again
    before = _files(root)
    assert bind(root, new)["migrated"] is None
    assert _files(root) == before


def test_the_gpu_lane_alone_may_be_added(root):
    old = _binding()
    new = _binding(revision="2" * 40, **GPU)
    bind(root, old)
    _request(root, old, new)
    assert bind(root, new)["migrated"] == 1
    assert read_door(root) == door_of(new)


@pytest.mark.parametrize(
    "change",
    [
        {"context": {"network": "test", "netuid": 567}},
        {"receiver_hotkey": "5Other"},
        {"challenge": {"id": "electric-motor-magnetics", "version": "1.9"}},
        {"measure_query": False},
        {"evaluation_pack_digest": "sha256:" + "9" * 64},
        {"material_cache_bytes": 1},
        {"gpu_construction_device": {"kind": "x", "record": "sha256:" + "1" * 64}},
    ],
)
def test_any_other_door_key_refuses_even_with_a_request(root, change):
    old = _binding()
    new = _new(**change)
    bind(root, old)
    _request(root, old, new)
    before = _files(root)
    with pytest.raises(StateBindingRefused, match="retained door binding differs"):
        bind(root, new)
    assert _files(root) == before


def test_a_migratable_key_may_not_be_dropped(root):
    old = _binding(**GPU)
    new = _binding(revision="2" * 40)  # the GPU lane keys dropped
    bind(root, old)
    _request(root, old, new)
    with pytest.raises(StateBindingRefused):
        bind(root, new)


@pytest.mark.parametrize(
    "override",
    [
        {"from": "sha256:" + "0" * 64},
        {"to": "sha256:" + "0" * 64},
        {"schema": "carbon.other"},
        {"extra": 1},
        {"index": 2},
    ],
)
def test_a_request_for_another_change_refuses(root, override):
    old, new = _binding(), _new()
    bind(root, old)
    _request(root, old, new, **override)
    before = _files(root)
    with pytest.raises(StateBindingRefused):
        bind(root, new)
    assert _files(root) == before


def test_a_replayed_request_cannot_move_the_door_again(root):
    old, new = _binding(), _new()
    bind(root, old)
    _request(root, old, new)
    bind(root, new)
    # a third door, with the old request still installed: its `from` is no longer the current door
    third = _new(revision="3" * 40, parent={"image_id": "sha256:" + "7" * 64})
    with pytest.raises(StateBindingRefused):
        bind(root, third)
    assert read_door(root) == door_of(new)


def test_two_declared_migrations_chain(root):
    old, new = _binding(), _new()
    bind(root, old)
    _request(root, old, new)
    bind(root, new)
    third = _new(revision="3" * 40, parent={"image_id": "sha256:" + "7" * 64})
    _request(root, new, third, index=2)
    assert bind(root, third)["migrated"] == 2
    assert read_door(root) == door_of(third)
    assert sorted(os.listdir(root / MIGRATIONS_DIR)) == ["0001.json", "0002.json"]


def test_an_older_release_with_the_original_images_still_starts(root):
    """M4: the pre-migration release reads only the original door: it starts on the migrated state with its own
    images, and a release with the migrated images then starts again (the chain stands).
    """
    old, new = _binding(), _new()
    bind(root, old)
    _request(root, old, new)
    bind(root, new)
    # what an older release does: compare its door with door-binding.json only
    assert json.loads((root / DOOR_NAME).read_bytes()) == door_of(old)
    original = (root / DOOR_NAME).read_bytes()
    write_once(
        root / DOOR_NAME, canonical(door_of(old))
    )  # the older release's own write: a no-op
    assert (root / DOOR_NAME).read_bytes() == original
    assert bind(root, new)["migrated"] is None


@pytest.mark.parametrize(
    "tamper",
    [
        lambda link: {**link, "from": "sha256:" + "0" * 64},
        lambda link: {**link, "index": 2},
        lambda link: {**link, "door": {**link["door"], "receiver_hotkey": "5Other"}},
        lambda link: {**link, "to": "sha256:" + "0" * 64},
    ],
)
def test_a_tampered_link_refuses_every_read(root, tamper):
    old, new = _binding(), _new()
    bind(root, old)
    _request(root, old, new)
    bind(root, new)
    path = root / MIGRATIONS_DIR / "0001.json"
    link = json.loads(path.read_bytes())
    os.chmod(path, 0o600)
    path.write_bytes(canonical(tamper(link)))
    with pytest.raises(StateBindingRefused):
        read_door(root)
    with pytest.raises(StateBindingRefused):
        bind(root, new)


def test_a_gap_or_stray_link_name_refuses(root):
    old, new = _binding(), _new()
    bind(root, old)
    _request(root, old, new)
    bind(root, new)
    (root / MIGRATIONS_DIR / "0001.json").rename(root / MIGRATIONS_DIR / "0002.json")
    with pytest.raises(StateBindingRefused, match="door migrations unreadable"):
        read_door(root)


def test_the_migratable_keys_are_exactly_the_images_and_the_gpu_lane():
    assert state_binding.MIGRATABLE_KEYS == {
        "parent",
        "inference_image",
        "construction_parents",
        "graph_gpu_image",
        "graph_gpu_ops_digest",
        "graph_gpu_device",
    }
    assert "evaluation_pack_digest" not in state_binding.MIGRATABLE_KEYS


def test_migrated_images_says_whether_a_link_moved_a_worker_image(root):
    old = _binding()
    bind(root, old)
    assert state_binding.migrated_images(root) is False
    gpu_only = _binding(revision="2" * 40, **GPU)
    _request(root, old, gpu_only)
    bind(root, gpu_only)
    assert (
        state_binding.migrated_images(root) is False
    )  # the GPU lane alone moves no owner manifest image
    moved = _binding(
        revision="3" * 40, parent=NEW_IMAGE, construction_parents=[NEW_IMAGE], **GPU
    )
    _request(root, gpu_only, moved, index=2)
    bind(root, moved)
    assert state_binding.migrated_images(root) is True


def test_a_type_change_of_another_key_is_not_hidden_by_an_image_move(root):
    """Keys compare by their canonical bytes: ``true`` and ``1`` differ."""
    old = _binding()
    new = _new(measure_query=1)
    bind(root, old)
    _request(root, old, new)
    with pytest.raises(StateBindingRefused):
        bind(root, new)


def test_a_migration_on_a_revision_this_state_already_ran_refuses(root):
    old = _binding()
    same_revision = _new(revision="1" * 40)
    bind(root, old)
    _request(root, old, same_revision)
    before = _files(root)
    with pytest.raises(StateBindingRefused, match="needs a new code revision"):
        bind(root, same_revision)
    assert _files(root) == before


def test_a_used_request_never_applies_twice(root):
    """A -> B, B -> A, then the A -> B request's bytes again (index 3): refused, its digest is in link 1."""
    a, b = _binding(), _new()
    bind(root, a)
    first = _request(root, a, b).read_bytes()
    bind(root, b)
    back = _binding(
        revision="3" * 40, **GPU
    )  # the original images back, the GPU lane kept
    _request(root, b, back, index=2)
    bind(root, back)
    again = _new(revision="4" * 40)
    # the same request bytes as link 1 (its from/to name the doors, not the revision) re-installed
    path = root / MIGRATION_REQUEST
    path.write_bytes(first)
    os.chmod(path, 0o600)
    with pytest.raises(StateBindingRefused):
        bind(root, again)


def test_a_write_temp_left_by_a_crash_is_not_a_link(root):
    old, new = _binding(), _new()
    bind(root, old)
    _request(root, old, new)
    bind(root, new)
    (root / MIGRATIONS_DIR / ".0002.json.abcd").write_bytes(b"partial")
    assert read_door(root) == door_of(new)


def test_a_door_migrations_file_refuses_typed(root):
    bind(root, _binding())
    (root / MIGRATIONS_DIR).write_bytes(b"x")
    with pytest.raises(StateBindingRefused, match="door migrations unreadable"):
        read_door(root)


def test_a_link_too_large_to_read_back_is_refused_before_it_is_written(root):
    old = _binding()
    new = _new(construction_parents=[{"image_id": "sha256:" + "c" * 64}] * 2000)
    bind(root, old)
    _request(root, old, new)
    before = _files(root)
    with pytest.raises(StateBindingRefused, match="too large"):
        bind(root, new)
    assert _files(root) == before


def test_migrated_images_is_false_again_after_a_reverse_migration(root):
    a, b = _binding(), _new()
    bind(root, a)
    _request(root, a, b)
    bind(root, b)
    assert state_binding.migrated_images(root) is True
    back = _binding(revision="3" * 40, **GPU)  # the original images, the GPU lane kept
    _request(root, b, back, index=2)
    bind(root, back)
    assert state_binding.migrated_images(root) is False
