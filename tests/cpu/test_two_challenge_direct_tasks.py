"""One direct task provider carries each Challenge's original public TRAIN.

The child boundary is intercepted before model code runs. Battery has no
registered score in this prospective DEVELOPMENT construction test.
"""

import hashlib
from pathlib import Path

import pytest
from test_direct_v3_durable_tasks import _fixture

from carbon import research
from carbon.battery import challenge as battery_challenge
from carbon.battery.construction_bundle_material import (
    bundle_material as battery_material,
)
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.development_session import bundle_construction_worker

ROOT = Path(__file__).resolve().parents[2]


def _material(kind):
    return battery_material() if kind == "battery" else bundle_material_v5()


@pytest.mark.parametrize("kind", ("synthetic", "battery"))
def test_registered_challenge_train_reaches_same_direct_task_child(
    tmp_path, monkeypatch, kind
):
    material = _material(kind)
    original_train = material["train"]
    if kind == "battery":
        assert original_train == (ROOT / battery_challenge.TRAIN_V1_PATH).read_bytes()
        assert hashlib.sha256(original_train).hexdigest() == (
            battery_challenge.TRAIN_V1_SHA256
        )
    selected_root = tmp_path / "selected"
    selected_root.mkdir()
    request, provider, discovery = _fixture(
        selected_root, monkeypatch, material=material
    )
    other = _material("battery" if kind == "synthetic" else "synthetic")
    other_root = tmp_path / "other"
    other_root.mkdir()
    other_request, _other_provider, _other_discovery = _fixture(
        other_root, monkeypatch, material=other
    )
    assert request.challenge_key == discovery.info.challenge_key
    assert request.public_train_digest == material["construction_kit"]["train_digest"]
    assert request.challenge_key != other_request.challenge_key

    tasks = provider()
    try:
        admitted = tasks.start_research_task(request).task
        assert admitted.immutable_bindings.challenge_key == request.challenge_key
        assert admitted.immutable_bindings.public_train_digest == (
            request.public_train_digest
        )
        with pytest.raises((ValueError, research.ResearchTaskProviderError)):
            tasks.start_research_task(other_request)

        observed = {}

        def stop_before_child(*_args, **kwargs):
            observed.update(kwargs)
            raise ValueError("test-only child stop")

        monkeypatch.setattr(
            bundle_construction_worker,
            "reconstruct_and_infer_public",
            stop_before_child,
        )
        result = tasks.run_queued_task(admitted.task_id)
        assert result.state is research.DirectTaskStateV3.UNRESOLVED
        assert observed["train"] == original_train
        assert observed["challenge_binding"] == {
            "challenge_id": request.challenge_key.challenge_id,
            "challenge_version": request.challenge_key.version,
            "train_digest": request.public_train_digest,
            "interface_digest": request.interface_digest,
            "construction_limits_digest": request.construction_limits_digest,
        }
        assert observed["expected_output_shape"] == material["expected_output_shape"]
    finally:
        tasks.close()
