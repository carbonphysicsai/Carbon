"""Motor 1.9 magnet material inputs in the 1.9 reference runner (exam-motor 8545 step 2, names 8872; P1, door-code).

Claims:
0. run_batch.py is not edited: its bytes are bound by the committed decision-study freezes (release g10200), so the
   1.9 runner reuses it unchanged (test_motor_decision_study holds that binding).
1. 1.8 UNCHANGED: a case with neither ``br_t`` nor ``mur_m`` gets run_batch.py's own params and machine.pro bytes.
2. 1.9: a case with both sets the solve's ``br`` and ``mur_m``; the eight Challenge inputs go to the geometry and
   validity checks; nothing else in the params changes.
3. FAIL CLOSED: one of the two alone, or a value no solve can take (not finite, not positive, a bool), refuses, and
   inside run_batch.py's case step that is a case not written.

Every value is a SYNTHETIC fixture; nothing is solved.
"""

from __future__ import annotations

import json

import pytest

from carbon.motor import domain, getdp
from scripts.dev.motor.reference import run_batch
from scripts.dev.motor.reference import run_batch_19 as runner

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
MATERIAL = {"br_t": 1.31, "mur_m": 1.05}


def _pro(params, inputs, area):
    return getdp.pro_text(
        {**params, "coil_area_mm2": area(inputs)}, nonlinear=getdp.BRAUER
    )


# ---------------------------------------------------------------- 1. 1.8 unchanged


def test_a_case_without_material_is_byte_identical():
    view = runner._Domain()
    assert not view.validity(dict(CASE))
    params = runner.case_params(dict(CASE), {})
    own = runner._CASE_PARAMS(CASE, {})
    assert own["br"] == domain.FIXED["br"] and own["mur_m"] == domain.FIXED["mur_m"]
    assert json.dumps(params, indent=1) == json.dumps(own, indent=1)
    assert _pro(params, CASE, view.coil_area_mm2) == _pro(
        own, CASE, domain.coil_area_mm2
    )


# ---------------------------------------------------------------- 2. 1.9


def test_a_case_with_both_sets_the_solve_material():
    case = {**CASE, **MATERIAL}
    view = runner._Domain()
    assert not view.validity(case)
    assert view.coil_area_mm2(case) == domain.coil_area_mm2(CASE)
    params = runner.case_params(case, {})
    own = runner._CASE_PARAMS(CASE, {})
    assert params["br"] == 1.31 and params["mur_m"] == 1.05
    assert list(params) == list(own)
    assert {k: v for k, v in params.items() if k not in ("br", "mur_m")} == {
        k: v for k, v in own.items() if k not in ("br", "mur_m")
    }
    text = _pro(params, case, view.coil_area_mm2)
    assert "1.31" in text and "1.05" in text
    assert text != _pro(own, CASE, domain.coil_area_mm2)


def test_install_points_the_case_step_at_the_1_9_inputs(monkeypatch):
    monkeypatch.setattr(run_batch, "case_params", run_batch.case_params)
    monkeypatch.setattr(run_batch, "domain", run_batch.domain)
    runner.install()
    assert run_batch.case_params is runner.case_params
    assert not run_batch.domain.validity({**CASE, **MATERIAL})
    assert run_batch.domain.FIXED is domain.FIXED


# ---------------------------------------------------------------- 3. fail closed


@pytest.mark.parametrize("extra", [{"br_t": 1.3}, {"mur_m": 1.05}])
def test_one_material_input_alone_refuses(extra):
    with pytest.raises(ValueError, match="both br_t and mur_m or neither"):
        runner.split_material({**CASE, **extra})


@pytest.mark.parametrize("bad", [0.0, -1.2, float("nan"), float("inf"), True, "1.2"])
def test_a_value_no_solve_can_take_refuses(bad):
    with pytest.raises(ValueError, match="finite positive number"):
        runner.split_material({**CASE, "br_t": bad, "mur_m": 1.0})
    # inside run_batch.py's case step a ValueError is a case not written (FAILED_INFRA)
    with pytest.raises(ValueError):
        runner._Domain().validity({**CASE, "br_t": bad, "mur_m": 1.0})
