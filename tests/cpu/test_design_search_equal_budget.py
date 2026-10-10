"""Toy-only replay tests: no Challenge physics or reference execution."""

import copy
import json

import pytest

from carbon.design_search import equal_budget as eb


def panel(challenge="motor", direction="min"):
    jobs = []
    for index in range(4):
        candidates = []
        for design_id, value, model_rank, baseline_rank in (
            ("a", 3.0, 2, 0),
            ("b", 2.0, 1, 2),
            ("c", 1.0, 0, 1),
        ):
            reference = {"status": "FEASIBLE", "value": value}
            if challenge == "battery-v3":
                reference["per_index"] = {
                    band: {"status": "FEASIBLE", "value": value}
                    for band in ("5", "15", "25", "35", "40")
                }
            candidates.append(
                {
                    "design_id": design_id,
                    "reference": reference,
                    "solve_cost": {"wall_s": 2, "core_s": 4},
                    "planning_bound": {"wall_s": 2, "core_s": 4},
                    "screen_rank": {"model": model_rank, "baseline": baseline_rank},
                }
            )
        jobs.append(
            {
                "job_id": f"toy-{index}",
                "cluster_id": f"bank-{index // 2}",
                "candidates": candidates,
                "solver_order": ["a", "b", "c"],
                "screen_cost": {
                    "model": {"wall_s": 0.2, "core_s": 0.2},
                    "baseline": {"wall_s": 0.2, "core_s": 0.2},
                },
            }
        )
    return eb.seal(
        {
            "schema": eb.SCHEMA,
            "evidence_class": "DEVELOPMENT",
            "challenge": challenge,
            "source_digest": "sha256:" + "a" * 64,
            "decision_rule_id": "toy-rule-v1",
            "objective": {
                "direction": direction,
                "unit": "toy-units",
                **(
                    {
                        "index_weights": {
                            band: 0.2 for band in ("5", "15", "25", "35", "40")
                        }
                    }
                    if challenge == "battery-v3"
                    else {}
                ),
            },
            "cost_basis": "ASSUMPTION",
            "execution_plan": "SERIAL_COMPLETE_PANELS",
            "registrations": {
                "solver_search": "toy-order-v1",
                "model_screen": "toy-screen-v1",
                "baseline_screen": "toy-baseline-v1",
                "cost_plan": "toy-cost-bound-v1",
            },
            "budgets": [
                {"wall_s": 2, "core_s": 4},
                {"wall_s": 4, "core_s": 8},
                {"wall_s": 7, "core_s": 14},
            ],
            "jobs": jobs,
        }
    )


@pytest.mark.parametrize("challenge", ["battery-v3", "motor", "f02"])
def test_three_arms_budget_and_paired_bootstrap(challenge):
    report = eb.compare(
        panel(challenge), bootstrap_replicates=200, confidence=0.95, seed=7
    )
    assert report["status"] == "OK"
    assert report["independent_clusters"] == 2
    first = report["curves"][0]
    assert first["estimates"]["model_then_solver"]["feasible_pick_fraction"] == 0
    assert (
        first["estimates"]["solver_alone"]["mean_best_verified_value_conditional"] == 3
    )
    assert first["estimates"]["p_model_beats_solver"] == 0
    second = report["curves"][1]
    assert (
        second["estimates"]["model_then_solver"]["mean_best_verified_value_conditional"]
        == 1
    )
    assert second["estimates"]["model_then_solver"]["mean_regret_conditional"] == 0
    assert (
        second["estimates"]["baseline_then_solver"][
            "mean_best_verified_value_conditional"
        ]
        == 3
    )
    assert second["estimates"]["p_model_beats_solver"] == 1
    assert second["bootstrap_ci"]["p_model_beats_solver"] == [1, 1]
    assert report == eb.compare(
        panel(challenge), bootstrap_replicates=200, confidence=0.95, seed=7
    )


def test_compute_budget_is_independent_of_wall_budget():
    body = {k: v for k, v in panel().items() if k != "panel_digest"}
    body["budgets"] = [{"wall_s": 99, "core_s": 3}]
    result = eb.compare(
        eb.seal(body), bootstrap_replicates=100, confidence=0.95, seed=1
    )
    assert (
        result["curves"][0]["estimates"]["solver_alone"]["feasible_pick_fraction"] == 0
    )


def test_screen_cannot_overrun_budget_before_verification():
    body = {k: v for k, v in panel().items() if k != "panel_digest"}
    body["budgets"] = [{"wall_s": 2, "core_s": 4}]
    for job in body["jobs"]:
        job["screen_cost"]["model"] = {"wall_s": 3, "core_s": 1}
    report = eb.compare(
        eb.seal(body), bootstrap_replicates=100, confidence=0.95, seed=1
    )
    model = report["curves"][0]["estimates"]["model_then_solver"]
    assert model["over_budget_before_search_fraction"] == 1
    assert model["mean_verified_count"] == 0


def test_unresolved_reference_blocks_every_curve():
    body = {k: v for k, v in panel().items() if k != "panel_digest"}
    body["jobs"][0]["candidates"][0]["reference"] = {
        "status": "UNRESOLVED",
        "value": None,
    }
    result = eb.compare(
        eb.seal(body), bootstrap_replicates=100, confidence=0.95, seed=1
    )
    assert result["status"] == "UNRESOLVED_PANEL"
    assert result["unresolved_candidates"] == 1
    assert result["curves"] == []


def test_cannot_choose_solver_order_from_missing_or_duplicate_points():
    body = {k: v for k, v in panel().items() if k != "panel_digest"}
    body["jobs"][0]["solver_order"] = ["a", "b", "b"]
    with pytest.raises(eb.EqualBudgetError, match="solver order"):
        eb.compare(eb.seal(body), bootstrap_replicates=100, confidence=0.95, seed=1)


def test_planning_bound_and_digest_fail_closed():
    source = panel()
    tampered = copy.deepcopy(source)
    tampered["jobs"][0]["candidates"][0]["reference"]["value"] = 999
    with pytest.raises(eb.EqualBudgetError, match="digest"):
        eb.compare(tampered, bootstrap_replicates=100, confidence=0.95, seed=1)
    body = {k: v for k, v in panel().items() if k != "panel_digest"}
    body["jobs"][0]["candidates"][0]["planning_bound"]["core_s"] = 3
    with pytest.raises(eb.EqualBudgetError, match="planning bound"):
        eb.compare(eb.seal(body), bootstrap_replicates=100, confidence=0.95, seed=1)


def test_parallel_wall_time_is_not_silently_added():
    body = {k: v for k, v in panel().items() if k != "panel_digest"}
    body["execution_plan"] = "PARALLEL"
    with pytest.raises(eb.EqualBudgetError, match="serial complete-panel"):
        eb.compare(eb.seal(body), bootstrap_replicates=100, confidence=0.95, seed=1)


def test_one_bank_has_no_confidence_interval():
    body = {k: v for k, v in panel().items() if k != "panel_digest"}
    for job in body["jobs"]:
        job["cluster_id"] = "one-bank"
    report = eb.compare(
        eb.seal(body), bootstrap_replicates=100, confidence=0.95, seed=1
    )
    assert report["independent_clusters"] == 1
    assert all(curve["bootstrap_ci"] is None for curve in report["curves"])


def test_indexed_any_band_breach_cannot_be_compensated():
    body = {k: v for k, v in panel("battery-v3").items() if k != "panel_digest"}
    reference = body["jobs"][0]["candidates"][2]["reference"]
    reference["per_index"]["40"] = {"status": "INFEASIBLE", "value": None}
    with pytest.raises(eb.EqualBudgetError, match="any-band breach"):
        eb.compare(eb.seal(body), bootstrap_replicates=100, confidence=0.95, seed=1)
    reference["status"] = "INFEASIBLE"
    reference["value"] = None
    report = eb.compare(
        eb.seal(body), bootstrap_replicates=100, confidence=0.95, seed=1
    )
    assert report["status"] == "OK"


def test_maximization_regret_uses_buyer_units():
    report = eb.compare(
        panel("f02", "max"), bootstrap_replicates=100, confidence=0.95, seed=1
    )
    second = report["curves"][1]["estimates"]
    assert second["solver_alone"]["mean_regret_conditional"] == 0
    assert second["model_then_solver"]["mean_regret_conditional"] == 2


def test_cli_prints_aggregates_without_ids(tmp_path, capsys):
    source = tmp_path / "toy-panel.json"
    source.write_text(json.dumps(panel()), encoding="utf-8")
    eb.main(
        [
            str(source),
            "--bootstrap-replicates",
            "100",
            "--confidence",
            "0.95",
            "--seed",
            "1",
        ]
    )
    output = capsys.readouterr().out
    assert '"status": "OK"' in output
    assert "toy-0" not in output and "bank-0" not in output
    assert '"design_id"' not in output
