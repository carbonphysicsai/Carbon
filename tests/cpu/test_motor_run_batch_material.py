"""Motor 1.9 magnet material inputs in the reference runner (exam-motor 8545 step 2, names 8872; P1, door-code).

Claims:
1. 1.8 UNCHANGED: a case with neither ``br_t`` nor ``mur_m`` solves with ``domain.FIXED``; its params and its
   machine.pro text are the same bytes as before.
2. 1.9: a case with both writes them into the solve's params and machine.pro; the eight Challenge inputs go to the
   geometry and validity checks as before.
3. FAIL CLOSED: one of the two alone, or a value no solve can take (not finite, not positive, a bool), refuses.

Every value is a SYNTHETIC fixture; nothing is solved.
"""

from __future__ import annotations

import json

import pytest

from carbon.motor import domain, getdp
from scripts.dev.motor.reference import run_batch

#: A valid eight-input case (the first public 1.8 TRAIN row's inputs).
CASE = {
    "airgap_mm": 0.8304609206210771,
    "current_angle_deg": 2.997616385604074,
    "current_density_a_mm2": 4.642727533201469,
    "embrace": 0.8749975119563407,
    "magnet_mm": 3.2706798530600745,
    "slot_bottom_mm": 35.37695220162885,
    "slot_open_deg": 3.6523881839106895,
    "tooth_mm": 2.667588807291972,
}


def _pro(inputs, params):
    return getdp.pro_text(
        {**params, "coil_area_mm2": domain.coil_area_mm2(inputs)},
        nonlinear=getdp.BRAUER,
    )


def _old_params(inputs, options):
    """case_params as it was before the material inputs: FIXED br and mur_m."""
    params = run_batch.case_params(inputs, options)
    assert params["br"] == domain.FIXED["br"]
    assert params["mur_m"] == domain.FIXED["mur_m"]
    return params


# ---------------------------------------------------------------- 1. 1.8 unchanged


def test_a_case_without_material_is_byte_identical():
    inputs, material = run_batch.split_material(dict(CASE))
    assert inputs == CASE and material == {}
    assert not domain.validity(inputs)
    params = run_batch.case_params(inputs, {}, material)
    old = _old_params(CASE, {})
    assert json.dumps(params, indent=1) == json.dumps(old, indent=1)
    assert _pro(inputs, params) == _pro(CASE, old)


# ---------------------------------------------------------------- 2. 1.9


def test_a_case_with_both_sets_the_solve_material():
    inputs, material = run_batch.split_material({**CASE, "br_t": 1.31, "mur_m": 1.05})
    assert inputs == CASE
    assert material == {"br": 1.31, "mur_m": 1.05}
    assert not domain.validity(inputs)
    params = run_batch.case_params(inputs, {}, material)
    assert params["br"] == 1.31 and params["mur_m"] == 1.05
    old = _old_params(CASE, {})
    assert {k: v for k, v in params.items() if k not in ("br", "mur_m")} == {
        k: v for k, v in old.items() if k not in ("br", "mur_m")
    }
    text = _pro(inputs, params)
    assert "1.31" in text and "1.05" in text
    assert text != _pro(CASE, old)


# ---------------------------------------------------------------- 3. fail closed


@pytest.mark.parametrize("extra", [{"br_t": 1.3}, {"mur_m": 1.05}])
def test_one_material_input_alone_refuses(extra):
    with pytest.raises(ValueError, match="both br_t and mur_m or neither"):
        run_batch.split_material({**CASE, **extra})


@pytest.mark.parametrize("bad", [0.0, -1.2, float("nan"), float("inf"), True, "1.2"])
def test_a_value_no_solve_can_take_refuses(bad):
    with pytest.raises(ValueError, match="finite positive number"):
        run_batch.split_material({**CASE, "br_t": bad, "mur_m": 1.0})
