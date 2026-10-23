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
        "truth": [
            [float(v) for v in row]
            for row, c in zip(bank["references"], bank["cohorts"], strict=True)
            if c == "decision_sealed_grid"
        ],
        "model": _power_law_model(public["train"]),
    }


def _power_law_model(train_raw):
    """A stand-in model with exactly the registered sensitivities: the TRAIN
    log-log fit (the probes carry no references, so a model must be supplied)."""
    import io

    import numpy as np

    with np.load(io.BytesIO(train_raw), allow_pickle=False) as data:
        x, y = np.asarray(data["inputs"], float), np.asarray(data["targets"], float)
    design = np.column_stack([np.ones(len(x)), np.log(x)])
    coefficients, *_ = np.linalg.lstsq(design, np.log(y), rcond=None)

    def predict(inputs):
        row = np.concatenate([[1.0], np.log(np.asarray(inputs, float))])
        return [float(v) for v in np.exp(row @ coefficients)]

    return predict


def _cells(rows):
    return [r for r in rows if r["cohort"] != "probe_response"]


def _full(case, cell_outputs, probe=None, rows=None):
    """Predictions for every row in the delivered order: the cell predictions in
    the order the cells appear, the stand-in power-law model (or ``probe``) at
    each probe row."""
    model = probe or case["model"]
    cells = iter(cell_outputs)
    return [
        (
            model([float(row["inputs"][n]) for n in case["names"]])
            if row["cohort"] == "probe_response"
            else list(map(float, next(cells, [0.0] * 7)))
        )
        for row in (rows or case["rows"])
    ]


def _measure(case, outputs, *, rows=None, definition=None, module=sealed):
    if module is sealed and len(outputs) == 8:
        outputs = _full(case, outputs, rows=rows)
    elif module is not sealed:
        rows = [r for r in (rows or case["rows"]) if r["cohort"] != "probe_response"]
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
    cohorts = case["bank"]["cohorts"]
    assert cohorts.count(sealed.COHORT) == 8 and len(cohorts) == 60
    # The private probes are interleaved with the cells, never a suffix.
    assert cohorts[:8] != (sealed.COHORT,) * 8 and cohorts[-8:] != (sealed.COHORT,) * 8
    assert set(cohorts) == {sealed.COHORT, "probe_response"}
    assert definition["probes"] == {"cohort": "probe_response", "rows": 52}
    assert case["bank"]["reference_present"] == tuple(
        c == sealed.COHORT for c in cohorts
    )
    assert {
        r["condition_id"]
        for r, c in zip(case["bank"]["reference_records"], cohorts, strict=True)
        if c == sealed.COHORT
    } == {"condition-0"}


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
    dev_rows = [
        {**row, "cohort": "decision_near_limit"} for row in _cells(case["rows"])
    ]
    dev_definition = {
        **dev.definition(
            bank=case["bank"], train_raw=case["public"]["train"], version="1.2"
        ),
        "geometry_count": 8,
    }
    dev_result = _measure(
        case, outputs, rows=dev_rows, definition=dev_definition, module=dev
    )
    # D = min(V, C): the sealed grid adds the critical-prediction credit to the
    # development measure's verified value; everything else is the same.
    assert sealed_result["design_fidelity"]["C"] is not None
    assert sealed_result["D"] == min(
        dev_result["D"], sealed_result["design_fidelity"]["C"]
    )
    ignored = ("A", "D", "gates", "design_fidelity", "A_legs", "physics_half")
    assert {k: v for k, v in sealed_result.items() if k not in ignored} == {
        k: v for k, v in dev_result.items() if k not in ignored
    }
    # The physics half: A_acc is the development A; the gates add the law gate.
    assert sealed_result["A_legs"]["A_acc"] == dev_result["A"]
    assert {k: v for k, v in sealed_result["gates"].items() if k != "physics_laws"} == (
        dev_result["gates"]
    )


def test_a_bank_that_is_not_the_sealed_grid_refuses(case):
    truth = case["truth"]
    wrong_cohort = [{**row, "cohort": "decision_near_limit"} for row in case["rows"]]
    with pytest.raises(fdm.F08MeasurementRefused) as refused:
        _measure(case, truth, rows=wrong_cohort)
    assert refused.value.code == "f08_bank_cohort"
    first, second = [
        i for i, r in enumerate(case["rows"]) if r["cohort"] != "probe_response"
    ][:2]
    twice = copy.deepcopy(case["rows"])
    twice[second]["record"][
        "condition_id"
    ] = "condition-1"  # 8 designs x 2 conditions is not the registered shape
    with pytest.raises(fdm.F08MeasurementRefused) as refused:
        _measure(case, truth, rows=twice)
    assert refused.value.code == "f08_sealed_grid"
    repeated = copy.deepcopy(case["rows"])
    repeated[second]["record"]["design_id"] = repeated[first]["record"]["design_id"]
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
    ids = [row["case_id"] for row in _cells(case["rows"])]
    other = next(i for i, cid in enumerate(ids) if cid != exact["pick"])
    skewed = _measure(case, _shift_frequency(case, other))
    # The pick, the gates and the verified value are all unchanged.
    assert skewed["pick"] == exact["pick"] and skewed["regret_mm_per_n"] == 0.0
    assert all(skewed["gates"].values())
    assert skewed["design_fidelity"]["C"] < 1.0
    assert skewed["D"] == skewed["design_fidelity"]["C"] < 1.0


def test_wrong_margins_on_the_selected_geometry_also_cap_d(case):
    exact = _measure(case, case["truth"])
    ids = [row["case_id"] for row in _cells(case["rows"])]
    chosen = ids.index(exact["pick"])
    skewed = _measure(case, _shift_frequency(case, chosen))
    assert skewed["pick"] == exact["pick"] and skewed["D"] < 1.0


def test_a_definition_without_the_critical_block_grades_value_only(case):
    legacy = {k: v for k, v in case["definition"].items() if k != "critical"}
    ids = [row["case_id"] for row in _cells(case["rows"])]
    exact = _measure(case, case["truth"])
    other = next(i for i, cid in enumerate(ids) if cid != exact["pick"])
    skewed = _measure(case, _shift_frequency(case, other), definition=legacy)
    assert skewed["D"] == 1.0 and "design_fidelity" not in skewed


# --- the physics half (A = mean(A_acc, A_robust, A_law)) ---------------------


def _unphysical(case):
    """Accurate within A_acc but breaking the 1/zeta peak law: each damping
    level peak moved independently by a few percent."""
    outputs = copy.deepcopy(case["truth"])
    names = case["definition"]["targets"]
    for row in outputs:
        row[names.index("peak_tip_z005_mm_per_n")] *= 1.06
        row[names.index("peak_tip_z020_mm_per_n")] *= 0.94
    return outputs


def test_the_definition_registers_the_physics_block(case):
    block = case["definition"]["physics"]
    assert block["rule"] == "A=mean(A_acc,A_robust,A_law,A_response)"
    assert block["legs_not_applied"] == []
    assert {law["name"] for law in block["laws"]} >= {
        "damping_scaling_005_010",
        "frequency_independence_005_010",
        "peak_not_below_static",
    }
    assert sealed.f08_physics.GATE in [
        *sealed.fdm.GATES,
        sealed.f08_physics.GATE,
    ]


def test_a_model_equal_to_the_references_earns_full_physics_legs(case):
    result = _measure(case, case["truth"])
    # The references satisfy the laws to within their own residual, so the law
    # leg is near but not necessarily exactly one; the other legs are exact.
    assert result["A_legs"]["A_acc"] == 1.0 and result["A_legs"]["A_robust"] == 1.0
    assert result["A_legs"]["A_law"] > 0.99
    assert result["gates"]["physics_laws"] is True


def test_an_accurate_but_unphysical_model_loses_on_the_law_leg(case):
    good = _measure(case, case["truth"])
    bad = _measure(case, _unphysical(case))
    assert bad["A_legs"]["A_law"] < good["A_legs"]["A_law"]
    assert bad["A"] < good["A"]
    assert bad["physics_half"]["mean_residual"] > good["physics_half"]["mean_residual"]


def test_a_peak_below_the_static_compliance_fails_the_law_gate(case):
    outputs = copy.deepcopy(case["truth"])
    names = case["definition"]["targets"]
    outputs[0][names.index("peak_tip_z010_mm_per_n")] = 0.0
    result = _measure(case, outputs)
    assert result["gates"]["physics_laws"] is False
    assert "peak_not_below_static" in result["physics_half"]["gate_failed_laws"]


def test_unordered_damping_peaks_fail_the_law_gate(case):
    outputs = copy.deepcopy(case["truth"])
    names = case["definition"]["targets"]
    j5, j20 = (names.index(f"peak_tip_z{z}_mm_per_n") for z in ("005", "020"))
    outputs[1][j5], outputs[1][j20] = outputs[1][j20], outputs[1][j5]
    result = _measure(case, outputs)
    assert result["gates"]["physics_laws"] is False
    assert "peaks_ordered_by_damping" in result["physics_half"]["gate_failed_laws"]


def test_the_physics_block_is_optional_for_an_earlier_definition(case):
    legacy = {k: v for k, v in case["definition"].items() if k != "physics"}
    result = _measure(case, case["truth"], definition=legacy)
    assert "A_legs" not in result and "physics_laws" not in result["gates"]


def test_a_sealed_f08_bank_is_graded_under_the_v2_grid_version(case):
    """Dispatch by the bank population reaches the min(V, C) version for every
    served Challenge version."""
    for version in ("1.2", "1.3", "1.4"):
        chosen = sealed.adapter_for_bank(case["bank"], version)
        assert chosen.EVALUATION_VERSION == "f08-dual-sealed-grid-8x1-v2"
        assert chosen.VERSION == version


# --- A_response from the private probes ---------------------------------------


def _wrong_trend_model(case):
    """Correct everywhere the references are (the cells), wrong trends between
    them: the length dependence of every output is inverted."""
    good = case["model"]
    names = case["names"]

    def predict(x):
        flipped = list(x)
        j = names.index("length_mm")
        flipped[j] = (180.0 * 260.0) / x[j]
        return good(flipped)

    return predict


def test_the_probes_are_private_unreferenced_rows_after_the_cells(case):
    rows = case["rows"]
    assert [r["cohort"] for r in rows].count("decision_sealed_grid") == 8
    assert [r["cohort"] for r in rows[:8]] != ["decision_sealed_grid"] * 8
    probes = [r for r in rows if r["cohort"] == "probe_response"]
    assert len(probes) == 52 and all(r["reference"] is None for r in probes)
    assert sum(1 for r in probes if r["record"]["probe"]["dim"] is None) == 4


def test_the_registered_sensitivities_come_from_train(case):
    spec = case["definition"]["physics"]["response"]
    assert spec["inputs"] == list(sealed.f08_physics.INPUTS)
    assert len(spec["exponent"]) == 7 and len(spec["exponent"][0]) == 6
    # beam theory: static compliance rises steeply with length, frequency falls
    j = spec["outputs"].index("static_tip_mm_per_n")
    assert spec["exponent"][j][0] > 2.0
    f = spec["outputs"].index("peak_frequency_z010_hz")
    assert spec["exponent"][f][0] < -1.0


def test_a_model_with_the_registered_sensitivities_earns_full_a_response(case):
    result = _measure(case, case["truth"])
    assert result["A_legs"]["A_response"] == pytest.approx(1.0, abs=1e-3)
    assert result["physics_half"]["sign_gate_failed"] == []


def test_a_shuffled_sensitivity_model_loses_on_the_response_leg(case):
    good = _measure(case, case["truth"])
    outputs = _full(case, case["truth"], probe=_wrong_trend_model(case))
    bad = _measure(case, outputs)
    assert bad["A_legs"]["A_response"] < good["A_legs"]["A_response"] - 0.05
    assert bad["A_legs"]["A_acc"] == good["A_legs"]["A_acc"]
    assert bad["gates"]["physics_laws"] is False
    assert any("length_mm" in item for item in bad["physics_half"]["gate_failed_laws"])


def test_an_unusable_probe_prediction_fails_the_gate_and_scores_zero_response(case):
    def broken(x):
        return [0.0] * 7

    result = _measure(case, _full(case, case["truth"], probe=broken))
    assert result["A_legs"]["A_response"] == 0.0
    assert result["gates"]["physics_laws"] is False
    assert "probe_prediction_invalid" in result["physics_half"]["gate_failed_laws"]


def test_the_probes_are_deterministic_from_the_batch(case):
    from test_f08_sealed_pack import batch

    again = pack.sealed_bank(*batch())
    assert (again["inputs"] == case["bank"]["inputs"]).all()
    other = pack.sealed_bank(*batch(seed=12))
    assert not (other["inputs"] == case["bank"]["inputs"]).all()


def test_an_infeasible_pick_under_v2_is_not_eligible(case):
    """A model that makes a reference-infeasible geometry look best picks it: the
    verified-pick gate fails, the outcome is a missed opportunity and the graded
    model is not eligible, whatever its A and D are."""
    from carbon.scoring import dual_score

    exact = _measure(case, case["truth"])
    names = case["definition"]["targets"]
    tips = [names.index(n) for n in case["definition"]["tip_targets"]]
    limit = json.loads(case["public"]["important_limit_definition"])["constraints"]
    bad = copy.deepcopy(case["truth"])
    infeasible = next(
        i
        for i, row in enumerate(case["truth"])
        if max(row[j] for j in tips) > limit["dynamic_tip_mm_per_n_max"]
    )
    for j in tips:
        bad[infeasible][j] = 1e-4  # predicted far safer and better than any other
    result = _measure(case, bad)
    ids = [r["case_id"] for r in _cells(case["rows"])]
    assert result["pick"] == ids[infeasible] != exact["pick"]
    assert result["gates"]["verified_pick_feasible"] is False
    assert result["decision_outcome"] == "MISSED_OPPORTUNITY"

    provisional = "sha256:" + "0" * 64
    pack = dual_score.register_pack(
        {
            **sealed.applied_pack(),
            "physics_contract_digest": provisional,
            "measurement_contract_digest": provisional,
        }
    )

    def leg(value):
        return (
            {"status": "RESOLVED", "value": value, "unit": "1"}
            if value is not None
            else {"status": "CANDIDATE_INVALID", "value": None, "unit": "1"}
        )

    row = dual_score.score(
        {
            "schema": dual_score.INPUT_SCHEMA,
            "scope": pack["scope"],
            "challenge": pack["challenge"],
            "physics_contract_digest": provisional,
            "measurement_contract_digest": provisional,
            "population_role": "P",
            "common_mask_digest": provisional,
            "models": [
                {
                    "artifact_digest": provisional,
                    "gates": {
                        k: "PASS" if v else "FAIL" for k, v in result["gates"].items()
                    },
                    "measurements": {
                        physical.METRICS["A"]: leg(result["A"]),
                        physical.METRICS["D"]: leg(result["D"]),
                    },
                    "decision_outcome": result["decision_outcome"],
                }
            ],
        },
        pack,
    )["models"][0]
    assert row["status"] != "SCORED_DEVELOPMENT_CANDIDATE" and row["score"] in (
        None,
        0,
        0.0,
    )
