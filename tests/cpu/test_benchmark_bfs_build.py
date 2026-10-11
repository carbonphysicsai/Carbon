"""Synthetic/public preparation checks; no solves, spend or reference claims."""

import copy
import itertools
import json
from pathlib import Path

import pytest
from test_portfolio_baselines import fixture

from carbon.challenge_pipeline import benchmark_bfs as b
from carbon.design_search import tasks
from carbon.development_comparison import bfs_baselines as baseline


def seal(data):
    return {**data, "registration_digest": tasks.digest(data)}


def register():
    return seal(
        {
            "family": b.FAMILY,
            "scope": "SYNTHETIC_FIXTURE",
            "grammar": {
                "interior_dofs": 3,
                "ordinate_step_over_H": 0.01,
                "wall_ordinates_over_H": [-1, 0],
                "recovery_length_over_H": [0.5, 4],
                "length_step_over_H": 0.1,
            },
            "conditions": {
                "Re_H": [28800, 43200],
                "Mach": [0.1, 0.2],
                "inlet_thickness_over_H": [1.35, 1.65],
            },
            "diagnostic_pools": {
                k: [{"Re_H": 36000, "Mach": 0.128, "inlet_thickness_over_H": 1.5}]
                for k in ("frontier", "transition")
            },
        }
    )


def test_actions_deterministic_unique_monotone_and_non_dispatchable():
    r = register()
    result = b.actions(r, seed=31, count=20)
    assert result == b.actions(r, seed=31, count=20)
    assert not result["dispatchable"]
    assert len({tasks.digest(a) for a in result["actions"]}) == 20
    for a in result["actions"]:
        c = b.contour(a)
        assert c[0][1] == -1 and c[-1][1] == 0
        assert all(x[1] <= y[1] for x, y in itertools.pairwise(c))


@pytest.mark.parametrize(
    "field,value",
    [
        ("interior_dofs", None),
        ("ordinate_step_over_H", 0),
        ("wall_ordinates_over_H", [0, 0]),
    ],
)
def test_absent_registration_never_invents_grammar(field, value):
    r = register()
    r["grammar"][field] = value
    r = seal({k: v for k, v in r.items() if k != "registration_digest"})
    with pytest.raises(b.PreparationError):
        b.actions(r, seed=0, count=1)


def test_scope_and_registration_tamper_fail():
    r = register()
    r["scope"] = "HIDDEN_EVAL"
    with pytest.raises(b.PreparationError):
        b.conditions(r, seed=0, count=10)


def test_p_q_w_no_redraw_and_exact_diagnostic_allocation():
    r = register()
    p = b.conditions(r, seed=12, count=20)
    assert all(x["draw_role"] == "population" for x in p["rows"])
    q = b.conditions(r, seed=12, count=20, proposal="Q")
    assert {k: sum(x["draw_role"] == k for x in q["rows"]) for k in b.Q} == {
        "nominal": 8,
        "corners": 4,
        "frontier": 6,
        "transition": 2,
    }
    assert q["none_feasible"] == "RETAIN_NO_REDRAW"
    assert q["w"] != q["Q"]
    with pytest.raises(b.PreparationError):
        b.conditions(r, seed=0, count=8, proposal="Q")


def test_absent_frontier_pool_is_a_hold_not_fake_enrichment():
    r = register()
    r.pop("registration_digest")
    r["diagnostic_pools"] = {}
    with pytest.raises(b.PreparationError):
        b.conditions(seal(r), seed=0, count=10, proposal="Q")


def test_continuous_questions_are_full_briefs_not_field_samples():
    r = register()
    r.pop("registration_digest")
    r["requirement_law"] = {
        "public_calibration_sha256": "a" * 64,
        "reattachment_max_over_H": [5, 7],
        "service_points_per_brief": 2,
        "duty_weights": [0.4, 0.6],
    }
    q = b.questions(seal(r), seed=6, count=8)
    assert len(q["questions"]) == 8 and q["exposure_E"] == 1
    assert all(len(x["conditions"]) == 2 for x in q["questions"])
    assert (
        len({x["requirements"]["reattachment_max_over_H"] for x in q["questions"]}) == 8
    )
    assert q["none_feasible"] == "RETAIN_NO_REDRAW"
    with pytest.raises(b.PreparationError):
        b.questions(seal(r), seed=6, count=None)


def test_novelty_uses_descriptor_distance_not_a_producer_boolean():
    m = {"cutoff": 0.2, "measurement_sha256": "a" * 64, "catalogue_sha256": "b" * 64}
    assert b.geometry_distance_audit([0.8, 0.8], [[0, 0]], m)["outside"]
    assert not b.geometry_distance_audit([0.1, 0.1], [[0, 0]], m)["outside"]
    result = b.decision_novelty(
        b.FAMILY,
        {
            "scope": "PUBLIC_DEVELOPMENT",
            "rows": [
                {"id": "fake", "geometry_novel": True, "threshold_measurement": m}
            ],
        },
    )
    assert result["rows"][0]["status"] == "UNRESOLVED_GEOMETRY_RULE"


def test_calibration_requires_contested_frontier_and_answer_changes():
    designs = [
        {
            "design": str(i),
            "feasible": i < 5,
            "margin": (-1 if i >= 5 else 1),
            "objective": i,
        }
        for i in range(10)
    ]
    other = copy.deepcopy(designs)
    other[1]["objective"] = -1
    report = b.calibration_check(
        {"a": designs, "b": other},
        minimum_useful_improvement=1,
        minimum_margin_spread=2,
    )
    assert report["status"] == "CALIBRATION_PASSES"
    assert report["distinct_winners"] == ["0", "1"]
    close = copy.deepcopy(designs)
    close[1]["objective"] = -0.2
    memorized = b.calibration_check(
        {"a": designs, "b": close},
        minimum_useful_improvement=1,
        minimum_margin_spread=2,
    )
    assert memorized["status"] == "CALIBRATION_FAILS" and memorized[
        "common_value_equivalent_pick"
    ] == ["0"]
    assert (
        b.calibration_check(
            {"a": designs}, minimum_useful_improvement=1, minimum_margin_spread=2
        )["status"]
        == "CALIBRATION_FAILS"
    )
    other[0]["feasible"] = None
    assert (
        b.calibration_check(
            {"a": other}, minimum_useful_improvement=1, minimum_margin_spread=2
        )["status"]
        == "UNRESOLVED"
    )


def plane(p=100000, velocity=10):
    return [
        {
            "rho_kg_m3": 1.2,
            "p_static_pa": p,
            "u_m_s": velocity,
            "v_m_s": 0,
            "u_normal_m_s": velocity,
            "area_m2": 0.01,
        }
    ]


def test_observer_uses_mass_total_pressure_not_shifted_cp_and_exposes_reverse():
    result = b.observe(
        plane(),
        plane(99000),
        {"x_over_H": [0, 1, 2], "signed_cf": [-1, -1, 1]},
        gamma=1.4,
        rho_ref=1.2,
        u_ref=10,
    )
    assert result["loss_pa"] == pytest.approx(1000, abs=0.01)
    assert result["reattachment_over_H"] == 1.5
    assert result["mass_residual_fraction"] == 0
    outlet = plane(99000) + plane(99000, -1)
    assert b.plane_observer(outlet, gamma=1.4)["reverse_flow_detected"]
    with pytest.raises(b.PreparationError):
        b.plane_observer(plane(99000, -10), gamma=1.4)


def test_wall_root_policy_does_not_claim_unobserved_reattachment():
    assert b.reattachment([0, 1, 2], [-1, 0, 1])["status"] == "UNRESOLVED"
    assert b.reattachment([0, 1, 2], [-1, -1, -1])["reattachment_over_H"] is None
    assert b.reattachment([0, 1, 2], [1, 1, 1])["reattachment_over_H"] == 0
    assert (
        b.reattachment([0, 1, 2, 3, 4], [-1, 1, -1, -1, 1])["reattachment_over_H"]
        == 3.5
    )


def test_deck_binds_inlet_and_sst_mapping_without_claiming_valid_package():
    physical = {
        "mesh_file": "case.su2",
        "inlet_file": "inlet.dat",
        "sst_options": "V1994m",
        "H_m": 0.01,
        "outlet_static_pa": 100000,
        "inlet_total_temperature_k": 300,
        "inlet_total_pressure_pa": 101000,
        "inlet_plane_x_over_H": -4,
        "exit_plane_x_over_H": 40,
        **{k: "a" * 64 for k in ("mesh_sha256", "inlet_sha256", "sst_mapping_sha256")},
    }
    action = b.actions(register(), seed=0, count=1)["actions"][0]
    condition = b.conditions(register(), seed=0, count=1)["rows"][0]["condition"]
    d = b.deck(action, condition, physical)
    assert "KIND_TURB_MODEL= SST" in d["config"]
    assert "SPECIFIED_INLET_PROFILE= YES" in d["config"]
    assert not d["dispatchable"]
    physical["inlet_file"] = "../../private.dat"
    with pytest.raises(b.PreparationError):
        b.deck(action, condition, physical)


def test_train_disjointness_ignores_rung_and_domain_reports_gaps():
    panel = [
        {
            "action": {"length_over_H": 2},
            "condition": {"Re_H": 36000},
            "rung": 0,
            "scope": "SYNTHETIC_FIXTURE",
        }
    ]
    generated = [
        dict(panel[0], rung=2),
        {
            "action": {"length_over_H": 3},
            "condition": {"Re_H": 36000},
            "scope": "SYNTHETIC_FIXTURE",
        },
    ]
    plan = b.train_plan(b.FAMILY, generated, panel, count=1)
    assert plan["cases"] == [generated[1]]
    assert plan["scope"] == "SYNTHETIC_FIXTURE"
    domain = {
        "action": {"length_over_H": [0.5, 4]},
        "condition": {"Re_H": [28800, 43200]},
        "observables": ["loss_pa", "reattachment_over_H", "exit_reverse_flow"],
    }
    assert b.domain_coverage(b.FAMILY, panel, domain)["covered"]
    domain["condition"] = {}
    assert not b.domain_coverage(b.FAMILY, panel, domain)["covered"]
    with pytest.raises(b.PreparationError):
        b.train_plan(
            b.FAMILY, [dict(generated[1], scope="HIDDEN_EVAL")], panel, count=1
        )


def test_public_anchor_run_cannot_fake_variant_novelty():
    root = Path(__file__).resolve().parents[2]
    data = json.loads(
        (
            root
            / "docs/development/challenge_pipeline/benchmark-readiness/bfs/public-anchor-novelty-input.json"
        ).read_text()
    )
    result = b.decision_novelty(b.FAMILY, data)
    assert result["rows"][0]["status"] == "PUBLIC_ANCHOR_EXCLUDED"
    assert not result["hidden_bank_authorized"]
    data["scope"] = "HIDDEN_EVAL"
    with pytest.raises(b.PreparationError):
        b.decision_novelty(b.FAMILY, data)


def test_refinement_orders_are_numeric_not_boolean_pass_flags():
    rows = [{"h": 1 / n, "error_l2": 1 / n**2} for n in (16, 32, 64)]
    assert b.observed_orders(rows, [1.8, 2.2])["inside_supplied_band"]
    rows[-1]["error_l2"] = 0
    with pytest.raises(b.PreparationError):
        b.observed_orders(rows, [1.8, 2.2])


def test_symbolic_mms_defines_all_conserved_sources_not_sst_verification():
    pytest.importorskip("sympy")
    derived = b.manufactured_sources()
    assert len(derived["sources"]) == 4
    x, y = derived["coordinates"]
    rho, u, v, _ = derived["primitive"]
    assert derived["sources"][0] == (rho * u).diff(x) + (rho * v).diff(y)
    assert derived["scope"] == "LAMINAR_SUBSYSTEM_ONLY"


def test_coarse_rans_heldout_comparator_and_screening_cost_export():
    export, _ = fixture("cooling-cell")
    export.pop("export_digest")
    export.update(scope="SYNTHETIC_FIXTURE", family=b.FAMILY)
    export["export_digest"] = tasks.digest(export)
    material = {
        "export_digest": export["export_digest"],
        "coordinate_fields": ["coordinate"],
        "rows": [],
    }
    for i, r in enumerate(export["questions"][0]["reference"]):
        material["rows"].append(
            {
                **r,
                "geometry_id": r["candidate"],
                "coordinates": [i],
                "coarse_values": r["values"],
                "coarse_source": "coarse" + str(i),
                "fine_source": "fine" + str(i),
            }
        )
    report = baseline.measure(export, material=material)
    assert (
        report["pointwise"]["predicted_rows"] == 3
    )  # endpoints abstain, no extrapolation
    assert report["equal_budget_screening"]["candidate_rankings"]
    assert report["equal_budget_screening"]["query_cost"]["samples"] == 5
    assert report["v4"].startswith("UNRESOLVED")
    material["rows"][0]["coarse_source"] = "fine1"
    with pytest.raises(ValueError):
        baseline.measure(export, material=material)


def test_pressure_correlation_cannot_replace_missing_separation_limits():
    r = baseline.sudden_expansion_loss(
        area_ratio=2,
        dynamic_pressure_pa=100,
        applicability={"geometry": "abrupt_expansion", "source": "fixture"},
    )
    assert r["loss_pa"] == 25 and r["reattachment_over_H"] is None
    with pytest.raises(baseline.cb.Unsupported):
        baseline.sudden_expansion_loss(
            area_ratio=2,
            dynamic_pressure_pa=100,
            applicability={"geometry": "recovery_spline", "source": "fixture"},
        )


def test_execution_lesson_is_in_the_validated_log_not_only_a_document_folder():
    from carbon.challenge_pipeline.lessons import LESSONS, validate

    p = LESSONS / "2026-10-11-bfs-preparation.json"
    assert validate(json.loads(p.read_text()), p.stem, {})["challenge"] == b.FAMILY


def duty_fixture():
    export, _ = fixture("cooling-cell")
    old = export["questions"][0]["task"]
    return tasks.task(
        "synthetic-duty-question",
        identity=old["identity"],
        conditions=[{"id": c, "stratum": "s"} for c in ("nominal", "rare")],
        strata={"s": {"p": 1, "q": 1, "w": 1}},
        candidates=old["candidates"],
        actions=old["actions"],
        objective={
            "quantity": "loss_pa",
            "unit": "Pa",
            "sense": "min",
            "aggregate": "mean",
        },
        limits=[
            {"quantity": "reattachment_over_H", "unit": "H", "op": "<=", "value": 6},
            {
                "quantity": "exit_reverse_flow",
                "unit": "fraction",
                "op": "<=",
                "value": 0,
            },
        ],
    )


def test_duty_cycle_changes_pick_not_per_point_limits_or_original_task():
    original = duty_fixture()
    registered = baseline.duty_task(original, {"nominal": 0.9, "rare": 0.1})
    candidates = original["candidates"]
    truth = {
        (c, cond): {"loss_pa": 100, "reattachment_over_H": 4, "exit_reverse_flow": 0}
        for c in candidates
        for cond in ("nominal", "rare")
    }
    a, bb = candidates[:2]
    truth[(a, "nominal")]["loss_pa"], truth[(a, "rare")]["loss_pa"] = 1, 30
    truth[(bb, "nominal")]["loss_pa"], truth[(bb, "rare")]["loss_pa"] = 10, 10
    assert tasks.select(original, tasks.assess(original, truth)) == bb
    transformed = baseline.duty_values(registered, truth)
    assert tasks.select(registered, tasks.assess(registered, transformed)) == a
    assert tasks.assess(registered, transformed)[a]["objective"] == pytest.approx(3.9)
    assert original["objective"]["quantity"] == "loss_pa"
    assert registered["task_digest"] != original["task_digest"]
    zero = baseline.duty_task(original, {"nominal": 1, "rare": 0})
    truth[(a, "rare")]["reattachment_over_H"] = 7
    assert (
        tasks.assess(zero, baseline.duty_values(zero, truth), reference=True)[a][
            "feasible"
        ]
        is False
    )
    truth.pop((bb, "rare"))
    assert (
        tasks.assess(zero, baseline.duty_values(zero, truth), reference=True)[bb][
            "feasible"
        ]
        is None
    )


@pytest.mark.parametrize(
    "weights",
    [
        {"nominal": 1},
        {"nominal": -0.1, "rare": 1.1},
        {"nominal": True, "rare": 0},
        {"nominal": 0.4, "rare": 0.4},
    ],
)
def test_duty_weights_missing_negative_boolean_or_unnormalized_fail_closed(weights):
    with pytest.raises(ValueError):
        baseline.duty_task(duty_fixture(), weights)


def test_duty_transform_refuses_an_uncompiled_objective_and_prescaled_source():
    task = duty_fixture()
    with pytest.raises(ValueError, match="duty-compiled"):
        baseline.duty_values(task, {})
    task.pop("task_digest")
    task["secondary"] = {
        "quantity": baseline.DUTY_QUANTITY,
        "unit": "Pa",
        "sense": "min",
        "aggregate": "mean",
    }
    task["task_digest"] = tasks.digest(task)
    with pytest.raises(ValueError, match="raw source"):
        baseline.duty_task(task, {"nominal": 0.9, "rare": 0.1})


def test_duty_comparator_has_matched_decision_and_equal_budget_rankings():
    task = duty_fixture()
    reference = [
        {
            "candidate": c,
            "condition": cond,
            "values": {
                "loss_pa": i + 1 if cond == "nominal" else 20 - 2 * i,
                "reattachment_over_H": 4,
                "exit_reverse_flow": 0,
            },
        }
        for i, c in enumerate(task["candidates"])
        for cond in ("nominal", "rare")
    ]
    export = {
        "scope": "SYNTHETIC_FIXTURE",
        "family": b.FAMILY,
        "questions": [
            {
                "case": "nominal-heavy",
                "task": task,
                "reference": reference,
                "duty_weights": {"nominal": 0.9, "rare": 0.1},
            },
            {
                "case": "rare-heavy",
                "task": task,
                "reference": reference,
                "duty_weights": {"nominal": 0.1, "rare": 0.9},
            },
        ],
    }
    export["export_digest"] = tasks.digest(export)
    material = {
        "export_digest": export["export_digest"],
        "coordinate_fields": ["coordinate"],
        "rows": [],
    }
    for r in reference:
        material["rows"].append(
            {
                "candidate": r["candidate"],
                "condition": r["condition"],
                "geometry_id": r["candidate"],
                "coordinates": [task["actions"][r["candidate"]]["coordinate"]],
                "coarse_values": r["values"],
                "coarse_source": "coarse:" + r["candidate"],
                "fine_source": "fine:" + r["candidate"],
            }
        )
    report = baseline.measure(export, material=material)
    assert report["objective_coverage"] == "REGISTERED_DUTY_WEIGHTED_COMPLETE_BRIEF"
    ranks = report["equal_budget_screening"]["per_brief"]
    assert (
        ranks[0]["candidate_rankings"][0]["objective"]["quantity"]
        == baseline.DUTY_QUANTITY
    )
    assert (
        ranks[0]["candidate_rankings"][0]["ranked_feasible"][0]["candidate"]
        != ranks[1]["candidate_rankings"][0]["ranked_feasible"][0]["candidate"]
    )
    assert (
        ranks[0]["candidate_rankings"][0]["task_digest"]
        != ranks[1]["candidate_rankings"][0]["task_digest"]
    )
    assert report["pointwise"]["predicted_rows"] == 6
