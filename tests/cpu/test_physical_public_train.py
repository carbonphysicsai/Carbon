"""Lossless public TRAIN transport, independent of scientific scoring."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from carbon.challenge_kit import physical_public, physical_public_train as train
from carbon.cold_plate import challenge as cooling, domain as cooling_domain
from carbon.development_session import construction_tensor_codec as codec
from carbon.motor import challenge as motor, domain as motor_domain

ROOT = Path(__file__).resolve().parents[2]
FAMILIES = ((motor, motor_domain, 150), (cooling, cooling_domain, 400))


def _source(challenge):
    return challenge.canonical_text(
        ROOT / challenge.TRAIN_PATH, challenge.TRAIN_SHA256, "train"
    )


@pytest.mark.parametrize("challenge,domain,count", FAMILIES)
def test_pinned_derivative_is_deterministic_lossless_and_codec_readable(
    challenge, domain, count
):
    challenge_id = challenge.CHALLENGE.challenge_id
    original = _source(challenge)
    raw, provenance = train.derive_public_train(challenge_id, original)
    assert (raw, provenance) == train.derive_public_train(challenge_id, original)
    loaded = train.load_public_train(challenge_id)
    assert loaded["train"] == raw
    assert loaded["provenance"] == provenance
    assert len(loaded["case_ids"]) == count
    assert loaded["case_ids"] == tuple(f"train-{i:04d}" for i in range(count))
    assert provenance["source_sha256"] == "sha256:" + challenge.TRAIN_SHA256
    assert provenance["train_sha256"] == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert provenance["numeric_interface"]["input_names"] == list(domain.INPUTS)
    assert loaded["inputs"].dtype == loaded["targets"].dtype == np.dtype("<f8")
    assert not loaded["inputs"].flags.writeable
    assert not loaded["targets"].flags.writeable
    binding = {
        "challenge_id": challenge_id,
        "challenge_version": challenge.CHALLENGE.version,
        "train_digest": provenance["train_sha256"],
        "interface_digest": "sha256:" + "0" * 64,
        "construction_limits_digest": "sha256:" + "1" * 64,
    }
    decoded_x, decoded_y = codec.train_tensors(raw, binding)
    np.testing.assert_array_equal(decoded_x, loaded["inputs"])
    np.testing.assert_array_equal(decoded_y, loaded["targets"])
    rows = [json.loads(line) for line in original.splitlines()]
    for index, row in enumerate(rows):
        assert decoded_x[index].tolist() == [
            float(row["inputs"][name]) for name in domain.INPUTS
        ]
        if challenge is motor:
            assert decoded_y[index].tolist() == [
                float(value) for value in row["outputs"]["torque_nm"]
            ]
        else:
            assert decoded_y[index].tolist() == [
                float(row["outputs"]["peak_c"]),
                *(float(value) for value in row["outputs"]["profile_c"]),
                float(row["outputs"]["pressure_drop_pa"]),
            ]


def test_named_target_slices_preserve_native_index_order():
    motor_layout = train.numeric_interface_document(motor.CHALLENGE.challenge_id)
    cooling_layout = train.numeric_interface_document(cooling.CHALLENGE.challenge_id)
    assert motor_layout["target_slices"] == {"torque_nm": [0, 60]}
    assert cooling_layout["target_slices"] == {
        "peak_c": [0, 1],
        "profile_c": [1, 31],
        "pressure_drop_pa": [31, 32],
    }
    assert motor_layout["target_axis"]["values"] == [
        i * motor_domain.PERIOD_DEG / motor_domain.ANGLE_STEPS
        for i in range(motor_domain.ANGLE_STEPS)
    ]
    assert cooling_layout["target_axis"]["values"] == list(
        range(cooling_domain.PROFILE_SEGMENTS)
    )
    assert cooling_layout["target_units"] == {
        "peak_c": "degC",
        "profile_c": "degC",
        "pressure_drop_pa": "Pa",
    }


@pytest.mark.parametrize("challenge,domain,count", FAMILIES)
@pytest.mark.parametrize(
    "damage",
    ("missing_row", "missing_target", "wrong_vector", "nonfinite", "bool_input"),
)
def test_bad_source_fails_closed(monkeypatch, challenge, domain, count, damage):
    rows = [json.loads(line) for line in _source(challenge).splitlines()]
    if damage == "missing_row":
        rows.pop()
    elif damage == "missing_target":
        rows[0]["outputs"].pop(domain.PREDICTED[0])
    elif damage == "wrong_vector":
        field = "torque_nm" if challenge is motor else "profile_c"
        rows[0]["outputs"][field].pop()
    elif damage == "nonfinite":
        rows[0]["inputs"][domain.INPUTS[0]] = float("nan")
    elif damage == "bool_input":
        rows[0]["inputs"][domain.INPUTS[0]] = True
    raw = b"\n".join(json.dumps(row, allow_nan=True).encode() for row in rows) + b"\n"
    monkeypatch.setattr(challenge, "TRAIN_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError):
        train.derive_public_train(challenge.CHALLENGE.challenge_id, raw)


@pytest.mark.parametrize("challenge,domain,count", FAMILIES)
def test_loader_refuses_modified_artifact(
    monkeypatch, tmp_path, challenge, domain, count
):
    challenge_id = challenge.CHALLENGE.challenge_id
    names = train._ARTIFACTS[challenge_id]
    for name in names:
        (tmp_path / name).write_bytes((train._DATA / name).read_bytes())
    data = bytearray((tmp_path / names[0]).read_bytes())
    data[-1] ^= 1
    (tmp_path / names[0]).write_bytes(data)
    monkeypatch.setattr(train, "_DATA", tmp_path)
    with pytest.raises(ValueError, match="identity differs"):
        train.load_public_train(challenge_id)


@pytest.mark.parametrize("challenge,domain,count", FAMILIES)
def test_normal_kit_binds_derived_digest_and_actual_worker_limits(
    challenge, domain, count
):
    from carbon.development_session.local_diagnostic_plan import MAX_TASK_WALL_SECONDS
    from carbon.development_session.research_carrier import (
        LIBRARY_BUILD_PROVENANCE,
        _worker_profile,
    )

    challenge_id, version = (
        challenge.CHALLENGE.challenge_id,
        challenge.CHALLENGE.version,
    )
    kit = physical_public.construction_kit(challenge_id, version)
    assert set(kit) == {
        "id",
        "version",
        "train_digest",
        "interface_digest",
        "construction_limits_digest",
    }
    provenance = train.load_public_train(challenge_id)["provenance"]
    assert kit["train_digest"] == provenance["train_sha256"]
    assert kit["train_digest"] != "sha256:" + challenge.TRAIN_SHA256
    assert kit["interface_digest"] == physical_public._digest(
        physical_public.interface_document(challenge_id, version)
    )
    selected = physical_public.trusted_material(challenge_id, version)
    limits = selected["limits_document"]
    assert kit["construction_limits_digest"] == physical_public._digest(limits)
    assert limits["train_cases"] == count
    assert limits["accuracy_gate"] is None and limits["live_eligible"] is False
    profile = _worker_profile(None, LIBRARY_BUILD_PROVENANCE).body
    policy = limits["reconstruction_resource_policy"]
    assert policy["cpu_count_max"] == profile["cpu"]["count"]
    assert policy["memory_bytes_max"] == profile["memory"]["bytes"]
    assert policy["network"] == profile["security"]["network"]
    assert policy["total_reconstruction_wall_seconds_max"] == MAX_TASK_WALL_SECONDS


def test_unknown_or_unmaterialized_physical_selector_fails_closed():
    with pytest.raises(ValueError, match="unknown public physical TRAIN"):
        physical_public.construction_kit("f02-burst-thermal", "1.0")
    with pytest.raises(ValueError, match="version"):
        physical_public.construction_kit(motor.CHALLENGE.challenge_id, "9.9")
