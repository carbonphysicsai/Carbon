"""Cooling's dual measurement reproduces the counted-dual packet's readout.

The operator packet (OPTIMIZER_COUNTED_DUAL_PACKETS_20261018, ``cooling``)
recorded, on the 48 counted CFD cells (RESEARCH_SCORELAB_MOTOR_COOLING_ACTUAL_
SHARED_CORE_READOUT_20261018): learned-krr-v1 A 0.827582826340918, D 1, pick
d03; analytic-v1 A 0.844420842483987, D 1; nearest-neighbour-v1
A 0.5624469259870758, D 0, infeasible pick d08. The port, regenerated from
committed sources and reading predictions as the producer does, must give the
same values; the packet's leg-minimum rule then sets the baseline's legs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from carbon.challenge_kit import physical_pack, physical_public_train
from carbon.cold_plate import analytic, exam
from carbon.cold_plate import decision_study as ds
from carbon.cold_plate import track_b as route
from carbon.scoring import cooling_dual_measurement as cdm
from carbon.scoring import cooling_dual_pack as cooling
from carbon.scoring import physical_dual_pack as physical

ROOT = Path(__file__).resolve().parents[2]
KRR = {"A": 0.827582826340918, "D": 1.0, "pick": "d03"}
ANALYTIC_A = 0.844420842483987
NEAREST = {"A": 0.5624469259870758, "D": 0.0, "pick": "d08"}


@pytest.fixture(scope="module")
def case():
    bank = physical_pack.development_bank(cooling.CHALLENGE, cooling.VERSION)
    public = physical_pack.public_roles(cooling.CHALLENGE, cooling.VERSION)
    names = physical_public_train.numeric_interface_document(cooling.CHALLENGE)[
        "input_names"
    ]
    definition = {
        **cooling.definition(bank=bank, train_raw=public["train"]),
        "producer_digest": cooling.producer_digest(),
    }
    return {
        "bank": bank,
        "public": public,
        "names": names,
        "rows": physical.bank_rows(bank, names),
        "definition": definition,
        "limits": json.loads(public["important_limit_definition"]),
        "objective": json.loads(public["design_objective"]),
    }


def _flat(outputs):
    return [outputs["peak_c"], *outputs["profile_c"], outputs["pressure_drop_pa"]]


def _measure(case, outputs, repeats=None):
    return cooling.measure(
        bank_rows=case["rows"],
        outputs=outputs,
        repeats=repeats or [outputs, outputs],
        definition=case["definition"],
        limits=case["limits"],
        objective=case["objective"],
        train_raw=case["public"]["train"],
        names=case["names"],
    )


def _baseline(case):
    train = cooling._train_records(case["public"]["train"], case["names"])
    return cooling._baseline_outputs(case["rows"], train)


def test_the_pack_sources_are_the_packets_own(case):
    config = route.load_config(ROOT)
    assert case["objective"]["decision_contract"] == ds.decision_contract(config)
    # The pack TRAIN is the packet's TRAIN: identical native normalisation.
    train = cooling._train_records(case["public"]["train"], case["names"])
    assert exam.scales_from_train(train) == exam.scales_from_train(
        route._train(config, ROOT)
    )
    cdm.validate_definition(case["definition"])


def test_the_rebuilt_baseline_reproduces_the_packets_legs(case):
    result = _measure(case, _baseline(case))
    assert result["gates"] == {
        "native_cold_plate": True,
        "complete48_common_mask": True,
        "selected_design_verified_feasible": True,
    }
    assert result["A"] == pytest.approx(KRR["A"], rel=0, abs=1e-12)
    assert result["D"] == KRR["D"]
    assert result["pick"] == KRR["pick"]
    assert result["decision_outcome"] == "VERIFIED_FEASIBLE"


def test_the_analytic_and_nearest_neighbour_controls_reproduce(case):
    analytic_outputs = [
        _flat({k: v for k, v in analytic.predict(row["inputs"]).items()})
        for row in case["rows"]
    ]
    result = _measure(case, analytic_outputs)
    assert result["A"] == pytest.approx(ANALYTIC_A, rel=0, abs=1e-12)
    assert result["D"] == 1.0
    nearest = route._nearest_neighbour(route._train(route.load_config(ROOT), ROOT))
    batch = {row["case_id"]: row["inputs"] for row in case["rows"]}
    predicted = nearest(batch)
    result = _measure(case, [_flat(predicted[row["case_id"]]) for row in case["rows"]])
    assert result["A"] == pytest.approx(NEAREST["A"], rel=0, abs=1e-12)
    assert result["D"] == NEAREST["D"]
    assert result["pick"] == NEAREST["pick"]
    assert result["gates"]["selected_design_verified_feasible"] is False
    assert result["decision_outcome"] == "MISSED_OPPORTUNITY"


def test_the_packets_minimum_rule_sets_the_baselines_legs(case):
    documents = cooling.pack_documents(
        bank=case["bank"],
        physics=cooling.physics_contract(),
        interface_raw=case["public"]["interface"],
        train_raw=case["public"]["train"],
        limits_raw=case["public"]["important_limit_definition"],
        objective_raw=case["public"]["design_objective"],
    )
    pack = json.loads(documents["score_pack"])
    assert pack["hard_gates"] == list(cdm.GATES)
    assert pack["legs"]["A"]["minimum"] == pytest.approx(KRR["A"], rel=0, abs=1e-12)
    assert pack["legs"]["D"]["minimum"] == KRR["D"]
    definition = json.loads(documents["accuracy_definition"])
    assert definition["source_script_sha256"] == cooling.SOURCE_SCRIPT_SHA256
    assert definition["scale_status"] == "PROSPECTIVE_EXPERIMENT_NOT_ADOPTED"


def test_a_repeat_beyond_the_native_rule_or_an_invalid_row_is_typed(case):
    outputs = _baseline(case)
    drifted = [list(v) for v in outputs]
    drifted[0][0] += 1e-3
    result = _measure(case, outputs, repeats=[outputs, drifted])
    assert result["gates"]["native_cold_plate"] is False
    assert result["gate_failed_cases"] == [case["rows"][0]["case_id"]]
    broken = [list(v) for v in outputs]
    broken[5] = [float("nan")] * 32
    result = _measure(case, broken)
    assert result["A"] is None
    assert result["gates"]["native_cold_plate"] is False
    with pytest.raises(
        cdm.CoolingMeasurementRefused, match="cooling_prediction_roster"
    ):
        _measure(case, outputs[:-1], repeats=[outputs, outputs])
