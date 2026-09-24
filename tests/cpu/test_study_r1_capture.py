"""R1 on session records: two simulated validators, decided by compare_r1.

The records are shaped exactly as `repeat_gpu.py` prints them. Every refusal is
paired with an acceptance on the same record, so a green run cannot come from a
check that is incapable of firing. The NVML name map ships empty; these tests
register a name for the duration of each test, standing in for a name read on a
real device.
"""

import json
from pathlib import Path

import pytest

from scripts.dev.gpu_determinism_study import r1_capture
from scripts.dev.gpu_determinism_study.compare_units import RecordError

REPO = Path(__file__).resolve().parents[2]
DEVIATION = REPO / "docs/development/GPU_DETERMINISM_STAGE_B_DRIVER_DEVIATION.json"
PINNED = (
    "--xla_gpu_deterministic_ops=true --xla_gpu_exclude_nondeterministic_ops=true "
    "--xla_gpu_autotune_level=0"
)
A40_NAME = "specimen A40 name"
L4_NAME = "specimen L4 name"
HOST_1 = ("GPU-6fb9f860-a693-1f05-8510-09300c93d617", "580.159.03")
HOST_2 = ("GPU-b55ef9f3-5fd2-d26b-3a56-95b9b65260d7", "580.159.03")
VALUES = [0.9803, -0.25, 0.5, 0.0]


@pytest.fixture(autouse=True)
def recorded_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        r1_capture, "PART_BY_NVML_NAME", {A40_NAME: "A40", L4_NAME: "L4"}
    )


def record(label, unit, *, name=A40_NAME, values=VALUES, **overrides):
    uuid, driver = unit
    hexed = [float(v).hex() for v in values]
    base = {
        "label": label,
        "numerics": {
            "schema": "carbon.numerics.v1",
            "backend": "gpu",
            "xla_flags": PINNED,
            "default_matmul_precision": "highest",
            "nvidia_tf32_override": "0",
            "cublas_workspace_config": ":4096:8",
            "cuda_version": "13.0",
            "cudnn_version": "9.1",
            "cpu_effective_isa": "AVX512",
        },
        "software": {"python": "3.11.9", "jax": "0.7.0", "jaxlib": "0.7.0"},
        "device_identity": {
            "index": 0,
            "uuid": uuid,
            "name": name,
            "driver_version": driver,
        },
        "materials": {
            "plan_ref": {
                "challenge_id": "fixture_authoring",
                "challenge_version": "1.0",
                "schema_version": "1.0",
                "canonicalization_profile": "carbon_construction_canonical_v1",
                "digest": "sha256:" + "c" * 64,
            },
            "plan_sha256": "1" * 64,
            "train_sha256": "2" * 64,
            "randomness_sha256": "3" * 64,
        },
        "runs": [
            {
                "index": i,
                "status": "COMPLETE",
                "weights_sha256": "d" * 64,
                "predictions": hexed,
            }
            for i in range(3)
        ],
        "bit_identical": True,
    }
    for key, value in overrides.items():
        section, _, field = key.partition("__")
        if field:
            base[section][field] = value
        else:
            base[section] = value
    return base


def validators(first=None, second=None):
    return [
        ("v1.json", first or record("v1", HOST_1)),
        ("v2.json", second or record("v2", HOST_2)),
    ]


def test_two_simulated_validators_on_one_part_are_reproducible() -> None:
    result = r1_capture.compare(validators())
    assert result["outcome"] == "AGREE"
    assert result["r1"]["outcome"] == "REPRODUCIBLE"
    assert result["r1"]["pairs"][0]["max_absolute_delta"] == 0.0
    assert "not validator_launch" in result["r1"]["execution"]


def test_one_float32_ulp_is_not_reproducible() -> None:
    shifted = [VALUES[0] + 2.0**-24, *VALUES[1:]]
    result = r1_capture.compare(validators(second=record("v2", HOST_2, values=shifted)))
    assert result["r1"]["outcome"] == "NOT_REPRODUCIBLE"
    assert result["r1"]["pairs"][0]["max_absolute_delta"] == 2.0**-24


def test_different_parts_fail_identity_before_any_numerical_comparison() -> None:
    result = r1_capture.compare(validators(second=record("v2", HOST_2, name=L4_NAME)))
    pair = result["r1"]["pairs"][0]
    assert pair["outcome"] == "R0_IDENTITY_MISMATCH"
    assert pair["r0_mismatched_fields"] == ["backend_profile_ref"]


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"materials__train_sha256": "9" * 64}, "generator_ref"),
        ({"materials__randomness_sha256": "9" * 64}, "seed_role_structure_ref"),
        ({"numerics__cuda_version": "12.8"}, "environment_ref"),
        (
            {"software": {"python": "3.11.9", "jax": "0.6.2", "jaxlib": "0.6.2"}},
            "environment_ref",
        ),
    ],
)
def test_a_difference_in_what_ran_is_an_identity_mismatch(override, field) -> None:
    result = r1_capture.compare(validators(second=record("v2", HOST_2, **override)))
    pair = result["r1"]["pairs"][0]
    assert pair["outcome"] == "R0_IDENTITY_MISMATCH"
    assert field in pair["r0_mismatched_fields"]


def test_host_cpu_isa_is_recorded_but_not_identity() -> None:
    other = record("v2", HOST_2, numerics__cpu_effective_isa="AVX2")
    assert (
        r1_capture.compare(validators(second=other))["r1"]["outcome"] == "REPRODUCIBLE"
    )


def test_differing_drivers_stop_before_r1_and_a_deviation_lets_it_run() -> None:
    stage_b = record("v2", (HOST_2[0], "580.159.04"))
    refused = r1_capture.compare(validators(second=stage_b))
    assert refused["outcome"] == "REFUSED_DRIVER_MISMATCH"
    assert refused["r1"] is None
    from scripts.dev.gpu_determinism_study.compare_units import DriverDeviation

    deviation = DriverDeviation.read(json.loads(DEVIATION.read_text()))
    admitted = r1_capture.compare(validators(second=stage_b), deviation)
    assert admitted["r1"]["outcome"] == "REPRODUCIBLE"
    assert admitted["deviation"] is not None


def test_an_unrecorded_device_name_has_no_capture(monkeypatch) -> None:
    r1_capture.capture(record("v1", HOST_1))  # the recorded name is captured
    with pytest.raises(RecordError, match="not a recorded name"):
        r1_capture.capture(record("v1", HOST_1, name="NVIDIA A100-SXM4-80GB"))
    monkeypatch.setattr(r1_capture, "PART_BY_NVML_NAME", {})
    with pytest.raises(RecordError, match="not a recorded name"):
        r1_capture.capture(record("v1", HOST_1))


def test_the_shipped_name_map_holds_only_names_read_on_real_devices() -> None:
    """Every entry is backed by an identity read committed as evidence."""
    import importlib

    fresh = importlib.reload(r1_capture)
    try:
        evidence = REPO / "docs/development/evidence/r1-simulated-validators-2026-09-24"
        read = {
            device["name"]
            for identity in evidence.glob("*/identity.json")
            for device in json.loads(identity.read_text())
        }
        assert (
            set(fresh.PART_BY_NVML_NAME)
            == read
            == {
                "NVIDIA L4",
                "NVIDIA H100 80GB HBM3",
            }
        )
        # Qualified but never read: no entry, so no capture.
        assert not {"A40", "RTX PRO 6000 SE"} & set(fresh.PART_BY_NVML_NAME.values())
    finally:
        importlib.reload(r1_capture)


def test_a_session_whose_runs_disagree_has_no_capture() -> None:
    specimen = record("v1", HOST_1)
    r1_capture.capture(specimen)
    specimen["runs"][2]["predictions"] = [float(v).hex() for v in [0.1, *VALUES[1:]]]
    with pytest.raises(RecordError, match="different predictions"):
        r1_capture.capture(specimen)


def test_a_session_without_predictions_has_no_capture() -> None:
    specimen = record("v1", HOST_1)
    for run in specimen["runs"]:
        run.pop("predictions")
    with pytest.raises(RecordError, match="STUDY_PREDICTIONS=1"):
        r1_capture.capture(specimen)


def test_a_session_on_another_challenge_has_no_capture() -> None:
    specimen = record("v1", HOST_1)
    specimen["materials"]["plan_ref"]["challenge_id"] = "fixture-burgers"
    with pytest.raises(RecordError, match="valid R1 identity"):
        r1_capture.capture(specimen)


def test_predictions_round_trip_bit_for_bit() -> None:
    import numpy as np

    values = np.array([0.9803, 1e-30, -3.4e38, 2.0**-24], dtype=np.float32)
    hexed = [float(v).hex() for v in values.tolist()]
    back = np.array([float.fromhex(h) for h in hexed], dtype=np.float32)
    assert back.tobytes() == values.tobytes()
