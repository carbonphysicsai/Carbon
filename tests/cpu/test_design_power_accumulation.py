"""Toy-only producer power accumulation; no Challenge or hidden material."""

from __future__ import annotations

import json

import pytest

from carbon.design_search import controls, diversity, power, power_accumulation, tasks


def _question(case, support):
    registered = tasks.task(
        case,
        identity={
            "challenge": "toy-power",
            "contract_version": "v1",
            "action_grammar": {
                "schema": tasks.GRAMMAR_SCHEMA,
                "version": "toy-power.v1",
                "variables": [
                    {"name": "choice", "type": "integer", "min": 0, "max": 1, "step": 1}
                ],
                "rules": [],
            },
            "optimizer": {"class": "exhaustive", "version": "v1"},
            "query_budget": 2,
            "seed": 9,
            "observer_version": "toy-power-observer.v1",
            "reference_bank": support,
        },
        conditions=[{"id": "condition", "stratum": "only"}],
        strata={"only": {"p": 1, "q": 1, "w": 1}},
        candidates=["safe", "unsafe"],
        actions={"safe": {"choice": 0}, "unsafe": {"choice": 1}},
        objective={
            "quantity": "cost",
            "unit": "toy-unit",
            "sense": "min",
            "aggregate": "worst",
        },
        limits=[{"quantity": "margin", "unit": "toy-unit", "op": ">=", "value": 0}],
    )
    reference = [
        {
            "candidate": "safe",
            "condition": "condition",
            "values": {"cost": 1.0, "margin": 1.0},
        },
        {
            "candidate": "unsafe",
            "condition": "condition",
            "values": {"cost": 0.0, "margin": -0.1},
        },
    ]
    return registered, reference


def _fixture(*, banks=6, exposure_limit=2, shared_bank=False):
    cases = []
    power_cases = []
    good_cases = []
    exposure = []
    for number in range(banks):
        case = f"PRIVATE-CASE-{number}"
        support = "PRIVATE-SHARED-BANK" if shared_bank else f"PRIVATE-BANK-{number}"
        registered, reference = _question(case, support)
        cases.append(
            {
                "case": case,
                "state": "FEASIBLE_EXISTS",
                "winner": "safe",
                "close_call": False,
                "refinement_demand": False,
            }
        )
        power_cases.append(
            {
                "case": case,
                "support_case": support,
                "task": registered,
                "reference": reference,
            }
        )
        good_cases.append({"case": case, "predictions": reference})
        exposure.append({"case": case, "limit": exposure_limit, "used": 0})
    bank = diversity.seal_bank(
        {
            "schema": diversity.BANK_SCHEMA,
            "sealed": True,
            "exposure_unit": power_accumulation.EXPOSURE_UNIT,
            "case_exposure": exposure,
            "cases": cases,
            "power_cases": power_cases,
            "private_marker": "DO_NOT_EXPORT_PRIVATE_MARKER",
        }
    )
    law = diversity.register_law(
        {
            "schema": diversity.LAW_SCHEMA_V2,
            "population_status": "UNREGISTERED",
            "kind": "grid",
            "draw_model": "iid_with_replacement",
            "batch_size": 2,
            "bins": [{"case": row["case"], "q_mass": 1 / banks} for row in cases],
            "mass_l1_error_bound": 0.0,
        }
    )
    registration = controls.register_controls(
        [
            {
                "schema": controls.CONTROL_SCHEMA,
                "name": "edge",
                "kind": "edge_optimist",
                "severity": {"margin": {"value": 0.2, "unit": "toy-unit"}},
                "limit_quantities": ["margin"],
            }
        ]
    )
    return bank, law, registration, power.register_good_predictor(good_cases)


def test_q_only_law_never_fabricates_population_measure():
    bank, law, controls_, good = _fixture()
    report = power.power_report(
        bank,
        law,
        None,
        controls_,
        good,
        alpha=0.05,
        power_target=0.8,
        simulation_seed=17,
        replicates=60,
        max_questions=4,
        accumulation=power_accumulation.register_accumulation(
            exposure_unit="per_question_draws", max_windows=2
        ),
    )
    assert report["laws"]["grid"]["P"] is None
    points = report["sealed_bank_cross_batch"]["controls"][0]["metrics"][
        "false_feasible"
    ]["points"]
    assert {(row["questions_per_batch"], row["windows"]) for row in points} == {
        (k, window) for k in range(1, 5) for window in (1, 2)
    }
    assert next(
        row for row in points if row["questions_per_batch"] == 4 and row["windows"] == 2
    )["exposure_feasible"]
    rendered = json.dumps(report)
    assert "PRIVATE-CASE" not in rendered
    assert "PRIVATE-BANK" not in rendered
    assert "DO_NOT_EXPORT_PRIVATE_MARKER" not in rendered


def test_cross_batch_retains_shared_bank_cluster_and_per_question_exposure():
    bank, law, controls_, good = _fixture(banks=1)
    accumulation = power_accumulation.register_accumulation(
        exposure_unit="per_question_draws", max_windows=3
    )
    report = power.power_report(
        bank,
        law,
        None,
        controls_,
        good,
        alpha=0.05,
        power_target=0.8,
        simulation_seed=17,
        replicates=30,
        max_questions=2,
        accumulation=accumulation,
    )
    points = report["sealed_bank_cross_batch"]["controls"][0]["metrics"][
        "false_feasible"
    ]["points"]
    assert all(
        row["estimated_detection_probability"] == 0
        for row in points
        if row["exposure_feasible"]
    )
    assert all(
        row["mean_nonzero_bank_clusters"] <= 1
        for row in points
        if row["exposure_feasible"]
    )
    assert (
        next(
            row
            for row in points
            if row["questions_per_batch"] == 1 and row["windows"] == 3
        )["estimated_detection_probability"]
        is None
    )
    with pytest.raises(tasks.TaskError, match="per-question"):
        power_accumulation.register_accumulation(
            exposure_unit="batch_windows", max_windows=2
        )


def test_q_only_registration_requires_explicit_absent_p():
    bank, law, _, _ = _fixture()
    altered = dict(law)
    altered["population_status"] = "REGISTERED"
    altered = diversity.register_law(
        {key: value for key, value in altered.items() if key != "registration_digest"}
    )
    with pytest.raises(tasks.TaskError, match="question bin"):
        diversity.diversity_report(bank, altered)
    v1 = diversity.register_law(
        {
            **{
                key: value for key, value in law.items() if key != "registration_digest"
            },
            "schema": diversity.LAW_SCHEMA,
        }
    )
    with pytest.raises(tasks.TaskError, match="question bin"):
        diversity.diversity_report(bank, v1)


def test_cross_batch_curve_replays_and_can_gain_power_from_distinct_banks():
    bank, _, _, _ = _fixture(banks=8)
    differences = {row["case"]: 1.0 for row in bank["cases"]}
    clusters = {row["case"]: row["support_case"] for row in bank["power_cases"]}
    arguments = {
        "alpha": 0.05,
        "target": 0.8,
        "seed": 19,
        "replicates": 200,
        "max_questions": 3,
        "accumulation": power_accumulation.register_accumulation(
            exposure_unit="per_question_draws", max_windows=4
        ),
    }
    first = power_accumulation.cross_batch_curve(
        bank["case_exposure"], differences, clusters, **arguments
    )
    assert first == power_accumulation.cross_batch_curve(
        bank["case_exposure"], differences, clusters, **arguments
    )
    one = next(
        point
        for point in first["points"]
        if point["questions_per_batch"] == 3 and point["windows"] == 1
    )
    four = next(
        point
        for point in first["points"]
        if point["questions_per_batch"] == 3 and point["windows"] == 4
    )
    assert one["estimated_detection_probability"] == 0
    assert (
        four["estimated_detection_probability"] > one["estimated_detection_probability"]
    )
    assert four["mean_nonzero_bank_clusters"] <= 8


def test_eight_questions_can_run_five_windows_at_e_five_per_question():
    bank, _, _, _ = _fixture(banks=8, exposure_limit=5, shared_bank=True)
    differences = {row["case"]: 1.0 for row in bank["cases"]}
    clusters = {row["case"]: row["support_case"] for row in bank["power_cases"]}
    curve = power_accumulation.cross_batch_curve(
        bank["case_exposure"],
        differences,
        clusters,
        alpha=0.05,
        target=0.8,
        seed=4,
        replicates=20,
        max_questions=8,
        accumulation=power_accumulation.register_accumulation(
            exposure_unit="per_question_draws", max_windows=5
        ),
    )
    point = next(
        row
        for row in curve["points"]
        if row["questions_per_batch"] == 8 and row["windows"] == 5
    )
    assert point["exposure_feasible"]
    assert point["estimated_detection_probability"] == 0
    assert point["mean_nonzero_bank_clusters"] == 1
