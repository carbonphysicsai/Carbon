"""A task ADMITTED before a declared door migration (state_binding M1-M3: new worker images, the A100 graph GPU lane)
(16 Nov 2026, 116 drained: "admitted_image_changed"). Reproduces it through the graph retention path
(`lean_recipe_retention._collect_graph_artifacts`) with a real owner provider re-frozen by the migration: the task's
admitted image binding and its evidence name the OLD images, the provider now serves the NEW ones (TE3's repro).

Expected now: a task BUILT under an earlier door of the checked chain is HELD (a pending code: nothing reserved or
charged; graded with its admitted image in a later head), never refused as Carbon's failure and never graded on another
image; without a declared migration, and for an image that is no earlier door's, the check still refuses.
"""

from __future__ import annotations

import sys
from dataclasses import replace

import pytest
from test_direct_parents import torch_image
from test_direct_two_parent_tasks import _tasks

from carbon.challenge_validator import auto_grade
from carbon.challenge_validator.lean_recipe_retention import (
    MIGRATED_BUILD_HELD,
    RetentionUnavailable,
    _collect_graph_artifacts,
)
from carbon.development_session import gpu_practice
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="the task supervisor leases with fcntl"
)

SUBMISSION = "task-admitted-before-the-migration"
H = "sha256:" + "1" * 64


class _Recipe:
    digest = H

    @staticmethod
    def to_dict():
        # a source digest the evidence does NOT name: the call fails right AFTER the image check
        return {"source": {"submission_digest": "sha256:" + "9" * 64}, "challenge": {}}


def _evidence(image_id):
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
    }


def _migrated_provider(tmp_path, monkeypatch, *, migrated=True):
    """An owner opened under the OLD images, one graph task admitted there, then reopened under the NEW images after a
    declared migration (as the receiver does: binding_migrated + the earlier door's graph image bindings).
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


def test_a_task_built_before_a_declared_migration_is_held_not_failed(
    tmp_path, monkeypatch
):
    provider, old, _new = _migrated_provider(tmp_path, monkeypatch)
    try:
        # was "admitted_image_changed" on 116 (FAILED_INFRA); now held: a pending code, nothing reserved
        code = _code(provider, _evidence(old.image_id))
        assert code == MIGRATED_BUILD_HELD
        assert code in auto_grade._PENDING
    finally:
        provider.close()


def test_without_a_declared_migration_the_owner_does_not_even_open(
    tmp_path, monkeypatch
):
    """Unchanged guard: new images without a declared migration refuse at the owner's binding, before any grade."""
    with pytest.raises(ValueError, match="image binding changed"):
        _migrated_provider(tmp_path, monkeypatch, migrated=False)


def test_an_image_that_is_no_earlier_doors_still_refuses_after_a_migration(
    tmp_path, monkeypatch
):
    provider, _old, _new = _migrated_provider(tmp_path, monkeypatch)
    try:
        other = "sha256:" + "f" * 64
        provider._task_image_bindings[SUBMISSION] = (
            DirectDevelopmentTasksV3._image_binding(
                replace(torch_image(), image_id=other, config_digest=other)
            )
        )
        assert _code(provider, _evidence(other)) == "admitted_image_changed"
    finally:
        provider.close()
