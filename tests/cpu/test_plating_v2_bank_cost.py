"""Planning arithmetic on public D3 only; future bank mix is not observed."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts.dev.battery import plating_v2_bank_cost as cost


@pytest.fixture
def public_d3():
    values = {}
    for name, digest in cost.INPUT_SHA256.items():
        raw = (cost.D3 / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        values[name] = (
            [json.loads(line) for line in raw.splitlines()]
            if name.endswith(".jsonl")
            else json.loads(raw)
        )
    return values


def _plan(files, **kwargs):
    return cost.plan_cost(
        files["labels-v2-r1.json"],
        files["records.jsonl"],
        pdd_total=kwargs.get("pdd_total", 8390),
        action_condition_solves=kwargs.get("action_condition_solves", 1000),
    )


def test_full_v2_window_includes_pending_pdd_not_just_solved(public_d3):
    result = _plan(public_d3)
    assert result["source_counts"] == {
        "pdd_solved": 611,
        "pdd_pending": 84,
        "ev4_solved": 58,
        "ev4_pending": 19,
    }
    assert result["full_v2_window_share"] == pytest.approx(695 / 8390)
    assert result["full_v2_window_share"] > 611 / 8390
    assert result["measured_count"] == {"40": 67, "80": 67, "160": 669}
    assert result["incremental_plating_cpu_h_at_observed_share"] == pytest.approx(
        6.796357196271167
    )
    assert result["incremental_plating_cpu_h_if_all_in_window"] == pytest.approx(
        82.0452329161368
    )
    assert result["base_reference_cpu_h_if_supplied"] is None
    assert "case_id" not in json.dumps(result)
    assert all(
        row["case_id"].startswith("ev4:")
        for row in public_d3["labels-v2-r1.json"]["rows"]
    )


def test_pre_v2_rule_refused_even_with_same_margin(public_d3):
    files = copy.deepcopy(public_d3)
    files["labels-v2-r1.json"]["rows"][0]["rule"] = "m160-d3"
    with pytest.raises(cost.CostRefused, match="v2_rule_or_source"):
        _plan(files)


def test_changed_label_refused(public_d3):
    files = copy.deepcopy(public_d3)
    row = next(
        row for row in files["labels-v2-r1.json"]["rows"] if row["label"] == "FEASIBLE"
    )
    row["label"] = "INFEASIBLE"
    with pytest.raises(cost.CostRefused, match="v2_label_mismatch"):
        _plan(files)


def test_missing_cost_rung_refused(public_d3):
    files = copy.deepcopy(public_d3)
    files["records.jsonl"] = [
        row for row in files["records.jsonl"] if row["mesh"] != 40
    ]
    with pytest.raises(cost.CostRefused, match="cost_coverage"):
        _plan(files)


@pytest.mark.parametrize("denominator", [0, 694, True])
def test_bad_denominator_refused(public_d3, denominator):
    with pytest.raises(cost.CostRefused):
        _plan(public_d3, pdd_total=denominator)


def test_cost_scales_with_actual_solve_count(public_d3):
    one = _plan(public_d3, action_condition_solves=1000)
    two = _plan(public_d3, action_condition_solves=2000)
    assert two["incremental_plating_cpu_h_at_observed_share"] == pytest.approx(
        2 * one["incremental_plating_cpu_h_at_observed_share"]
    )
