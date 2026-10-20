"""KOTH's one registered source: rebuild noise per Challenge, and the comparator."""

import json

import pytest

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import koth_registry as kr
from carbon.challenge_validator.interface import digest
from carbon.scoring.physical_dual_pack import BASELINE_ROLE

RECORD = digest("rebuild noise record")


def _write(tmp_path, challenges):
    path = tmp_path / "noise.json"
    path.write_bytes(
        json.dumps({"schema": kr.SCHEMA, "challenges": challenges}).encode()
    )
    return path


def test_the_committed_registry_registers_no_noise_yet():
    # Nothing is registered until a measurement record is reviewed; every
    # takeover is UNAVAILABLE and the ladder steps at eta.
    assert kr._load() == {}
    assert kr.rebuild_noise("electric-motor-magnetics") is None


def test_a_registered_noise_is_returned_and_others_are_none(tmp_path):
    path = _write(
        tmp_path,
        {"electric-motor-magnetics": {"value": 0.05, "measurement_digest": RECORD}},
    )
    assert kr.rebuild_noise("electric-motor-magnetics", path=path) == {
        "value": 0.05,
        "measurement_digest": RECORD,
    }
    assert kr.rebuild_noise("f02", path=path) is None


@pytest.mark.parametrize(
    "noise",
    [
        {"value": 0, "measurement_digest": RECORD},
        {"value": -0.1, "measurement_digest": RECORD},
        {"value": float("inf"), "measurement_digest": RECORD},
        {"value": 0.1, "measurement_digest": "not a digest"},
        {"value": 0.1},
        {"value": 0.1, "measurement_digest": RECORD, "host_classes": []},
    ],
)
def test_a_malformed_or_zero_noise_refuses(tmp_path, noise):
    path = _write(tmp_path, {"f02": noise})
    with pytest.raises(kr.RegistryInvalid):
        kr.rebuild_noise("f02", path=path)


def _pack(minimum_a, minimum_d, combination="weighted_arithmetic_mean", weight=0.5):
    leg = {"components": [], "minimum": None}
    return {
        "pack_digest": digest("score pack"),
        "legs": {"A": {**leg, "minimum": minimum_a}, "D": {**leg, "minimum": minimum_d}},
        "value_weight": weight,
        "combination": combination,
    }


def test_the_comparator_is_the_one_bank_promotion_accepts(tmp_path):
    path = _write(
        tmp_path,
        {"electric-motor-magnetics": {"value": 0.05, "measurement_digest": RECORD}},
    )
    source = digest("baseline run that set the leg minimums")
    rule = kr.comparator(
        "electric-motor-magnetics",
        _pack(0.4, 0.8),
        {"leg_minimum_source": {"role": BASELINE_ROLE, "entry_id": source}},
        path=path,
    )
    assert rule["schema"] == bp.COMPARATOR_SCHEMA
    assert rule["rebuild_noise"]["value"] == 0.05
    assert rule["minimum_source_entry_ids"] == [source]
    assert rule["ties"] == "incumbent_keeps"
    assert rule["baseline_total"] == pytest.approx(0.6)


def test_an_id_that_is_not_a_registered_challenge_refuses(tmp_path):
    # Otherwise the value would sit in the file and nothing would read it.
    path = _write(
        tmp_path,
        {"electric-motor-magnetic": {"value": 0.05, "measurement_digest": RECORD}},
    )
    with pytest.raises(kr.RegistryInvalid):
        kr.rebuild_noise("electric-motor-magnetics", path=path)


@pytest.mark.parametrize(
    ("pack", "expected"),
    [
        (_pack(0.4, 0.8), 0.6),
        (_pack(0.4, 0.8, weight=0.25), 0.5),
        (_pack(None, 0.8), None),
        (_pack(0.4, None), None),
        (_pack(0.25, 1.0, "bottleneck_capped_geometric"), 0.125),
        (_pack(0.0, 1.0, "bottleneck_capped_geometric"), 0.0),
    ],
)
def test_the_baseline_total_is_the_packs_own_total_at_its_leg_minimums(pack, expected):
    """OWNER-FIRST-CROWN-BEATS-BASELINE-01: the same combination dual_score uses."""
    if expected is None:
        assert kr.baseline_total(pack) is None
    else:
        assert kr.baseline_total(pack) == pytest.approx(expected)
