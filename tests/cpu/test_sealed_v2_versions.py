"""Every sealed v2 grade records its v2 evaluation version, and the hidden-family
exam rule cites the same string (the KOTH pack-set key depends on it; Validator
condition on receipt 615327e56)."""

from __future__ import annotations

import pytest

from carbon.challenge_validator import cooling_hidden, f02_hidden, f08_hidden
from carbon.challenge_validator import motor_sealed
from carbon.scoring import cooling_dual_pack as cooling
from carbon.scoring import f02_sealed_dual_pack as f02
from carbon.scoring import f08_sealed_dual_pack as f08
from carbon.scoring import motor_sealed_dual_pack as motor
from carbon.scoring import physical_dual_pack as physical

V2 = {
    "motor": "motor-dual-sealed-batch-30-v2",
    "cooling": "cooling-dual-sealed-batch-16-v2",
    "f08": "f08-dual-sealed-grid-8x1-v2",
    "f02": "f02-dual-sealed-grid-8x1-v2",
}
PLATFORM = {"inference_image_id": "sha256:" + "1" * 64}


def _hidden_rule_version(module):
    return module.hidden_rule()["exam"]["evaluation_version"]


@pytest.mark.parametrize(
    "name,module",
    [
        ("motor", motor_sealed),
        ("cooling", cooling_hidden),
        ("f08", f08_hidden),
        ("f02", f02_hidden),
    ],
)
def test_the_hidden_rule_cites_the_v2_version(name, module):
    assert _hidden_rule_version(module) == module.EVALUATION_VERSION == V2[name]


def _adapters():
    return {
        "motor": [motor.adapter(v) for v in ("1.1", "1.2", "1.3")],
        "cooling": [cooling.sealed_adapter(v) for v in ("1.1", "1.2", "1.3")],
        "f08": [f08.adapter(v) for v in ("1.2", "1.3", "1.4")],
        "f02": [f02.adapter(v) for v in ("2.1", "2.2", "2.3")],
    }


@pytest.mark.parametrize("name", sorted(V2))
def test_each_sealed_grade_records_the_v2_string(name):
    for chosen in _adapters()[name]:
        assert chosen is not None and chosen.EVALUATION_VERSION == V2[name]
        # What a pack and so every grade carries: plain, calibration and judge.
        assert physical._evaluation_version(chosen, PLATFORM, None) == V2[name]
        assert physical._evaluation_version(chosen, PLATFORM, "calibration").startswith(
            V2[name] + "-calibration-"
        )
        assert physical._evaluation_version(chosen, PLATFORM, {}).startswith(
            V2[name] + "-judge-"
        )
