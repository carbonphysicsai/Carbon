"""F08's dual measurement on the eight accepted references.

DEVELOPMENT only, Validator-reviewed exposed references (RR-PACKS-03). The
registered baseline (KRR, length 2, ridge 1e-4) is rebuilt from public TRAIN
and measured exactly as the producer measures a retained model's predictions.
Every reference is feasible, so D tests ranking only. Negative controls:
worse predictions lower A; a non-finite or out-of-band summary, and a repeat
that is not exactly equal, fail their gates rather than scoring.
"""

from __future__ import annotations

import json

import pytest

from carbon.challenge_kit import physical_pack
from carbon.scoring import f08_dual_measurement as fdm
from carbon.scoring import f08_dual_pack as f08
from carbon.scoring import physical_dual_pack as physical

PLATFORM = {"inference_image_id": "sha256:" + "1" * 64}


@pytest.fixture(scope="module")
def case():
    bank = physical_pack.development_bank(f08.CHALLENGE, f08.VERSION)
    public = physical_pack.public_roles(f08.CHALLENGE, f08.VERSION)
    names = f08.input_names()
    rows = physical.bank_rows(bank, names)
    return {
        "bank": bank,
        "public": public,
        "names": names,
        "rows": rows,
        "definition": f08.definition(bank=bank, train_raw=public["train"]),
        "limits": json.loads(public["important_limit_definition"]),
        "baseline": f08._baseline_outputs(rows, public["train"], names),
    }


def _measure(case, outputs, repeats=None):
    return f08.measure(
        bank_rows=case["rows"],
        outputs=outputs,
        repeats=repeats or [outputs, outputs],
        definition=case["definition"],
        limits=case["limits"],
        objective=None,
        train_raw=case["public"]["train"],
        names=case["names"],
    )


def test_the_registered_baseline_scores_and_picks_a_verified_geometry(case):
    result = _measure(case, case["baseline"])
    assert result["gates"] == {gate: True for gate in fdm.GATES}
    assert result["decision_outcome"] == "VERIFIED_FEASIBLE"
    assert result["pick"] == "pilot-0001"
    assert result["D"] == 1 / (1 + result["regret_mm_per_n"] / 0.01)
    assert 0 < result["A"] < 1
    assert case["definition"]["decision_coverage"] == (
        "RANKING_ONLY_NO_FEASIBILITY_BOUNDARY"
    )


def test_worse_predictions_lower_a(case):
    base = _measure(case, case["baseline"])["A"]
    # Compliances off by 30%; the peak frequencies (band-gated) unchanged.
    frequency = {
        case["definition"]["targets"].index(n)
        for n in case["definition"]["frequency_targets"]
    }
    worse = [
        [v if j in frequency else v * 1.3 for j, v in enumerate(row)]
        for row in case["baseline"]
    ]
    assert _measure(case, worse)["A"] < base


def test_invalid_summaries_and_unequal_repeats_fail_their_gates(case):
    outputs = case["baseline"]
    nan = [list(row) for row in outputs]
    nan[0][1] = float("nan")
    result = _measure(case, nan)
    assert result["gates"]["finite_native_summary"] is False
    assert result["A"] is None and result["pick"] is None
    assert result["decision_outcome"] == "MISSED_OPPORTUNITY"
    out_of_band = [list(row) for row in outputs]
    out_of_band[0][2] = 40.0
    assert _measure(case, out_of_band)["gates"]["finite_native_summary"] is False
    drifted = [list(row) for row in outputs]
    drifted[0][0] = drifted[0][0] * (1 + 1e-15) + 1e-18
    result = _measure(case, outputs, repeats=[outputs, drifted])
    assert result["gates"]["paired_repeat"] is False
    with pytest.raises(fdm.F08MeasurementRefused, match="f08_prediction_roster"):
        _measure(case, outputs[:-1], repeats=[outputs, outputs])


def test_the_common_rule_and_the_packets_variant(case):
    kwargs = {
        "bank": case["bank"],
        "physics": f08.physics_contract(),
        "interface_raw": case["public"]["interface"],
        "train_raw": case["public"]["train"],
        "limits_raw": case["public"]["important_limit_definition"],
        "objective_raw": case["public"]["design_objective"],
        "platform": PLATFORM,
    }
    baseline = _measure(case, case["baseline"])
    default = json.loads(f08.pack_documents(**kwargs)["score_pack"])
    assert default["hard_gates"] == list(fdm.GATES)
    assert default["legs"]["A"]["minimum"] == baseline["A"]
    assert default["legs"]["D"]["minimum"] == baseline["D"]
    variant_documents = f08.pack_documents(rule="baseline_a_no_d_minimum", **kwargs)
    variant = json.loads(variant_documents["score_pack"])
    assert variant["legs"]["A"]["minimum"] == baseline["A"]
    assert variant["legs"]["D"]["minimum"] is None
    assert json.loads(variant_documents["source_registration"])[
        "evaluation_version"
    ] == (f08.EVALUATION_VERSION + "-no-d-minimum")
    definition = json.loads(variant_documents["accuracy_definition"])
    assert definition["paired_repeat_procedure"] == "per_case"
    assert definition["source_script_sha256"] == f08.SOURCE_SCRIPT_SHA256


def test_the_physics_contract_is_enveloped_and_reads_no_pack_role(case):
    physics = f08.physics_contract()
    assert set(physics) == {"version", "definition"}
    assert "limits" not in physics["definition"]
    assert physics["definition"]["targets"] == case["definition"]["targets"]
