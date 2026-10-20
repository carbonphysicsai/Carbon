"""Battery's dual-pack adapter: the registered packet's values, measured by the
pinned battery value functions, and fail closed while D and B15 are HUMAN_INPUT."""

import copy
import functools
import gzip
import json
from pathlib import Path

import pytest

from carbon.challenge_kit import physical_pack
from carbon.scoring import battery_dual_measurement as bdm
from carbon.scoring import battery_dual_pack as adapter
from carbon.scoring import cooling_dual_pack, dual_score, motor_dual_pack
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import private_evaluation_source as source

REPOSITORY = Path(__file__).resolve().parents[2]
DECISION_REFERENCES = (
    REPOSITORY / "docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz"
)


@functools.cache
def _bank():
    return physical_pack.development_bank(adapter.CHALLENGE, adapter.VERSION)


def _rows():
    return physical.bank_rows(_bank(), adapter.input_names())


def _definition():
    return adapter.definition(bank=_bank(), train_raw=b"")


def _truth():
    return [list(map(float, row)) for row in _bank()["references"]]


def _practice(outputs, repeats=None, definition=None):
    return bdm.practice_measures(
        bank=_rows(),
        outputs=outputs,
        repeats=[outputs, outputs] if repeats is None else repeats,
        definition=definition or _definition(),
        contract=adapter._contract(),
    )


def test_the_definition_is_the_registered_packet():
    definition = _definition()
    bdm.validate_definition(definition)
    assert definition["registry"]["candidate"] == "G-FEAS/A-Q>"
    assert definition["g_feas"] == {
        "measure": "feasibility",
        "cutoff": 0.05,
        "comparison": "exceeds",
    }
    assert definition["paired_repeat"] == {"procedure": "per_case", "floor": 0}
    # The 17 PRACTICE cases without a v2 plating truth: counted, never rated.
    mask = definition["unresolved_mask"]
    assert mask["reason"] == "plating_reference_unresolved"
    assert len(mask["case_ids"]) == 17
    labels = {r["case_id"]: r["plating_label_v2"] for r in _bank()["reference_records"]}
    assert all(labels[c]["rule"] == "pending-m160-r1" for c in mask["case_ids"])
    # HUMAN_INPUT until the Battery v2 material asks for their rows.
    assert definition["decision_scenarios"] is None
    assert definition["b15_probe_plan"] is None


def test_the_applied_pack_registers_as_an_arithmetic_half_and_half():
    pack = dual_score.register_pack(
        {
            **adapter.applied_pack(),
            "physics_contract_digest": "sha256:" + "0" * 64,
            "measurement_contract_digest": "sha256:" + "1" * 64,
        }
    )
    assert pack["combination"] == "weighted_arithmetic_mean"
    assert pack["value_weight"] == 0.5
    assert pack["hard_gates"] == list(bdm.GATES)
    assert pack["decision_policy"]["VERIFIED_FEASIBLE"] == {
        "eligible": True,
        "maximum_D": 1.0,
    }
    assert all(leg["minimum"] is None for leg in pack["legs"].values())


def test_battery_dispatches_and_the_dispatch_table_is_in_no_producer_digest():
    # Selecting an adapter measures nothing: registering a Challenge must not
    # re-version (and unbind the calibration packs of) any other producer.
    assert source._physical_adapter(adapter.CHALLENGE, adapter.VERSION) is adapter
    assert "physical_adapters.py" not in physical._SHARED_FILES
    for module in (adapter, motor_dual_pack, cooling_dual_pack):
        assert "physical_adapters.py" not in module.FILES


def test_a_model_equal_to_the_reference_passes_every_practice_gate():
    measured = _practice(_truth())
    assert measured["A"] == 1.0
    assert measured["gates"] == {
        "exam_gates": True,
        "g_feas": True,
        "paired_repeat": True,
    }
    assert measured["false_feasible_rate"] == 0.0
    assert len(measured["unresolved_mask"]["case_ids"]) == 17


def test_an_optimistic_plating_model_fails_g_feas_on_v2_truth():
    # Calling every case plating-safe accepts the cases v2 says plate.
    width = len(_truth()[0])
    plating = (width - 4) - 1  # flat order: 121 V, 121 T, 1 plating, 4 capacity
    optimistic = [row[:plating] + [1.0] + row[plating + 1 :] for row in _truth()]
    measured = _practice(optimistic)
    assert measured["false_feasible_rate"] > 0.05
    assert measured["gates"]["g_feas"] is False
    assert measured["A"] < 1.0


def test_a_repeat_that_differs_at_all_fails_the_paired_repeat():
    truth = _truth()
    moved = copy.deepcopy(truth)
    moved[3][0] = moved[3][0] + 1e-12
    assert _practice(truth, repeats=[truth, moved])["gates"]["paired_repeat"] is False


def test_an_unresolved_case_is_never_rated():
    # A wildly wrong prediction on the unresolved cases alone changes nothing.
    definition = _definition()
    masked = set(definition["unresolved_mask"]["case_ids"])
    wrong = [
        [v + 50.0 for v in row] if case in masked else row
        for case, row in zip(_bank()["case_ids"], _truth(), strict=True)
    ]
    assert _practice(wrong) == _practice(_truth())


def test_a_definition_whose_mask_differs_refuses():
    definition = _definition()
    definition["unresolved_mask"] = {
        **definition["unresolved_mask"],
        "case_ids": definition["unresolved_mask"]["case_ids"][1:],
    }
    with pytest.raises(bdm.BatteryMeasurementRefused) as refused:
        _practice(_truth(), definition=definition)
    assert refused.value.code == "battery_unresolved_mask"


def test_battery_stays_unscored_while_d_and_b15_are_human_input():
    with pytest.raises(bdm.BatteryMeasurementRefused) as refused:
        adapter.measure(
            bank_rows=_rows(),
            outputs=_truth(),
            repeats=[_truth(), _truth()],
            definition=_definition(),
            limits={},
            objective={},
            train_raw=b"",
            names=adapter.input_names(),
        )
    assert refused.value.code == "battery_d_unregistered"
    with pytest.raises(bdm.BatteryMeasurementRefused) as refused:
        adapter.baseline_outputs([])
    assert refused.value.code == "battery_baseline_unregistered"


def test_a_changed_registry_refuses(monkeypatch):
    monkeypatch.setattr(bdm, "REGISTRY", (bdm.REGISTRY[0], "sha256:" + "0" * 64))
    with pytest.raises(bdm.BatteryMeasurementRefused) as refused:
        bdm.registry_gate()
    assert refused.value.code == "registry"


@functools.cache
def _ev4():
    lines = gzip.decompress(DECISION_REFERENCES.read_bytes()).decode().splitlines()
    records = [json.loads(line) for line in lines]
    contract = adapter._contract()
    scenarios = contract["scenarios"]["development"]
    ok = {r["case_id"]: r for r in records if r["status"] == "OK"}
    return contract, scenarios, ok, records


def test_d_is_the_quiz_regret_over_ev4_development_under_v2_truth():
    contract, scenarios, refs, records = _ev4()
    assert len(scenarios) == 12
    # A model that predicts every grid reference exactly; the five twice-failed
    # references keep a prediction (the model is asked) but no truth.
    neighbour = next(iter(refs.values()))["outputs"]
    predictions = {
        r["case_id"]: (r["outputs"] if r["status"] == "OK" else neighbour)
        for r in records
        if r["case_id"].startswith("ev4:D-")
    }
    q, measures = bdm.decision_value(contract, scenarios, predictions, refs)
    assert 0 < q <= 1
    assert 0 < measures["scenarios"] <= 12
    assert measures["regret"] == pytest.approx(1 / q - 1)
    assert measures["unresolved"] is not None
    # An all-infeasible scenario is excluded (quiz.q3_feasible's rule).
    feasible = [
        e
        for e in scenarios
        if bdm.decision_value(contract, [e], predictions, refs)[1]["scenarios"] == 1
    ]
    assert len(feasible) == measures["scenarios"] < 12
    # Missing any grid answer is the model's own missed opportunity.
    first = feasible[0]
    dropped = dict(predictions)
    dropped.pop(next(k for k in dropped if k.startswith("ev4:" + first["id"] + ":")))
    worse, _ = bdm.decision_value(contract, [first], dropped, refs)
    assert worse == 1 / (1 + contract["mistake_costs"]["missed_opportunity"])
