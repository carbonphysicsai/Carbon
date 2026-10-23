"""F02 grades a sealed exam batch as one design x condition grid (evaluation version
``f02-dual-sealed-grid-8x1-v1``): F02's registered measurement for a sealed batch, unchanged, on a complete 8 x 1
grid in the one sealed cohort, with 0.5 A + 0.5 D, no leg minimum carried, and the producer identity covering the
shared grouping."""

from __future__ import annotations

import copy
import json

import pytest
from test_f02_sealed_grading import _sealed_bank

from carbon.challenge_kit import physical_pack
from carbon.scoring import f02_dual_pack as dev
from carbon.scoring import f02_sealed_dual_pack as sealed
from carbon.scoring import physical_dual_pack as physical

PLATFORM = {"inference_image_id": "sha256:" + "1" * 64}


@pytest.fixture(scope="module")
def case():
    bank = _sealed_bank(probes=True)
    rows = physical.bank_rows(bank, sealed.input_names())
    return {
        "bank": bank,
        "rows": rows,
        "definition": sealed.definition(bank=bank, train_raw=b""),
        "truth": [
            [row["record"]["rung_peaks_c"]["primary"]]
            for row in rows
            if row["cohort"] == "decision_sealed_grid"
        ],
        "model": _power_law_model(),
    }


def _power_law_model():
    """A stand-in model with exactly the registered sensitivities (the probes
    carry no references): rise over the initial temperature, log-log in TRAIN."""
    import numpy as np

    from carbon.challenge_kit import f02_train

    train = f02_train.load_public_train(sealed._f02.VERSION)
    x = np.asarray(train["inputs"], float)
    rise = np.asarray(train["targets"], float)[:, 0] - 40.0
    design = np.column_stack([np.ones(len(x)), np.log(x)])
    coefficients, *_ = np.linalg.lstsq(design, np.log(rise), rcond=None)

    def predict(point):
        row = np.concatenate([[1.0], np.log(np.asarray(point, float))])
        return [40.0 + float(np.exp(row @ coefficients))]

    return predict


def _cells(rows):
    return [r for r in rows if r["cohort"] != "probe_response"]


def _full(case, cell_outputs, probe=None, rows=None):
    """Predictions for every row in the delivered order: the cell predictions in
    the order the cells appear, the stand-in model (or ``probe``) at each probe."""
    model = probe or case["model"]
    cells = iter(cell_outputs)
    return [
        (
            model([float(row["inputs"][n]) for n in ("peak_w", "on_time_s")])
            if row["cohort"] == "probe_response"
            else list(map(float, next(cells, [0.0])))
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
        limits={},
        objective={},
        train_raw=b"",
        names=sealed.input_names(),
    )


def test_the_definition_registers_the_grid_and_the_batchs_own_receipt(case):
    definition = case["definition"]
    sealed.validate_definition(definition)
    assert definition["bank_kind"] == "sealed_batch"
    assert definition["cohort_counts"] == {sealed.COHORT: 8}
    assert definition["grid"] == {"designs": 8, "conditions": 1}
    assert definition["reference_interval"]["receipt"] == physical.sha(
        case["bank"]["solver_evidence"]
    )
    assert sealed.EVALUATION_VERSION == "f02-dual-sealed-grid-8x1-v2"
    assert sealed.COHORT == "decision_sealed_grid"
    cohorts = case["bank"]["cohorts"]
    # 4 base points: each the base, 2 moves per input (2 inputs) and 2 law rows,
    # interleaved with the cells (never a suffix).
    assert cohorts.count(sealed.COHORT) == 8 and len(cohorts) == 8 + 4 * 7
    assert cohorts[-8:] != (sealed.COHORT,) * 8 and cohorts[:8] != (sealed.COHORT,) * 8
    assert definition["probes"] == {"cohort": "probe_response", "rows": 28}
    assert {
        r["condition_id"]
        for r, c in zip(case["bank"]["reference_records"], cohorts, strict=True)
        if c == sealed.COHORT
    } == {"condition-0"}


def test_a_model_equal_to_the_references_earns_full_a_and_d(case):
    result = _measure(case, case["truth"])
    assert result["A_legs"]["A_acc"] == 1.0 and result["D"] == 1.0
    # The stand-in power-law model is not exactly affine in power, so the law
    # leg is near but below one; the response leg matches the registered fit.
    assert result["A_legs"]["A_response"] == pytest.approx(1.0, abs=1e-3)
    assert result["A"] == pytest.approx(1.0, abs=2e-3)
    assert (
        all(result["gates"].values())
        and result["decision_outcome"] == "VERIFIED_FEASIBLE"
    )


def test_a_worse_model_lowers_a_and_all_values_are_finite(case):
    worse = [[row[0] + 0.3] for row in case["truth"]]
    result = _measure(case, worse)
    assert result["A"] is not None and 0 <= result["A"] < 1.0
    assert result["D"] is not None and 0 <= result["D"] <= 1.0


def test_the_grid_measure_equals_the_development_measure_on_a_dev_shaped_bank(case):
    """The sealed grader adds the grid check only: on the same cells under the development cohort the registered
    measurement gives the same A, D, gates and decision."""
    outputs = [[row[0] + 0.1] for row in case["truth"]]
    sealed_result = _measure(case, outputs)
    cells = _cells(case["rows"])
    order = sorted(range(len(cells)), key=lambda i: cells[i]["case_id"])
    dev_rows = [{**cells[i], "cohort": "decision_cold_eight"} for i in order]
    outputs = [outputs[i] for i in order]
    dev_definition = dev.definition(
        bank=sealed.probe_design.cells_only(case["bank"], by_case_id=True),
        train_raw=b"",
    )
    dev_result = _measure(
        case, outputs, rows=dev_rows, definition=dev_definition, module=dev
    )
    ignored = ("A", "D", "gates", "design_fidelity", "A_legs", "physics_half")
    assert {k: v for k, v in sealed_result.items() if k not in ignored} == {
        k: v for k, v in dev_result.items() if k not in ignored
    }
    assert sealed_result["A_legs"]["A_acc"] == dev_result["A"]
    assert {k: v for k, v in sealed_result["gates"].items() if k != "physics_laws"} == (
        dev_result["gates"]
    )
    # D = min(V, C): C is the native reduction's, V the mean decision measure.
    assert sealed_result["D"] <= dev_result["D"] + 1e-12


def test_a_bank_that_is_not_the_sealed_grid_refuses(case):
    truth = case["truth"]
    wrong_cohort = [{**row, "cohort": "decision_cold_eight"} for row in case["rows"]]
    with pytest.raises(sealed.Refused) as refused:
        _measure(case, truth, rows=wrong_cohort)
    assert refused.value.code == "f02_bank_cohort"
    first, second = [
        i for i, r in enumerate(case["rows"]) if r["cohort"] != "probe_response"
    ][:2]
    twice = copy.deepcopy(case["rows"])
    twice[second]["record"]["condition_id"] = "condition-1"
    with pytest.raises(sealed.Refused) as refused:
        _measure(case, truth, rows=twice)
    assert refused.value.code == "f02_sealed_grid"
    repeated = copy.deepcopy(case["rows"])
    repeated[second]["record"]["design_id"] = repeated[first]["record"]["design_id"]
    with pytest.raises(sealed.Refused):
        _measure(case, truth, rows=repeated)
    with pytest.raises(sealed.Refused):
        _measure(case, truth[:7], rows=case["rows"][:7])


def test_a_malformed_sealed_definition_refuses(case):
    for key, value in (
        ("cohort_counts", {"decision_cold_eight": 8}),
        ("grid", {"designs": 4, "conditions": 2}),
        ("bank_kind", "development"),
    ):
        with pytest.raises(sealed.Refused):
            sealed.validate_definition({**case["definition"], key: value})


def test_the_development_producer_is_untouched_and_dispatch_is_by_population(case):
    assert "f02_sealed_dual_pack.py" not in dev.FILES
    assert sealed.producer_digest() != dev.producer_digest()
    assert sealed.adapter("2.1") is sealed._ADAPTER
    assert sealed.adapter("2.3").EVALUATION_VERSION == sealed.EVALUATION_VERSION
    assert sealed.adapter("2.3").VERSION == "2.3" and sealed.adapter("9.9") is None
    assert sealed.adapter_for_bank(case["bank"], "2.1") is sealed._ADAPTER
    development = physical_pack.development_bank("f02", "2.1")
    assert (
        sealed.adapter_for_bank(development, "2.1").EVALUATION_VERSION
        != sealed.EVALUATION_VERSION
    )
    with pytest.raises(sealed.Refused):
        sealed.adapter_for_bank({"cohorts": ("practice",) * 8}, "2.1")
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
    first, second = tmp_path / "a", tmp_path / "b"
    one = sealed.write_sealed_pack(first, case["bank"], version="2.3", **PLATFORM)
    two = sealed.write_sealed_pack(second, case["bank"], version="2.3", **PLATFORM)
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
        sealed.write_sealed_pack(first, case["bank"], version="2.3")
    with pytest.raises(sealed.Refused):
        sealed.write_sealed_pack(
            tmp_path / "c", physical_pack.development_bank("f02", "2.1"), version="2.1"
        )


# --- the physics half ----------------------------------------------------------


def test_the_definition_registers_the_critical_and_physics_blocks(case):
    definition = case["definition"]
    assert definition["critical"]["rule"] == "D=min(V,C)"
    assert definition["critical"]["value"]["main_limit"] == [
        {"component": "thermal_margin", "sigma": 1}
    ]
    block = definition["physics"]
    assert block["rule"] == "A=mean(A_acc,A_robust,A_law,A_response)"
    exponents = block["response"]["exponent"][0]
    assert exponents[0] > 0 and exponents[1] > 0  # rises with power and time
    assert {law["name"] for law in block["laws"]} == {
        "affine_in_power",
        "peak_not_below_initial",
    }


def _non_affine_model(case):
    """Accurate near the cells but quadratic in power between them."""
    good = case["model"]

    def predict(point):
        base = good(point)[0]
        return [base + 0.05 * (point[0] - 85.0) ** 2]

    return predict


def test_a_nonaffine_model_loses_on_the_law_leg(case):
    good = _measure(case, case["truth"])
    bad = _measure(case, _full(case, case["truth"], probe=_non_affine_model(case)))
    assert bad["A_legs"]["A_law"] < good["A_legs"]["A_law"] - 0.02
    assert bad["A_legs"]["A_acc"] == good["A_legs"]["A_acc"]


def test_a_wrong_trend_model_loses_on_the_response_leg_and_gate(case):
    good = case["model"]

    def flipped(point):
        return good([100.0 + 70.0 - point[0], point[1]])

    result = _measure(case, _full(case, case["truth"], probe=flipped))
    assert result["A_legs"]["A_response"] < 0.9
    assert result["gates"]["physics_laws"] is False
    assert any("peak_w" in item for item in result["physics_half"]["gate_failed_laws"])


def test_a_peak_below_the_initial_temperature_fails_the_law_gate(case):
    outputs = [list(r) for r in case["truth"]]
    outputs[0] = [35.0]
    result = _measure(case, outputs)
    assert result["gates"]["physics_laws"] is False
    assert "peak_not_below_initial" in result["physics_half"]["gate_failed_laws"]


def test_a_sealed_f02_bank_is_graded_under_the_v2_grid_version(case):
    for version in ("2.1", "2.2", "2.3"):
        chosen = sealed.adapter_for_bank(case["bank"], version)
        assert chosen.EVALUATION_VERSION == "f02-dual-sealed-grid-8x1-v2"
        assert chosen.VERSION == version


def test_the_probes_follow_the_cells_unreferenced_and_deterministically(case):
    rows = case["rows"]
    probes = [r for r in rows if r["cohort"] == "probe_response"]
    assert all(r["reference"] is None for r in probes)
    again = _sealed_bank(probes=True)
    assert (again["inputs"] == case["bank"]["inputs"]).all()


def test_an_infeasible_pick_under_v2_is_not_eligible(case):
    from carbon.scoring import dual_score

    exact = _measure(case, case["truth"])
    infeasible = next(i for i, r in enumerate(case["truth"]) if r[0] > 95.0)
    # The model calls every other burst too hot and the infeasible one cold: it is
    # the only action offered, so it is picked, and it fails verification.
    bad = [[120.0] for _ in case["truth"]]
    bad[infeasible] = [60.0]
    result = _measure(case, bad)
    assert result["gates"]["verified_pick"] is False
    assert result["selected_action"] != exact["selected_action"]
    provisional = "sha256:" + "0" * 64
    pack = dual_score.register_pack(
        {
            **sealed.applied_pack(),
            "physics_contract_digest": provisional,
            "measurement_contract_digest": provisional,
        }
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
                        physical.METRICS[leg]: (
                            {"status": "RESOLVED", "value": result[leg], "unit": "1"}
                            if result[leg] is not None
                            else {
                                "status": "CANDIDATE_INVALID",
                                "value": None,
                                "unit": "1",
                            }
                        )
                        for leg in ("A", "D")
                    },
                    "decision_outcome": result["decision_outcome"],
                }
            ],
        },
        pack,
    )["models"][0]
    assert row["status"] != "SCORED_DEVELOPMENT_CANDIDATE"
