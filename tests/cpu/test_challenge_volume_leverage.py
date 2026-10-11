"""Economic sensitivity arithmetic, not market, inference or physical qualification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/development/challenge_pipeline/value-cost"
SHEET = json.loads((DOCS / "volume-leverage.json").read_text(encoding="utf-8"))
PRIOR = json.loads((DOCS / "analysis.json").read_text(encoding="utf-8"))
NAMES = ("battery", "motor", "cooling-cell", "f02", "f06", "f08", "f13", "f17")
COMMON = SHEET["common_assumptions"]


def test_scenarios_cannot_become_execution_or_acceptance():
    assert SHEET["maturity"] == "SPECIFIED"
    assert SHEET["adoption"] == "HUMAN_INPUT"
    assert SHEET["framework_rank"] == PRIOR["ranking"] == "UNCOMPUTABLE"
    assert SHEET["empirical_annual_rank"] == "NOT_DEMONSTRATED"
    assert set(SHEET["cards"]) == set(NAMES)
    assert SHEET["solver_runs"] == 0 and SHEET["spend_grant"] is None
    assert not any(
        SHEET[key]
        for key in ("dispatch_ready", "protected_material", "historical_rescore")
    )
    assert PRIOR["volume_leverage_followup"]["sheet"] == "volume-leverage.json"
    assert not PRIOR["volume_leverage_followup"]["owner_framework_changed"]


@pytest.mark.parametrize("name", NAMES)
def test_volume_is_bottom_up_assumed_not_shipments_or_paid_demand(name):
    card = SHEET["cards"][name]
    volume, value = card["volume"], card["value"]
    assert volume["status"] == "ASSUMPTION_CONDITIONAL_COHORT_NOT_MARKET"
    assert volume["empirical_lower_bound"] == 0
    assert volume["observed_annual_decisions"] is None
    assert volume["eligibility_adoption_rate"] is None
    assert len({source["author"] for source in volume["sources"]}) >= 2
    assert len({source["url"] for source in volume["sources"]}) >= 2
    v3 = (DOCS / f"{name}.md").read_text(encoding="utf-8").split("### V3", 1)[1]
    for source in volume["sources"]:
        assert source["url"] in v3 and source["support"]
    factors = zip(volume["cohort_size"], volume["cadence_per_unit"])
    calculated = [size * cadence for size, cadence in factors]
    if name == "battery":
        assert volume["unit"] == "ELIGIBLE_CHARGING_SESSIONS_PER_YEAR"
        calculated = [
            units * days for units, days in zip(calculated, volume["operating_days"])
        ]
    else:
        assert volume["unit"] == "IN_SCOPE_REVISIONS_PER_YEAR"
        assert volume["operating_days"] is None
    assert volume["annual_units"] == pytest.approx(calculated)
    old_value = PRIOR["cards"][name]["buyer_value"]
    v2 = old_value["after_gross"] or old_value["before_gross"]
    assert value["v2_assumed_usd_per_unit"] == v2
    assert value["conditional_annual_gross_usd"] == pytest.approx(
        [units * dollars for units, dollars in zip(calculated, v2)]
    )
    assert value["v3_pass"] == "NOT_DEMONSTRATED"
    for key in (
        "realized_annual_usd",
        "enabled_incremental_annual_usd",
        "net_annual_usd",
    ):
        assert value[key] is None


@pytest.mark.parametrize("name", NAMES)
def test_workflow_analogues_do_not_earn_matched_counts_or_model_bounds(name):
    workflow = SHEET["cards"][name]["workflow"]
    assert workflow["count_status"] == "SOURCED_ANALOGUE_WITH_ASSUMED_TRANSFER"
    assert PRIOR["cards"][name]["workflow_evaluation_count"] == workflow["count_status"]
    assert workflow["N_measured_for_current_buyer"] is None
    assert workflow["distinct_new_reference_work_required"]
    assert workflow["N"] == sorted(workflow["N"])
    assert workflow["inference_status"] == "ASSUMPTION_NOT_MEASURED_FOR_THIS_TASK"
    assert workflow["v4_pass"] == "NOT_DEMONSTRATED"
    assert workflow["strongest_baseline_pass"] == "NOT_DEMONSTRATED"
    assert workflow["current_complete_panel_cost_pass"] == "NOT_DEMONSTRATED"
    assert workflow["evaluation_unit"] and workflow["sources"]
    text = (DOCS / f"{name}.md").read_text(encoding="utf-8")
    v4 = text.split("### V4", 1)[1].split("### V5", 1)[0]
    for source in workflow["sources"]:
        assert source["url"] in v4
    # Owner-reported context does not fill the existing full-panel quantile slots.
    cost = PRIOR["cards"][name]["cost"]
    assert cost["complete_case_p50_cpu_h"] is cost["complete_case_p95_cpu_h"] is None


@pytest.mark.parametrize("name", NAMES)
def test_build_acquisition_fit_reuse_and_retained_truth_are_charged(name):
    card = SHEET["cards"][name]
    workflow, result = card["workflow"], card["calculations"]
    reference = workflow["reference_cpu_s"]
    if reference is None:
        assert name in {"motor", "f06", "f17"}
        assert workflow["reference_cost_status"] == "NOT_MEASURED"
        assert result is None
        return
    assert len(result) == 3
    for index, (n, r, row) in enumerate(zip(workflow["N"], reference, result)):
        c = COMMON["inference_cpu_s"][index]
        m = COMMON["decisions_per_model"][index]
        b = workflow["acquisition_evaluations"]
        f = COMMON["fit_cpu_h"][index]
        v = workflow["retained_evaluations"]
        direct = n * r / 3600
        acquisition = b * r / 3600
        build = acquisition + f
        serving = n * c / 3600
        model = serving + build / m
        end = model + v * r / 3600
        expected = {
            "reference_cpu_h": direct,
            "acquisition_cpu_h": acquisition,
            "build_cpu_h": build,
            "amortized_build_cpu_h": build / m,
            "serving_cpu_h": serving,
            "retained_verification_cpu_h": v * r / 3600,
            "model_cpu_h": model,
            "end_to_end_cpu_h": end,
            "leverage_excluding_verification": direct / model,
            "leverage_including_verification": direct / end,
            "cpu_h_saved": direct - end,
            "serial_wall_h_saved_assumption": direct - end,
            "compute_usd_saved": (direct - end) * COMMON["cpu_price_usd_per_h"],
        }
        for key, number in expected.items():
            assert row[key] == pytest.approx(number)
        denominator = ((n - v) * r - n * c) / 3600
        if denominator > 0:
            assert row["minimum_decisions_to_break_even"] == pytest.approx(
                build / denominator
            )
        else:
            assert row["minimum_decisions_to_break_even"] is None
        assert (
            row["leverage_including_verification"]
            < row["leverage_excluding_verification"]
        )


def test_cold_start_and_cheap_baseline_can_fail_not_be_clamped_to_zero():
    cooling = SHEET["cards"]["cooling-cell"]["calculations"]
    assert cooling[1]["cpu_h_saved"] < 0
    assert cooling[1]["leverage_including_verification"] < 1
    assert cooling[1]["minimum_decisions_to_break_even"] == pytest.approx(
        10.431496062992126
    )
    baseline = SHEET["f08_cached_baseline"]
    seconds = (
        baseline["designs"]
        * baseline["new_geometry_basis_cpu_s"]
        / baseline["decisions_served"]
        + baseline["queries"] * baseline["cached_query_cpu_s"]
    )
    assert seconds == 850
    assert baseline["baseline_cpu_h"] == pytest.approx(seconds / 3600)
    verified = seconds + (
        baseline["retained_reference_evaluations"]
        * baseline["new_geometry_basis_cpu_s"]
    )
    assert verified == 1000
    assert baseline["baseline_with_verification_cpu_h"] == pytest.approx(
        verified / 3600
    )
    assert (
        baseline["baseline_with_verification_cpu_h"]
        < baseline["model_end_to_end_cpu_h"]
    )
    assert baseline["v4_result_if_baseline_meets_same_decision_adequacy"] == "FAIL"


def test_annual_base_tie_is_not_measured_market_or_a_scientific_rank():
    values = {
        name: card["value"]["conditional_annual_gross_usd"][1]
        for name, card in SHEET["cards"].items()
    }
    assert SHEET["conditional_base_order"] == sorted(
        NAMES, key=lambda name: -values[name]
    )
    assert values["f06"] == values["f17"] == 72000
    assert values["battery"] == 315000
    assert 0 * SHEET["cards"]["battery"]["value"]["v2_assumed_usd_per_unit"][1] == 0
    text = (DOCS / "analysis.md").read_text(encoding="utf-8")
    for phrase in ("Negative stays negative", "V4 FAILS", "CPU is not elapsed time"):
        assert phrase in text


def test_reported_c1_contexts_and_censored_tail_are_not_quantiles():
    cards = SHEET["cards"]
    assert cards["battery"]["workflow"]["reference_cpu_s"] == [91, 91, 91]
    assert cards["cooling-cell"]["workflow"]["reference_cpu_s"] == [1620] * 3
    assert cards["f02"]["workflow"]["reference_cpu_s"] == [120, 150, 180]
    assert cards["f08"]["workflow"]["reference_cpu_s"] == [40, 75, 110]
    silencer = cards["f13"]["workflow"]
    assert silencer["reference_cpu_s"] == [456, 1800, 4860]
    assert "NOT_UPPER_BOUND" in silencer["reference_cpu_s_semantics"]
    assert COMMON["reference_wall_to_cpu"].endswith("ASSUMPTION")
    assert COMMON["inference_cpu_s"] == COMMON["inference_wall_s"] == [1, 0.1, 0.001]


def test_battery_batch_record_not_current_single_query_bound():
    receipt = SHEET["battery_timing"]
    assert receipt["role"] == "train"
    timing = json.loads((ROOT / receipt["path"]).read_text(encoding="utf-8"))
    record = next(
        row for row in timing if row["role"] == "train" and row["tag"] == receipt["tag"]
    )
    assert record["n"] == receipt["n"] == 400
    assert record["first_s"] == pytest.approx(receipt["first_batch_wall_s"])
    assert record["steady_s"] == pytest.approx(receipt["steady_batch_wall_s"])
    assert receipt["single_query_p95_wall_s"] is None
    assert receipt["v3_applicability"] == "NOT_DEMONSTRATED"
    producer = (ROOT / receipt["producer"]).read_text(encoding="utf-8")
    assert "m.predict(x)" in producer and '"steady_s": t2 - t1' in producer
