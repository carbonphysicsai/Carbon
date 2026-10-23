"""F08 grades a sealed exam batch as one design x condition grid (evaluation version
``f08-dual-sealed-grid-8x1-v2``): the registered dual measurement, unchanged, on a complete 8 x 1 grid in the one
sealed cohort, with 0.5 A + 0.5 D, no leg minimum carried, and the producer identity covering the shared grouping.
"""

from __future__ import annotations

import copy
import json

import pytest
from test_f08_sealed_pack import batch

from carbon.challenge_kit import f08_sealed_pack as pack
from carbon.challenge_kit import physical_pack
from carbon.scoring import f08_dual_measurement as fdm
from carbon.scoring import f08_dual_pack as dev
from carbon.scoring import f08_sealed_dual_pack as sealed
from carbon.scoring import physical_dual_pack as physical

PLATFORM = {"inference_image_id": "sha256:" + "1" * 64}


@pytest.fixture(scope="module")
def case():
    document, records = batch()
    bank = pack.sealed_bank(document, records)
    public = physical_pack.public_roles(sealed.CHALLENGE, sealed.VERSION)
    names = sealed.input_names()
    return {
        "bank": bank,
        "public": public,
        "names": names,
        "rows": physical.bank_rows(bank, names),
        "definition": sealed.definition(bank=bank, train_raw=public["train"]),
        "limits": json.loads(public["important_limit_definition"]),
        "truth": [[float(v) for v in row] for row in bank["references"]],
    }


def _measure(case, outputs, *, rows=None, definition=None, module=sealed):
    return module.measure(
        bank_rows=rows or case["rows"],
        outputs=outputs,
        repeats=[outputs, outputs],
        definition=definition or case["definition"],
        limits=case["limits"],
        objective=None,
        train_raw=case["public"]["train"],
        names=case["names"],
    )


def test_the_definition_registers_the_grid_and_the_batchs_own_receipt(case):
    definition = case["definition"]
    sealed.validate_definition(definition)
    assert definition["cohort_counts"] == {sealed.COHORT: 8}
    assert definition["grid"] == {"designs": 8, "conditions": 1}
    assert definition["reference_receipt_sha256"] == physical.sha(
        case["bank"]["solver_evidence"]
    )
    assert sealed.EVALUATION_VERSION == "f08-dual-sealed-grid-8x1-v2"
    assert sealed.COHORT == "decision_sealed_grid"
    assert case["bank"]["cohorts"] == (sealed.COHORT,) * 8
    assert {r["condition_id"] for r in case["bank"]["reference_records"]} == {
        "condition-0"
    }


def test_a_model_equal_to_the_references_earns_full_a_and_d(case):
    result = _measure(case, case["truth"])
    assert result["A"] == 1.0 and result["D"] == 1.0
    assert (
        all(result["gates"].values())
        and result["decision_outcome"] == "VERIFIED_FEASIBLE"
    )


def test_a_worse_model_lowers_a_and_all_values_are_finite(case):
    worse = [[v * 1.05 for v in row] for row in case["truth"]]
    result = _measure(case, worse)
    for leg in ("A", "D"):
        assert result[leg] is not None and 0 <= result[leg] <= 1
    assert result["A"] < 1.0


def test_the_grid_measure_equals_the_development_measure_on_a_dev_shaped_bank(case):
    """The sealed grader adds the grid check only: on the same cells under the development cohort the registered
    measurement gives the same A, D, gates and pick."""
    outputs = [[v * 1.02 for v in row] for row in case["truth"]]
    sealed_result = _measure(case, outputs)
    dev_rows = [{**row, "cohort": "decision_near_limit"} for row in case["rows"]]
    dev_definition = dev.definition(
        bank=case["bank"], train_raw=case["public"]["train"], version="1.2"
    )
    dev_result = _measure(
        case, outputs, rows=dev_rows, definition=dev_definition, module=dev
    )
    # D = min(V, C): the sealed grid adds the critical-prediction credit to the
    # development measure's verified value; everything else is the same.
    assert sealed_result["design_fidelity"]["C"] is not None
    assert sealed_result["D"] == min(
        dev_result["D"], sealed_result["design_fidelity"]["C"]
    )
    ignored = ("D", "design_fidelity")
    assert {k: v for k, v in sealed_result.items() if k not in ignored} == {
        k: v for k, v in dev_result.items() if k not in ignored
    }


def test_a_bank_that_is_not_the_sealed_grid_refuses(case):
    truth = case["truth"]
    wrong_cohort = [{**row, "cohort": "decision_near_limit"} for row in case["rows"]]
    with pytest.raises(fdm.F08MeasurementRefused) as refused:
        _measure(case, truth, rows=wrong_cohort)
    assert refused.value.code == "f08_bank_cohort"
    twice = copy.deepcopy(case["rows"])
    twice[1]["record"][
        "condition_id"
    ] = "condition-1"  # 8 designs x 2 conditions is not the registered shape
    with pytest.raises(fdm.F08MeasurementRefused) as refused:
        _measure(case, truth, rows=twice)
    assert refused.value.code == "f08_sealed_grid"
    repeated = copy.deepcopy(case["rows"])
    repeated[1]["record"]["design_id"] = repeated[0]["record"]["design_id"]
    with pytest.raises(fdm.F08MeasurementRefused):
        _measure(case, truth, rows=repeated)
    short = case["rows"][:7]
    with pytest.raises(fdm.F08MeasurementRefused):
        _measure(case, truth[:7], rows=short)


def test_a_malformed_sealed_definition_refuses(case):
    for key, value in (
        ("cohort_counts", {"decision_near_limit": 8}),
        ("grid", {"designs": 4, "conditions": 2}),
        ("reference_receipt_sha256", "not-a-digest"),
    ):
        bad = {**case["definition"], key: value}
        with pytest.raises(fdm.F08MeasurementRefused):
            sealed.validate_definition(bad)


def test_the_development_producer_is_untouched_and_dispatch_is_by_population(case):
    assert "f08_sealed_dual_pack.py" not in dev.FILES
    assert sealed.producer_digest() != dev.producer_digest()
    assert sealed.adapter("1.2") is sealed._ADAPTER
    assert sealed.adapter("1.3").EVALUATION_VERSION == sealed.EVALUATION_VERSION
    assert sealed.adapter("1.3").VERSION == "1.3" and sealed.adapter("9.9") is None
    assert sealed.adapter_for_bank(case["bank"], "1.2") is sealed._ADAPTER
    development = physical_pack.development_bank(dev.CHALLENGE, "1.2")
    chosen = sealed.adapter_for_bank(development, "1.2")
    assert chosen.EVALUATION_VERSION != sealed.EVALUATION_VERSION
    with pytest.raises(fdm.F08MeasurementRefused):
        sealed.adapter_for_bank({"cohorts": ("practice",) * 8}, "1.2")
    assert sealed.is_sealed_bank(case["bank"]) and not sealed.is_sealed_bank(
        development
    )


def _tree(root):
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_two_copies_of_the_receiver_pack_are_byte_identical(case, tmp_path):
    first = tmp_path / "a"
    second = tmp_path / "b"
    one = sealed.write_sealed_pack(first, case["bank"], version="1.3", **PLATFORM)
    two = sealed.write_sealed_pack(second, case["bank"], version="1.3", **PLATFORM)
    assert one.name == two.name == "evaluation-pack.json"
    assert _tree(first) == _tree(second)
    manifest = json.loads(one.read_bytes())
    assert manifest["pack_version"].endswith(sealed.PACK_SUFFIX)
    score_pack = json.loads(
        (first / manifest["private"]["score_pack"]["path"]).read_bytes()
    )
    assert all(leg["minimum"] is None for leg in score_pack["legs"].values())
    accuracy = json.loads(
        (first / manifest["public"]["accuracy_definition"]["path"]).read_bytes()
    )
    assert accuracy["producer_digest"] == sealed.producer_digest()
    assert accuracy["bank_digest"] == physical.bank_digest(case["bank"])
    with pytest.raises(ValueError):
        sealed.write_sealed_pack(first, case["bank"], version="1.3")  # a non-empty root
    with pytest.raises(fdm.F08MeasurementRefused):
        sealed.write_sealed_pack(
            tmp_path / "c",
            physical_pack.development_bank(dev.CHALLENGE, "1.2"),
            version="1.2",
        )


def test_the_definition_registers_the_critical_block(case):
    block = case["definition"]["critical"]
    assert block["rule"] == "D=min(V,C)"
    scales = {c["id"]: c["scale"] for c in block["components"]}
    assert scales["static_margin"] == 0.003
    assert [v for k, v in scales.items() if k.startswith("dynamic_margin_")] == [
        0.015
    ] * 3
    assert [v for k, v in scales.items() if k.startswith("resonance_")] == [10.0] * 3
    assert block["objective"]["scale"] == case["definition"]["D_scale_mm_per_n"]


def _shift_frequency(case, geometry):
    """A truth copy with one geometry first resonance moved 30 Hz, in band."""
    outputs = copy.deepcopy(case["truth"])
    j = case["definition"]["targets"].index(case["definition"]["frequency_targets"][0])
    low, high = case["definition"]["frequency_band_hz"]
    value = outputs[geometry][j]
    outputs[geometry][j] = value + 30.0 if value + 30.0 <= high else value - 30.0
    return outputs


def test_a_right_pick_with_wrong_resonance_scores_d_below_one(case):
    exact = _measure(case, case["truth"])
    assert exact["D"] == 1.0 and exact["design_fidelity"]["C"] == 1.0
    ids = [row["case_id"] for row in case["rows"]]
    other = next(i for i, cid in enumerate(ids) if cid != exact["pick"])
    skewed = _measure(case, _shift_frequency(case, other))
    # The pick, the gates and the verified value are all unchanged.
    assert skewed["pick"] == exact["pick"] and skewed["regret_mm_per_n"] == 0.0
    assert all(skewed["gates"].values())
    assert skewed["design_fidelity"]["C"] < 1.0
    assert skewed["D"] == skewed["design_fidelity"]["C"] < 1.0


def test_wrong_margins_on_the_selected_geometry_also_cap_d(case):
    exact = _measure(case, case["truth"])
    ids = [row["case_id"] for row in case["rows"]]
    chosen = ids.index(exact["pick"])
    skewed = _measure(case, _shift_frequency(case, chosen))
    assert skewed["pick"] == exact["pick"] and skewed["D"] < 1.0


def test_a_definition_without_the_critical_block_grades_value_only(case):
    legacy = {k: v for k, v in case["definition"].items() if k != "critical"}
    ids = [row["case_id"] for row in case["rows"]]
    exact = _measure(case, case["truth"])
    other = next(i for i, cid in enumerate(ids) if cid != exact["pick"])
    skewed = _measure(case, _shift_frequency(case, other), definition=legacy)
    assert skewed["D"] == 1.0 and "design_fidelity" not in skewed
