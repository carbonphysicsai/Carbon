"""A task ADMITTED and BUILT before a declared door migration (state_binding M1-M3: new worker images, the A100 graph
GPU lane) (16 Nov 2026, 116 drained: "admitted_image_changed"). Reproduces it through the graph retention path
(`lean_recipe_retention._collect_graph_artifacts`) with a real owner provider re-frozen by the migration: the task's
admitted image binding and its evidence name the OLD images, the provider now serves the NEW ones (TE3's repro).

(B) (Lead + Validator-2, 17 Nov): a task BUILT under an earlier door of the checked chain is GRADED WITH ITS ADMITTED
image (the earlier door's full identity), checked on the host first; absent there it is Carbon's failure (typed,
FAILED_INFRA), never the candidate's. Every inference of its grade (the regrade's passes, the pair, the single calls,
the menu re-check) runs on that image. A task GPU-built under the earlier door names that door's graph GPU image. A
bundle overlay task built on an earlier door's construction parent is graded with that door's parent and inference
image. Without a declared migration, and for an image that is no earlier door's, the check still refuses.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest
from test_direct_parents import torch_image
from test_direct_two_parent_tasks import _tasks

from carbon.challenge_validator import auto_grade
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.lean_recipe_retention import (
    MIGRATED_ACCELERATOR_DIFFERS,
    MIGRATED_IMAGE_UNAVAILABLE,
    RetentionUnavailable,
    _collect_graph_artifacts,
)
from carbon.development_session import gpu_practice
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
from carbon.reconstruction.worker.model import WorkerImageIdentity

needs_fcntl = pytest.mark.skipif(
    sys.platform == "win32", reason="the task supervisor leases with fcntl"
)

SUBMISSION = "task-admitted-before-the-migration"
H = "sha256:" + "1" * 64
OLD_GPU = "sha256:" + "6" * 64


class _Recipe:
    digest = H

    @staticmethod
    def to_dict():
        # a source digest the evidence does NOT name: the call fails right AFTER the image check
        return {"source": {"submission_digest": "sha256:" + "9" * 64}, "challenge": {}}


def _evidence(image_id, **lane):
    return {
        "schema": "carbon.direct-private-attempt.graph.v1",
        "image_id": image_id,
        "parent_image_id": image_id,
        "inference_image_id": image_id,
        "build_operation": "operation-" + "a" * 64,
        "inference_operation": "operation-" + "b" * 64,
        "build_controls_digest": H,
        "inference_controls_digest": H,
        "state_digest": H,
        "predictions_digest": H,
        "build_receipt": {},
        "inference_receipt": {},
        "predictions_raw_base64": "",
        "submission_digest": "sha256:" + "8" * 64,
        "predictions": [],
        **lane,
    }


@pytest.fixture
def host(monkeypatch):
    """The grading host's image store as the read-only doctor sees it: ``present`` holds the eligible image ids."""
    present = set()
    seen = []

    def doctor(*, image_id=None, image_identity=None, **_):
        seen.append((image_id, image_identity))
        return SimpleNamespace(
            eligible=image_id in present and image_identity.image_id == image_id
        )

    monkeypatch.setattr(
        "carbon.reconstruction.worker.docker_runtime.doctor", doctor, raising=True
    )
    return SimpleNamespace(present=present, seen=seen)


def _migrated_provider(tmp_path, monkeypatch, *, migrated=True):
    """An owner opened under the OLD images, one graph task admitted there, then reopened under the NEW images after a
    declared migration (as the receiver does: binding_migrated + the earlier door's graph image bindings and lanes).
    """
    old = torch_image()
    old_parents = gpu_practice.DirectParents.from_torch(old)
    tasks, request, _resolver, _checked = _tasks(
        tmp_path, monkeypatch, old_parents, "python-cpu-py311"
    )
    root = tasks._path.parent
    admitted = DirectDevelopmentTasksV3._image_binding(tasks.inference_image)
    tasks.close()
    new = replace(
        old, image_id="sha256:" + "e" * 64, config_digest="sha256:" + "e" * 64
    )
    provider = DirectDevelopmentTasksV3(
        root=root,
        requester="miner",
        ledger=tasks.ledger,
        owner="miner",
        discovery=tasks.discovery,
        image=None,
        inference_image=new,
        image_resolver=tasks.image_resolver,
        construction_parents=gpu_practice.DirectParents.from_torch(new),
        binding_migrated=migrated,
        migrated_image_bindings=frozenset({admitted}) if migrated else frozenset(),
        migrated_graph_gpu_images=(
            {admitted: frozenset({OLD_GPU})} if migrated else {}
        ),
    )
    provider._requests[SUBMISSION] = request
    provider._task_image_bindings[SUBMISSION] = admitted
    monkeypatch.setattr(
        provider, "_resolved_image", lambda _request: provider.inference_image
    )
    return provider, old, new


def _code(provider, evidence):
    with pytest.raises(RetentionUnavailable) as raised:
        _collect_graph_artifacts(provider, SUBMISSION, None, evidence, _Recipe(), {})
    return raised.value.code


@needs_fcntl
def test_a_task_built_before_a_declared_migration_gets_past_the_image_check_on_its_admitted_image(
    tmp_path, monkeypatch, host
):
    provider, old, _new = _migrated_provider(tmp_path, monkeypatch)
    try:
        host.present.add(old.image_id)
        # was "admitted_image_changed" on 116 (FAILED_INFRA), then held (5de00da7); now past the image check
        assert _code(provider, _evidence(old.image_id)) == (
            "admitted_graph_source_changed"
        )
        # checked on the host as the ADMITTED identity, exactly
        assert host.seen == [(old.image_id, old)]
        assert "migrated_build_held" not in auto_grade._PENDING
    finally:
        provider.close()


@needs_fcntl
def test_an_admitted_image_absent_from_the_host_is_carbons_failure(
    tmp_path, monkeypatch, host
):
    provider, old, _new = _migrated_provider(tmp_path, monkeypatch)
    try:
        code = _code(provider, _evidence(old.image_id))
        assert code == MIGRATED_IMAGE_UNAVAILABLE
        # not a pending code (never held forever) and not a candidate code: the grader's FAILED give-back
        assert code not in auto_grade._PENDING
    finally:
        provider.close()


@needs_fcntl
def test_a_task_gpu_built_under_the_earlier_door_names_that_doors_gpu_image(
    tmp_path, monkeypatch, host
):
    provider, old, _new = _migrated_provider(tmp_path, monkeypatch)
    try:
        host.present.add(old.image_id)
        built = _evidence(old.image_id, build_device="GPU", build_image_id=OLD_GPU)
        assert _code(provider, built) == "admitted_graph_source_changed"
        other = _evidence(
            old.image_id, build_device="GPU", build_image_id="sha256:" + "5" * 64
        )
        assert _code(provider, other) == "graph_worker_evidence_unavailable"
    finally:
        provider.close()


@needs_fcntl
def test_without_a_declared_migration_the_owner_does_not_even_open(
    tmp_path, monkeypatch
):
    """Unchanged guard: new images without a declared migration refuse at the owner's binding, before any grade."""
    with pytest.raises(ValueError, match="image binding changed"):
        _migrated_provider(tmp_path, monkeypatch, migrated=False)


@needs_fcntl
def test_an_image_that_is_no_earlier_doors_still_refuses_after_a_migration(
    tmp_path, monkeypatch, host
):
    provider, _old, _new = _migrated_provider(tmp_path, monkeypatch)
    try:
        other = "sha256:" + "f" * 64
        host.present.add(other)
        provider._task_image_bindings[SUBMISSION] = (
            DirectDevelopmentTasksV3._image_binding(
                replace(torch_image(), image_id=other, config_digest=other)
            )
        )
        assert _code(provider, _evidence(other)) == "admitted_image_changed"
        assert host.seen == []  # never checked, never graded
    finally:
        provider.close()


# -- the admitted-image selection, without a task supervisor (runs everywhere) ----------------------------------------

OLD_ID, NEW_ID, OTHER_ID = ("sha256:" + c * 64 for c in "1ab")


def _identity(image_id):
    # a worker image's id is its config digest (WorkerImageIdentity checks it)
    return WorkerImageIdentity(
        image_id, image_id, *("sha256:" + c * 64 for c in "345678")
    )


OLD, NEW, OTHER = _identity(OLD_ID), _identity(NEW_ID), _identity(OTHER_ID)
GRAPH_OLD = DirectDevelopmentTasksV3._image_binding(OLD)
GRAPH_OTHER = DirectDevelopmentTasksV3._image_binding(OTHER)


def _overlay(parent_id):
    return json.dumps(
        [
            "BUNDLE_OVERLAY",
            {
                "parent_image_id": parent_id,
                "bundle_ref": {},
                "tree_digest": H,
                "archive_digest": H,
            },
        ],
        sort_keys=True,
        separators=(",", ":"),
    )


def _provider(**bindings):
    return SimpleNamespace(
        inference_image=NEW,
        inference_accelerator=None,
        _image_binding=DirectDevelopmentTasksV3._image_binding,
        _task_image_bindings=dict(bindings),
        migrated_image_bindings=frozenset({GRAPH_OLD}),
        migrated_bundle_images={
            OLD_ID: {"parent": asdict(OLD), "inference_image": asdict(OLD)}
        },
    )


def test_only_an_exact_earlier_doors_image_is_an_admitted_image():
    provider = _provider(
        graph=GRAPH_OLD,
        other=GRAPH_OTHER,
        current=DirectDevelopmentTasksV3._image_binding(NEW),
        bundle=_overlay(OLD_ID),
        bundle_other=_overlay(OTHER_ID),
        bundle_current=_overlay(NEW_ID),
    )
    images = retention._task_admitted_images
    assert images(provider, "graph") == (OLD, OLD)
    assert images(provider, "bundle") == (OLD, OLD)
    for task in ("other", "current", "bundle_other", "bundle_current", "unknown"):
        assert images(provider, task) is None, task
    # a malformed earlier-door bundle record is no admitted image (fail closed)
    provider.migrated_bundle_images[OLD_ID] = {"parent": {"image_id": OLD_ID}}
    assert images(provider, "bundle") is None
    # an earlier door's image the current door still binds is the current door's own
    provider.migrated_image_bindings = frozenset({GRAPH_OLD})
    provider.inference_image = OLD
    assert images(provider, "graph") is None


def test_every_inference_of_a_migrated_tasks_grade_uses_its_admitted_image():
    provider = _provider(graph=GRAPH_OLD, other=GRAPH_OTHER)
    # the selected-pack passes with no regrade (pair, subset repeat, menu re-check, single calls)
    assert retention._inference_image_of(provider, None, "graph") == OLD
    assert retention._inference_image_of(provider, None, "other") is NEW
    assert retention._inference_image_of(provider, None) is NEW
    # a regrade carries the image it chose (`_regrade_inference_image`)
    chosen = SimpleNamespace(inference_image=OLD)
    assert retention._inference_image_of(provider, chosen, "other") == OLD


def _regrade(provider, origin, files, kind="graph"):
    recipe = SimpleNamespace(
        to_dict=lambda: {"source": {"kind": kind, "bundle_ref": {"x": 1}}}
    )
    return retention._regrade_inference_image(
        kind, files, provider, recipe, origin, None
    )


def test_the_counted_regrade_infers_on_the_admitted_image_checked_on_the_host(host):
    provider = _provider(graph=GRAPH_OLD, other=GRAPH_OTHER)
    files = {"image.json": json.dumps(asdict(OLD)).encode()}
    with pytest.raises(RetentionUnavailable, match=MIGRATED_IMAGE_UNAVAILABLE):
        _regrade(provider, "graph", files)
    host.present.add(OLD_ID)
    assert _regrade(provider, "graph", files) == OLD
    assert host.seen[-1] == (OLD_ID, OLD)
    # a retained record that is not exactly the admitted identity, or a task of no earlier door: refused as before
    changed = {"image.json": json.dumps({**asdict(OLD), "wheel_digest": H}).encode()}
    with pytest.raises(RetentionUnavailable, match="regrade_construction_parent"):
        _regrade(provider, "graph", changed)
    other = {"image.json": json.dumps(asdict(OTHER)).encode()}
    with pytest.raises(RetentionUnavailable, match="regrade_construction_parent"):
        _regrade(provider, "other", other)


def test_a_migrated_bundle_regrade_infers_on_its_earlier_doors_inference_image(
    host, monkeypatch
):
    monkeypatch.setattr(
        "carbon.development_session.library_bundles.LibraryBundleRef.from_dict",
        lambda value: value,
    )
    monkeypatch.setattr(retention, "_construction_parent", lambda provider, bundle: NEW)
    host.present.add(OLD_ID)
    provider = _provider(bundle=_overlay(OLD_ID), other=_overlay(OTHER_ID))
    files = {"image.json": json.dumps({"parent_image_id": OLD_ID}).encode()}
    assert _regrade(provider, "bundle", files, kind="bundle") == OLD
    other = {"image.json": json.dumps({"parent_image_id": OTHER_ID}).encode()}
    with pytest.raises(RetentionUnavailable, match="regrade_construction_parent"):
        _regrade(provider, "other", other, kind="bundle")


def test_an_admitted_image_on_another_accelerator_is_carbons_failure(host):
    host.present.add(OLD_ID)
    provider = _provider()
    provider.inference_accelerator = (
        "GPU"  # the door infers on a GPU, the admitted image on the CPU
    )
    with pytest.raises(RetentionUnavailable, match=MIGRATED_ACCELERATOR_DIFFERS):
        retention._verify_admitted_image(provider, OLD)
    assert host.seen == []  # refused before any host read


def test_a_bundle_overlay_built_on_an_earlier_doors_parent_is_checked_with_that_doors_images():
    """The bundle retention's overlay identity check (`_retain_served_artifacts`) reads its parent and inference image
    from here: an exact earlier-door construction parent takes that door's images; anything else keeps the current
    ones, so the check refuses it as before (``source_overlay_unavailable``)."""
    provider = _provider()
    current = _identity("sha256:" + "c" * 64)
    choose = retention._bundle_overlay_images
    assert choose(provider, current, json.loads(_overlay(OLD_ID))) == (OLD, OLD)
    for binding in (
        json.loads(_overlay(OTHER_ID)),  # no earlier door's parent
        json.loads(_overlay(current.image_id)),  # the current door's own task
        ["BUNDLE_SOURCE", {"parent_image_id": OLD_ID}],  # another binding form
        "not a binding",
    ):
        assert choose(provider, current, binding) == (current, NEW), binding


# -- every re-grade caller (Validator-2, 17 Nov): the counted grade, operator / uncounted regrades, the king's upkeep,
#    crown repeats and rebuild evidence all reach `regrade_retained_entry` -> `_regrade_inference_image` ---------------


def test_the_admitted_images_are_read_from_the_retained_record_alone():
    """A king or task admitted under an earlier contract has no row in the current provider: the regrade reads the
    sha-checked retained image.json, never the provider's task row."""
    provider = _provider()  # no task bindings at all
    graph = {"image.json": json.dumps(asdict(OLD)).encode()}
    assert retention._retained_admitted_images("graph", graph, provider) == (OLD, OLD)
    bundle = {"image.json": json.dumps({"parent_image_id": OLD_ID}).encode()}
    assert retention._retained_admitted_images("bundle", bundle, provider) == (
        OLD,
        OLD,
    )
    for kind, record in (
        ("graph", asdict(OTHER)),  # no earlier door's image
        ("graph", asdict(NEW)),  # the current door's own
        ("graph", {"image_id": OLD_ID}),  # not a whole identity
        ("graph", {**asdict(OLD), "wheel_digest": H}),  # not exactly the door's
        ("bundle", {"parent_image_id": OTHER_ID}),
    ):
        files = {"image.json": json.dumps(record).encode()}
        assert retention._retained_admitted_images(kind, files, provider) is None
    assert retention._retained_admitted_images("graph", {}, provider) is None


@pytest.fixture
def regrade_harness(tmp_path, monkeypatch, host):
    """`regrade_retained_entry` up to its first worker call, the worker monkeypatched to record its arguments (no
    docker, model or solver runs): an old-image graph model retained before the migration, its owner's provider on the
    NEW door with the earlier door's images threaded in."""
    import numpy as np

    from carbon.challenge_validator import speed_match
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
    from carbon.development_session import bundle_construction_worker as worker
    from carbon.development_session.bundle_construction_worker import _tensors
    from carbon.development_session.construction_recipe import RecipeRefused

    seen = []

    def infer_state(ledger, **kwargs):
        seen.append(kwargs)
        raise RecipeRefused("recorded")

    monkeypatch.setattr(worker, "_infer_state", infer_state)
    monkeypatch.setattr(worker, "_checked_binding", lambda *_a: {})
    monkeypatch.setattr(worker, "verify_direct_resource_policy", lambda *_a: None)
    monkeypatch.setattr(worker, "rebuild_wall_kwargs", lambda *_a: {})
    monkeypatch.setattr(retention, "_graph_regrade_query", lambda *_a, **_k: {})
    monkeypatch.setattr(retention, "_pool_graded_version", lambda _adapter: False)
    monkeypatch.setattr(retention, "_owner_directory", lambda value, _label: value)
    monkeypatch.setattr(retention, "output_dtype", lambda _interface: "float32")
    monkeypatch.setattr(speed_match, "tolerance", lambda *_a: None)

    practice = np.zeros((2, 3), dtype=np.float32)
    bank = np.ones((4, 3), dtype=np.float32)
    bank_raw = _tensors(inputs=bank)
    snapshot = SimpleNamespace(manifest_digest=H, read_role=lambda *_a, **_k: bank_raw)
    discovery = SimpleNamespace(
        evaluation_pack_snapshot=snapshot,
        evaluation_pack_digest=H,
        evaluation_pack_private_root=tmp_path,
        _material={
            "construction_kit": {
                "id": "x",
                "version": "1",
                **dict.fromkeys(
                    ("train_digest", "interface_digest", "construction_limits_digest"),
                    H,
                ),
            },
            "construction_limits_document": {
                "reconstruction_resource_policy": {"inference_wall_seconds_max": 60}
            },
            "interface_document": {},
            "practice_inputs": practice,
            "expected_output_shape": [2, 1],
            "allowlist_bytes": b"{}",
        },
    )
    provider = _provider()
    provider.ledger = SimpleNamespace(root=tmp_path)
    provider.construction_parent = NEW
    adapter = object.__new__(LeanRecipeAdapter)
    adapter.discovery = discovery
    adapter.challenge_id, adapter.challenge_version = "x", "1"
    adapter._provider = lambda owner: provider if owner == "miner" else None
    entry = {"challenge": "x", "challenge_version": "1", "state_digest": H}
    recipe = SimpleNamespace(to_dict=lambda: {"source": {"kind": "graph"}}, digest=H)

    def origin(record):
        files = {"image.json": json.dumps(record).encode(), "state.npz": b"state"}
        monkeypatch.setattr(
            retention,
            "_regrade_origin",
            lambda *_a, **_k: (entry, "rtsk_" + "0" * 64, "miner", {}, files, recipe),
        )

    def grade(**kwargs):
        with pytest.raises(RetentionUnavailable) as raised:
            retention.regrade_retained_entry(
                adapter,
                H,
                artifact_directory=tmp_path,
                entry_directory=tmp_path,
                **kwargs,
            )
        return raised.value.code

    return SimpleNamespace(seen=seen, origin=origin, grade=grade, host=host)


@pytest.mark.parametrize(
    "call",
    [
        {"counted": True},  # the counted grade (`_counted_bank_grade`)
        {},  # operator / uncounted regrade, the king's upkeep regrade (`regrade_result`)
        {
            "repeat_index": 1
        },  # crown repeat and rebuild evidence (`repeat_grade`, `retain_rebuild_evidence`)
    ],
)
def test_every_regrade_of_an_old_image_model_infers_on_its_admitted_image(
    regrade_harness, call
):
    regrade_harness.host.present.add(OLD_ID)
    regrade_harness.origin(asdict(OLD))
    assert regrade_harness.grade(**call) == "regrade_inference_recorded"
    (kwargs,) = regrade_harness.seen
    assert (
        kwargs["inference_image"] == OLD
    )  # the admitted image, never the door's current one
    assert regrade_harness.host.seen == [(OLD_ID, OLD)]


def test_a_regrade_whose_admitted_image_is_absent_is_carbons_failure(regrade_harness):
    regrade_harness.origin(asdict(OLD))
    assert regrade_harness.grade(counted=True) == MIGRATED_IMAGE_UNAVAILABLE
    assert regrade_harness.seen == []  # no inference ran


def test_a_regrade_of_a_model_of_no_earlier_door_still_refuses(regrade_harness):
    regrade_harness.host.present.add(OTHER_ID)
    regrade_harness.origin(asdict(OTHER))
    assert regrade_harness.grade() == "regrade_construction_parent_differs"
    assert regrade_harness.seen == [] and regrade_harness.host.seen == []


def test_the_kings_upkeep_regrades_an_old_image_king_instead_of_rebuilding(
    monkeypatch, tmp_path
):
    """`king_upkeep._step`: a moved parent sends the king to a rebuild on the current image; a king BUILT under an
    earlier door of the chain is regraded with his admitted image instead (the same program as before the switch).
    """
    provider = _provider()
    adapter = SimpleNamespace(_provider=lambda owner: provider)
    monkeypatch.setattr(retention, "_owner_directory", lambda value, _label: value)
    recipe = SimpleNamespace(to_dict=lambda: {"source": {"kind": "graph"}})

    def moved(record):
        files = {"image.json": json.dumps(record).encode()}
        monkeypatch.setattr(
            retention,
            "_regrade_origin",
            lambda *_a, **_k: ({}, "rtsk_" + "0" * 64, "miner", {}, files, recipe),
        )
        return retention.king_parent_moved(
            adapter,
            SimpleNamespace(incumbent=lambda: None),
            H,
            artifact_directory=tmp_path,
            entry_directory=tmp_path,
        )

    assert moved(asdict(OLD)) is False  # regraded with his admitted image
    assert moved(asdict(OTHER)) is True  # no earlier door's image: rebuilt, as before
    assert moved(asdict(NEW)) is False  # the current image: an ordinary regrade
