"""A declared door migration (mg21 rehearsal, 16 Nov) must leave a door that STARTS and RESTARTS:

1. each owner's provider binding (`research_tasks.DirectDevelopmentTasksV3`, its ``direct_binding`` row) freezes the
   worker images and the graph GPU lane; on a migrated door it re-freezes to the door's current ones (requester,
   owner and pack never move; the old row is kept as history) instead of refusing every owner;
2. a migrated start on a carried state (no legacy ``receiver-binding.json``) writes no legacy file naming the NEW
   door, and a legacy file a start already wrote that way still reads as the folded door, so a later restart binds.
"""

from __future__ import annotations

import json
import os
import sqlite3

import pytest
from test_direct_v3_durable_tasks import _fixture

from carbon.challenge_validator.state_binding import (
    DOOR_NAME,
    LEGACY_NAME,
    MIGRATION_REQUEST,
    MIGRATION_SCHEMA,
    StateBindingRefused,
    bind,
    door_digest,
    door_of,
    migrated_keys,
    read_door,
)
from carbon.development_session.profile import canonical
from carbon.development_session.research_tasks import (
    DirectDevelopmentTasksV3,
    _same_principal,
)
from carbon.reconstruction.worker.model import WorkerImageIdentity

PACK = "sha256:" + "a" * 64
OLD = {"image_id": "sha256:" + "b" * 64}
NEW = {"image_id": "sha256:" + "c" * 64}
GPU = {
    "graph_gpu_image": {"image_id": "sha256:" + "d" * 64},
    "graph_gpu_ops_digest": "sha256:" + "e" * 64,
    "graph_gpu_device": {
        "kind": "NVIDIA A100-SXM4-40GB",
        "record": "sha256:" + "f" * 64,
    },
}


def _binding(revision, **changes):
    binding = {
        "schema": "carbon.construction.direct-receiver.v1",
        "implementation": {"revision": revision},
        "parent": OLD,
        "construction_parents": [OLD],
        "context": {"network": "finney", "netuid": 116},
        "receiver_hotkey": "5Receiver",
        "challenge": {"id": "electric-motor-magnetics", "version": "1.8"},
        "measure_query": True,
        "evaluation_pack_digest": PACK,
    }
    binding.update(changes)
    return binding


def _migrated(revision):
    return _binding(revision, parent=NEW, construction_parents=[NEW], **GPU)


def _migrate(root, old, new):
    request = {
        "schema": MIGRATION_SCHEMA,
        "index": 1,
        "from": door_digest(door_of(old)),
        "to": door_digest(door_of(new)),
    }
    path = root / MIGRATION_REQUEST
    path.write_bytes(canonical(request))
    os.chmod(path, 0o600)


@pytest.fixture
def carried(tmp_path):
    """A state carried by a switch: its door binding, no legacy file (state_carry leaves it out)."""
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    old = _binding("1" * 40)
    bind(root, old)
    (root / LEGACY_NAME).unlink()
    return root, old


def test_a_migrated_start_on_a_carried_state_restarts(carried):
    root, old = carried
    new = _migrated("2" * 40)
    _migrate(root, old, new)
    assert bind(root, new)["migrated"] == 1
    assert not (root / LEGACY_NAME).exists()  # never a legacy file naming the NEW door
    # the next start (crash, reboot, rehearsal) binds, as does a later release of the migrated door
    assert bind(root, new)["migrated"] is None
    assert bind(root, _migrated("3" * 40))["migrated"] is None
    assert read_door(root) == door_of(new)
    assert migrated_keys(root) == {
        "parent",
        "construction_parents",
        "graph_gpu_image",
        "graph_gpu_ops_digest",
        "graph_gpu_device",
    }


def test_a_legacy_file_already_written_for_the_migrated_door_still_restarts(carried):
    root, old = carried
    new = _migrated("2" * 40)
    _migrate(root, old, new)
    bind(root, new)
    # what the old code wrote at the mg21 copy's start 2: the legacy file = the NEW release
    (root / LEGACY_NAME).write_bytes(canonical(new))
    os.chmod(
        root / LEGACY_NAME, 0o600
    )  # an operator record is private (private_json), as bind writes it
    assert bind(root, new)["migrated"] is None
    assert read_door(root) == door_of(new)


def test_a_legacy_file_of_any_other_door_still_refuses(carried):
    root, old = carried
    other = _binding("9" * 40, receiver_hotkey="5Other")
    (root / LEGACY_NAME).write_bytes(canonical(other))
    os.chmod(
        root / LEGACY_NAME, 0o600
    )  # an operator record is private (private_json), as bind writes it
    with pytest.raises(StateBindingRefused, match="retained door binding differs"):
        bind(root, old)
    with pytest.raises(StateBindingRefused, match="retained door binding differs"):
        read_door(root)


def test_a_fresh_state_still_writes_its_legacy_file(tmp_path):
    root = tmp_path / "fresh"
    root.mkdir(mode=0o700)
    assert bind(root, _binding("1" * 40))["legacy_written"] is True
    assert (root / LEGACY_NAME).exists() and (root / DOOR_NAME).exists()
    assert migrated_keys(root) == frozenset()


def test_same_principal_lets_only_images_and_the_gpu_lane_move():
    one, two = "sha256:" + "1" * 64, "sha256:" + "2" * 64
    pack, other_pack = "sha256:" + "a" * 64, "sha256:" + "b" * 64
    lane = ["GRAPH_GPU_LANE", "sha256:" + "d" * 64, "sha256:" + "e" * 64]
    old = ["miner", "miner", "PER_RECIPE_LIBRARY_IMAGE", one, "EVALUATION_PACK", pack]

    def ok(new, base=old):
        return _same_principal(json.dumps(base), json.dumps(new))

    assert ok(
        ["miner", "miner", "PER_RECIPE_LIBRARY_IMAGE", two, "EVALUATION_PACK", pack]
    )
    assert ok(
        [
            "miner",
            "miner",
            "PER_RECIPE_LIBRARY_IMAGE",
            two,
            "EVALUATION_PACK",
            pack,
            *lane,
        ]
    )
    # never: another requester or owner, another pack, another form or marker, a malformed lane tail
    assert not ok(
        ["other", "miner", "PER_RECIPE_LIBRARY_IMAGE", one, "EVALUATION_PACK", pack]
    )
    assert not ok(
        ["miner", "other", "PER_RECIPE_LIBRARY_IMAGE", one, "EVALUATION_PACK", pack]
    )
    assert not ok(
        [
            "miner",
            "miner",
            "PER_RECIPE_LIBRARY_IMAGE",
            one,
            "EVALUATION_PACK",
            other_pack,
        ]
    )
    assert not ok(
        ["miner", "miner", one, one, one, {"bundle": "x"}, "EVALUATION_PACK", pack]
    )
    assert not ok(
        [
            "miner",
            "miner",
            "PER_RECIPE_LIBRARY_IMAGE",
            one,
            "CONSTRUCTION_PARENT",
            "torch",
            two,
            "EVALUATION_PACK",
            pack,
        ]
    )
    assert not ok([*old, "GRAPH_GPU_LANE", "sha256:" + "d" * 64])
    # a fixed image's bundle reference never moves
    fixed = ["miner", "miner", one, one, one, {"bundle": "x"}]
    assert not ok(["miner", "miner", two, two, two, {"bundle": "y"}], fixed)
    assert ok(["miner", "miner", one, two, two, {"bundle": "x"}], fixed)
    assert not ok(["miner", "miner", two, one, one, {"bundle": "x"}], fixed)
    assert not _same_principal("not json", json.dumps(old))


def _reopen(tmp_path, fixed, inference_image, *, requester="miner", **extra):
    return DirectDevelopmentTasksV3(
        root=tmp_path / "tasks",
        requester=requester,
        ledger=fixed.ledger,
        owner="miner",
        discovery=fixed.discovery,
        image=fixed.image,
        inference_image=inference_image,
        **extra,
    )


def _store(tmp_path):
    found = [p for p in (tmp_path / "tasks").iterdir() if p.suffix == ".sqlite3"]
    assert len(found) == 1
    return found[0]


def test_an_owner_re_freezes_to_the_migrated_images_only_on_a_migrated_door(
    tmp_path, monkeypatch
):
    _request, provider, _discovery = _fixture(tmp_path, monkeypatch)
    fixed = provider()
    fixed.close()
    moved = WorkerImageIdentity(*("sha256:" + "9" * 64 for _ in range(8)))
    # a door never migrated: a changed image binding still refuses, as before
    with pytest.raises(ValueError, match="direct requester or image binding changed"):
        _reopen(tmp_path, fixed, moved)
    with sqlite3.connect(_store(tmp_path)) as db:
        entropy = db.execute("SELECT entropy FROM direct_binding WHERE id=1").fetchone()
    # a migrated door: the owner re-freezes, keeping the old row as history and its entropy
    _reopen(tmp_path, fixed, moved, binding_migrated=True).close()
    with sqlite3.connect(_store(tmp_path)) as db:
        assert (
            db.execute("SELECT entropy FROM direct_binding WHERE id=1").fetchone()
            == entropy
        )
        assert db.execute("SELECT count(*) FROM direct_binding_history").fetchone() == (
            1,
        )
    # the next start of the migrated door opens unchanged (no new history row)
    _reopen(tmp_path, fixed, moved, binding_migrated=True).close()
    with sqlite3.connect(_store(tmp_path)) as db:
        assert db.execute("SELECT count(*) FROM direct_binding_history").fetchone() == (
            1,
        )
    # another requester never re-freezes, migration or not
    with pytest.raises(ValueError, match="direct requester or image binding changed"):
        _reopen(tmp_path, fixed, moved, binding_migrated=True, requester="other")


# -- tasks admitted under the EARLIER door (A100 flip, 17 Nov: 'admitted_image_changed') -------------------------------


def test_the_earlier_doors_graph_images_are_named_from_the_checked_chain(carried):
    from carbon.challenge_validator.state_binding import migrated_graph_image_bindings

    root, old = carried
    assert migrated_graph_image_bindings(root) == frozenset()
    new = _migrated("2" * 40)
    _migrate(root, old, new)
    bind(root, new)
    old_binding = json.dumps(
        ["GRAPH_PARENT", OLD], sort_keys=True, separators=(",", ":")
    )
    new_binding = json.dumps(
        ["GRAPH_PARENT", NEW], sort_keys=True, separators=(",", ":")
    )
    assert migrated_graph_image_bindings(root) == {old_binding}
    assert new_binding not in migrated_graph_image_bindings(root)


def test_only_an_earlier_doors_exact_graph_image_moves_to_the_current_one():
    from types import SimpleNamespace

    from carbon.development_session.research_tasks import DirectDevelopmentTasksV3

    old_binding = json.dumps(
        ["GRAPH_PARENT", OLD], sort_keys=True, separators=(",", ":")
    )
    new_binding = json.dumps(
        ["GRAPH_PARENT", NEW], sort_keys=True, separators=(",", ":")
    )
    other = json.dumps(
        ["GRAPH_PARENT", {"image_id": "sha256:" + "9" * 64}],
        sort_keys=True,
        separators=(",", ":"),
    )
    migrated = SimpleNamespace(migrated_image_bindings=frozenset({old_binding}))
    never = SimpleNamespace(migrated_image_bindings=frozenset())
    moves = DirectDevelopmentTasksV3._migrated_graph_binding
    assert moves(migrated, old_binding, new_binding)
    assert not moves(
        never, old_binding, new_binding
    )  # a door never migrated: refused as before
    assert not moves(migrated, other, new_binding)  # an image of no earlier door
    assert not moves(migrated, old_binding, json.dumps(["BUNDLE_OVERLAY", {}]))


def test_a_built_task_of_an_earlier_door_names_its_earlier_image():
    from types import SimpleNamespace

    from carbon.challenge_validator.lean_recipe_retention import (
        _migrated_admitted_image_id,
    )

    old_binding = json.dumps(
        ["GRAPH_PARENT", OLD], sort_keys=True, separators=(",", ":")
    )
    provider = SimpleNamespace(migrated_image_bindings=frozenset({old_binding}))
    assert _migrated_admitted_image_id(provider, old_binding) == OLD["image_id"]
    assert _migrated_admitted_image_id(provider, "not json") is None
    assert (
        _migrated_admitted_image_id(SimpleNamespace(), old_binding) is None
    )  # no chain on this provider
