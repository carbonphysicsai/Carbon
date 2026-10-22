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
    bank = _sealed_bank()
    rows = physical.bank_rows(bank, sealed.input_names())
    return {
        "bank": bank,
        "rows": rows,
        "definition": sealed.definition(bank=bank, train_raw=b""),
        "truth": [[row["record"]["rung_peaks_c"]["primary"]] for row in rows],
    }


def _measure(case, outputs, *, rows=None, definition=None, module=sealed):
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
    assert sealed.EVALUATION_VERSION == "f02-dual-sealed-grid-8x1-v1"
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
    worse = [[row[0] + 0.3] for row in case["truth"]]
    result = _measure(case, worse)
    assert result["A"] is not None and 0 <= result["A"] < 1.0
    assert result["D"] is not None and 0 <= result["D"] <= 1.0


def test_the_grid_measure_equals_the_development_measure_on_a_dev_shaped_bank(case):
    """The sealed grader adds the grid check only: on the same cells under the development cohort the registered
    measurement gives the same A, D, gates and decision."""
    outputs = [[row[0] + 0.1] for row in case["truth"]]
    sealed_result = _measure(case, outputs)
    dev_rows = [{**row, "cohort": "decision_cold_eight"} for row in case["rows"]]
    dev_definition = dev.definition(bank=case["bank"], train_raw=b"")
    dev_result = _measure(
        case, outputs, rows=dev_rows, definition=dev_definition, module=dev
    )
    assert sealed_result == dev_result


def test_a_bank_that_is_not_the_sealed_grid_refuses(case):
    truth = case["truth"]
    wrong_cohort = [{**row, "cohort": "decision_cold_eight"} for row in case["rows"]]
    with pytest.raises(sealed.Refused) as refused:
        _measure(case, truth, rows=wrong_cohort)
    assert refused.value.code == "f02_bank_cohort"
    twice = copy.deepcopy(case["rows"])
    twice[1]["record"]["condition_id"] = "condition-1"
    with pytest.raises(sealed.Refused) as refused:
        _measure(case, truth, rows=twice)
    assert refused.value.code == "f02_sealed_grid"
    repeated = copy.deepcopy(case["rows"])
    repeated[1]["record"]["design_id"] = repeated[0]["record"]["design_id"]
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
