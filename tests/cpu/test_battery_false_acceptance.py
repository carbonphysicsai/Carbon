"""The near-limit false-acceptance measurement (OWNER-EXEC-APPROVALS-01).

The claims tested: it counts only cases the reference resolves (a value inside
the contract's band is not counted); the model's verdict is read without
bands, as the selector reads it; the localized figure is the worst
constraint's rate, so an error in one band is not averaged away; a missing
prediction is unmeasured, never clean; it sets no cutoff; and the retained
control evidence is what the code computes, with the localized sign-error
control caught where the mean optimism gate is not.
"""

import json
from pathlib import Path

from carbon.battery.value import false_acceptance as fa

REPO = Path(__file__).resolve().parents[2]
EVIDENCE = REPO / "docs/development/evidence/near-false-acceptance-2026-10-03"


def _contract():
    return json.loads((REPO / fa.CONTRACT).read_text())


def _outputs(margin, peak=30.0):
    return {
        "voltage_v": [3.5] * 121,
        "temperature_c": [25.0] * 120 + [peak],
        "plating_margin_v": margin,
        "capacity_ah": [4.9] * 4,
    }


def _refs(**cases):
    return {k: {"outputs": v} for k, v in cases.items()}


def test_a_resolved_failure_called_pass_is_a_false_acceptance():
    contract = _contract()
    band = contract["reference"]["uncertainty"]["bands"]["plating_margin_v"]
    refs = _refs(
        flipped=_outputs(-2 * band),
        caught=_outputs(-2 * band),
        unresolved=_outputs(-0.5 * band),
    )
    predictions = {
        "flipped": _outputs(+2 * band),
        "caught": _outputs(-2 * band),
        "unresolved": _outputs(+2 * band),
    }
    out = fa.component(contract, predictions, list(refs), refs)
    plating = out["constraints"]["no_plating_onset"]
    # The case inside the band is UNRESOLVED and not counted.
    assert plating["reference_fail"] == 2
    assert plating["false_acceptance"] == 1
    assert plating["false_acceptance_rate"] == 0.5


def test_the_worst_constraint_is_reported_not_the_mean():
    contract = _contract()
    refs = _refs(a=_outputs(-0.01, peak=50.0), b=_outputs(-0.01, peak=50.0))
    # Plating always waved through; temperature always caught.
    predictions = {"a": _outputs(+0.01, peak=50.0), "b": _outputs(+0.01, peak=50.0)}
    out = fa.component(contract, predictions, list(refs), refs)
    assert out["constraints"]["peak_temperature"]["false_acceptance_rate"] == 0.0
    assert out["worst_constraint"] == "no_plating_onset"
    assert out["worst_false_acceptance_rate"] == 1.0


def test_a_missing_prediction_is_unmeasured_and_no_failures_is_no_rate():
    contract = _contract()
    refs = _refs(a=_outputs(0.01), b=_outputs(0.01))
    assert fa.component(contract, {"a": _outputs(0.01)}, ["a", "b"], refs) is None
    clean = fa.component(contract, {"a": _outputs(0.01)}, ["a"], refs)
    assert clean["worst_false_acceptance_rate"] is None
    assert clean["worst_constraint"] is None


def test_the_retained_control_evidence_is_what_the_code_computes():
    retained = json.loads((EVIDENCE / "controls.json").read_text())
    assert retained == json.loads(json.dumps(fa.controls(REPO)))
    assert retained["cutoff"] is None and retained["state"] == "DESCRIPTIVE"


def test_it_catches_the_sign_error_the_mean_optimism_gate_misses():
    retained = json.loads((EVIDENCE / "controls.json").read_text())["controls"]
    rate = {k: v["worst_false_acceptance_rate"] for k, v in retained.items()}
    assert rate["control-oracle"] == 0.0
    assert rate["control-conservative"] == 0.0
    assert rate["control-rank_preserving_delay"] == 0.0
    assert rate["control-boundary_optimist"] == 1.0
    assert rate["control-localized_sign_error"] > 0.9
    assert retained["control-localized_sign_error"]["worst_constraint"] == (
        "no_plating_onset"
    )
    # The mean optimism measure puts the same control below every real member.
    optimism = json.loads(
        (
            REPO
            / "docs/development/evidence/admissibility-optimism-2026-10-03/optimism.json"
        ).read_text()
    )["datasets"]["ev4-2026-10-01"]
    sign_error = optimism["controls"]["control-localized_sign_error"]
    assert sign_error < optimism["real_min"]
