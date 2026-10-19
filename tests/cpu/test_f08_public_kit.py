"""Prospective f08 public kit; no evaluation or worker admission claim."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from carbon.challenge_kit import f08_public, f08_train, physical_public
from carbon.development_session import construction_tensor_codec as codec


def test_kit_reuses_exact_pinned_partial_train_and_named_numeric_interface():
    challenge_id, version = f08_train.CHALLENGE_ID, f08_train.CHALLENGE_VERSION
    material = f08_train.load_public_train()
    kit = f08_public.construction_kit(challenge_id, version)
    assert set(kit) == {
        "id",
        "version",
        "train_digest",
        "interface_digest",
        "construction_limits_digest",
    }
    assert kit["train_digest"] == "sha256:" + f08_train.TRAIN_SHA256
    assert hashlib.sha256(material["train"]).hexdigest() == f08_train.TRAIN_SHA256
    assert kit["train_digest"] == material["provenance"]["train_sha256"]
    interface = f08_public.interface_document(challenge_id, version)
    assert kit["interface_digest"] == f08_public._digest(interface)
    assert interface["input"] == {
        "names": list(f08_train.FIELDS),
        "units": ["mm"] * 6,
        "shape": [6],
    }
    assert interface["output"] == {
        "names": list(f08_train.TARGETS),
        "units": ["mm/N", "mm/N", "Hz", "mm/N", "Hz", "mm/N", "Hz"],
        "shape": [7],
        "named_slices": {
            name: [index, index + 1] for index, name in enumerate(f08_train.TARGETS)
        },
    }
    assert interface["one_row_per_geometry"] is True
    assert interface["learned_targets_only"] is True
    assert "mass_kg" not in interface["output"]["names"]
    binding = {
        "challenge_id": challenge_id,
        "challenge_version": version,
        "train_digest": kit["train_digest"],
        "interface_digest": kit["interface_digest"],
        "construction_limits_digest": kit["construction_limits_digest"],
    }
    x, y = codec.train_tensors(material["train"], binding)
    assert x.shape == (255, 6) and y.shape == (255, 7)
    assert x.dtype == y.dtype == np.dtype("float32")
    np.testing.assert_array_equal(x, material["inputs"])
    np.testing.assert_array_equal(y, material["targets"])


def test_f08_limits_bind_partial_source_and_actual_c03_profile():
    from carbon.development_session.local_diagnostic_plan import MAX_TASK_WALL_SECONDS
    from carbon.development_session.research_carrier import (
        LIBRARY_BUILD_PROVENANCE,
        _worker_profile,
    )

    challenge_id, version = f08_train.CHALLENGE_ID, f08_train.CHALLENGE_VERSION
    kit = f08_public.construction_kit(challenge_id, version)
    selected = f08_public.trusted_material(challenge_id, version)
    limits = selected["limits_document"]
    assert selected["limits_schema"] == limits["schema"]
    assert selected["scope"] == limits["scope"]
    assert kit["construction_limits_digest"] == f08_public._digest(limits)
    assert limits["train_cases"] == 255
    assert limits["train_dtype"] == "<f4"
    assert limits["train_case_ids_sha256"] == f08_public._digest(
        f08_train.load_public_train()["case_ids"]
    )
    assert limits["train_provenance_sha256"] == "sha256:" + f08_train.PROVENANCE_SHA256
    assert limits["original_256_complete"] is False
    assert limits["failed_case"] == {"id": "train-0016", "status": "OBSERVER_FAILED"}
    assert limits["original_action_evaluation_role"] == "EXCLUDED_ALL_256"
    assert limits["accuracy_gate"] is None and limits["live_eligible"] is False
    profile = _worker_profile(None, LIBRARY_BUILD_PROVENANCE).body
    policy = limits["reconstruction_resource_policy"]
    assert policy["schema"] == selected["resource_schema"]
    assert policy["cpu_count_max"] == profile["cpu"]["count"]
    assert policy["memory_bytes_max"] == profile["memory"]["bytes"]
    assert policy["swap_bytes_max"] == profile["memory"]["swap_bytes"]
    assert policy["build_wall_seconds_max"] == profile["deadline_seconds"]
    assert policy["inference_wall_seconds_max"] == profile["deadline_seconds"]
    assert policy["total_reconstruction_wall_seconds_max"] == MAX_TASK_WALL_SECONDS
    assert policy["network"] == profile["security"]["network"]
    assert policy["cleanup_required"] is True


def test_f08_source_selector_fails_closed_on_other_identity_or_missing_artifact(
    monkeypatch,
):
    with pytest.raises(ValueError, match="identity"):
        f08_public.construction_kit("chip-cold-plate", f08_train.CHALLENGE_VERSION)
    with pytest.raises(ValueError, match="identity"):
        f08_public.trusted_material(f08_train.CHALLENGE_ID, "9.9")
    monkeypatch.setattr(f08_train, "TRAIN_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="artifact identity"):
        f08_public.construction_kit(f08_train.CHALLENGE_ID, f08_train.CHALLENGE_VERSION)


def test_common_guard_does_not_implicitly_admit_new_f08_source():
    with pytest.raises(ValueError, match="unknown public physical TRAIN"):
        physical_public.construction_kit(
            f08_train.CHALLENGE_ID, f08_train.CHALLENGE_VERSION
        )
