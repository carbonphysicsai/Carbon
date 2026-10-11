"""Synthetic arithmetic and deck syntax, not solver or scientific adequacy."""

import ast
import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest
from test_portfolio_baselines import fixture

from carbon.challenge_pipeline import benchmark_mg as b
from carbon.challenge_pipeline import metagrating_decks as decks
from carbon.design_search import (
    budget_registration,
    equal_budget,
    metagrating_budget,
    tasks,
)
from carbon.development_comparison import metagrating_baselines as baseline


def seal(data):
    return {**data, "registration_digest": tasks.digest(data)}


def law():
    req = {
        "efficiency_min": [0.5, 0.8],
        "reflection_max": [0.05, 0.2],
        "unwanted_max": [0.05, 0.3],
    }
    diagnostic = {
        "angle_deg": 50,
        "requirements": {k: sum(v) / 2 for k, v in req.items()},
    }
    return seal(
        {
            "family": b.FAMILY,
            "scope": "SYNTHETIC_FIXTURE",
            "grammar": {
                "nx": 8,
                "ny": 8,
                "tile_cells": 2,
                "reflection_y": True,
                "minimum_feature_nm": 100,
                "thickness_nm": [250, 400],
                "thickness_step_nm": 25,
            },
            "wavelength_nm": 1050,
            "n_silicon": 3.45,
            "n_substrate": 1.45,
            "deflection_angle_deg": [40, 60],
            "requirement_law": {
                "public_calibration_sha256": "a" * 64,
                "intervals": req,
            },
            "diagnostic_pools": {
                k: [diagnostic] for k in ("frontier", "transition", "library_failure")
            },
        }
    )


def hardware():
    return {
        "periods_nm": [1050 / math.sin(math.radians(50)), 525],
        "wavelength_nm": 1050,
        "n_in": 1.45,
        "n_out": 1,
        "minimum_feature_nm": 10,
    }


def action():
    return {
        "mask": [[1, 1, 0, 0], [1, 1, 0, 0], [0, 0, 1, 1], [0, 0, 1, 1]],
        "thickness_nm": 325,
    }


def controls():
    return {
        "package_spec_sha256": "a" * 64,
        "observer_sha256": "b" * 64,
        "grammar_sha256": "c" * 64,
        "resolution_per_um": 50,
        "eps_averaging": True,
        "pml_nm": 500,
        "guard_nm": 500,
        "source_fwidth_fraction": 0.1,
        "after_sources_time": 100,
        "num_basis": 49,
        "field_grid": 16,
    }


def test_actions_are_binary_two_direction_fixed_period_and_finite_z():
    result = b.actions(law(), seed=2, count=4, periods_nm=hardware()["periods_nm"])
    assert result == b.actions(
        law(), seed=2, count=4, periods_nm=hardware()["periods_nm"]
    )
    assert len({tasks.digest(a) for a in result["actions"]}) == 4
    for a in result["actions"]:
        assert b.feature_check(
            a["mask"], periods_nm=hardware()["periods_nm"], minimum_feature_nm=100
        )["passes_registered_run_rule"]
        assert all(row == list(reversed(row)) for row in a["mask"])
        assert len({tuple(row) for row in a["mask"]}) > 1
        assert len({tuple(col) for col in zip(*a["mask"])}) > 1
    assert not result["dispatchable"]


@pytest.mark.parametrize("change", ["hidden", "precision", "dispersion"])
def test_missing_or_unsupported_science_stays_closed(change):
    r = law()
    r.pop("registration_digest")
    if change == "hidden":
        r["scope"] = "HIDDEN_EVAL"
    elif change == "precision":
        r["grammar"]["minimum_feature_nm"] = None
    else:
        r["wavelength_nm"] = 1100
    with pytest.raises((b.PreparationError, TypeError)):
        if change == "precision":
            b.actions(seal(r), seed=0, count=1, periods_nm=hardware()["periods_nm"])
        else:
            b.briefs(seal(r), seed=0, count=20)


def test_p_q_w_full_brief_none_feasible_and_library_failure_allocation():
    p = b.briefs(law(), seed=0, count=20)
    assert len({r["requirements"]["efficiency_min"] for r in p["briefs"]}) == 20
    assert all(len(r["conditions"]) == 1 for r in p["briefs"])
    q = b.briefs(law(), seed=1, count=40, proposal="Q")
    assert {k: sum(r["draw_role"] == k for r in q["briefs"]) for k in b.Q} == {
        "nominal": 16,
        "corners": 8,
        "frontier": 12,
        "transition": 4,
    }
    assert sum(r["library_failure_diagnostic"] for r in q["briefs"]) == 2
    assert q["none_feasible"] == "RETAIN_NO_REDRAW" and q["exposure_E"] == 1
    with pytest.raises(b.PreparationError):
        b.briefs(law(), seed=1, count=10, proposal="Q")
    r = law()
    r.pop("registration_digest")
    r["diagnostic_pools"] = {}
    with pytest.raises(b.PreparationError):
        b.briefs(seal(r), seed=1, count=20, proposal="Q")


def test_public_calibration_needs_each_contested_stratum_and_changed_winners():
    first = [
        {
            "design": str(i),
            "feasible": i < 5,
            "margin": 0.08 if i < 5 else -0.08,
            "efficiency": i / 20,
        }
        for i in range(10)
    ]
    second = copy.deepcopy(first)
    second[0]["efficiency"] = 1
    close = copy.deepcopy(first)
    close[0]["efficiency"] = 0.21
    memorized = b.calibration_check(
        {"a": first, "b": close},
        minimum_useful_improvement=0.05,
        minimum_margin_spread=0.1,
    )
    assert memorized["status"] == "CALIBRATION_FAILS" and memorized[
        "common_value_equivalent_pick"
    ] == ["4"]
    assert (
        b.calibration_check(
            {"a": first, "b": second},
            minimum_useful_improvement=0.05,
            minimum_margin_spread=0.1,
        )["status"]
        == "CALIBRATION_PASSES"
    )
    assert (
        b.calibration_check(
            {"a": first}, minimum_useful_improvement=0.05, minimum_margin_spread=0.1
        )["status"]
        == "CALIBRATION_FAILS"
    )
    second[0]["feasible"] = None
    assert (
        b.calibration_check(
            {"a": second}, minimum_useful_improvement=0.05, minimum_margin_spread=0.1
        )["status"]
        == "UNRESOLVED"
    )


def rows():
    h = hardware()
    return [
        {"side": side, "order": o, "co_power": 0, "cross_power": 0}
        for side, index in (("R", h["n_in"]), ("T", h["n_out"]))
        for o in b.propagating_orders(
            periods_nm=h["periods_nm"], wavelength_nm=1050, index=index
        )
    ]


def observe(data):
    h = hardware()
    return b.observe(
        data,
        periods_nm=h["periods_nm"],
        wavelength_nm=1050,
        n_in=h["n_in"],
        n_out=h["n_out"],
    )


def test_all_orders_cross_pol_residual_without_clipping_or_renormalizing():
    data = rows()
    for r in data:
        if r["side"] == "T" and r["order"] == [1, 0]:
            r.update(co_power=0.8, cross_power=0.02)
        if r["side"] == "R" and r["order"] == [0, 0]:
            r["co_power"] = 0.1
    result = observe(data)
    assert result["desired_efficiency"] == pytest.approx(0.82)
    assert result["desired_co_efficiency"] == 0.8
    assert result["desired_efficiency_pp"] == pytest.approx(82)
    assert result["cross_polarization"] == 0.02
    assert result["energy_residual"] == pytest.approx(0.08)
    assert result["unwanted_power"] == pytest.approx(0)
    with pytest.raises(b.PreparationError):
        observe(data[:-1])
    with pytest.raises(b.PreparationError):
        observe(data + [data[0]])
    data[0]["co_power"] = -0.01
    assert observe(data)["invalid_negative_power"]


def test_grazing_channel_is_unresolved_not_silently_absent():
    with pytest.raises(b.PreparationError):
        b.propagating_orders(periods_nm=[1050, 525], wavelength_nm=1050, index=1)


@pytest.mark.parametrize("side,sign", [("T", 1), ("R", -1)])
def test_field_projection_normalizes_outgoing_polarizations_with_direction(side, sign):
    e = np.zeros((8, 8, 3), dtype=complex)
    h = e.copy()
    e[..., 0] = 2
    e[..., 1] = 1
    h[..., 1] = sign * 2
    h[..., 0] = -sign
    projected = b.powers_from_fields(
        e,
        h,
        periods_nm=hardware()["periods_nm"],
        wavelength_nm=1050,
        index=1,
        side=side,
        incident_power=5,
    )
    zero = next(r for r in projected if r["order"] == [0, 0])
    assert zero["co_power"] == pytest.approx(0.8) and zero[
        "cross_power"
    ] == pytest.approx(0.2)
    assert sum(r["co_power"] + r["cross_power"] for r in projected) == pytest.approx(1)


def test_analytic_slab_and_zero_contrast_grating_are_exact_not_pattern_truth():
    for thickness in (100, 325, 500):
        r = b.slab_truth(
            n_in=1.45, n_layer=3.45, n_out=1, thickness_nm=thickness, wavelength_nm=1050
        )
        assert r["R"] + r["T"] == pytest.approx(1, abs=1e-14)
    r = b.slab_truth(n_in=1, n_layer=1, n_out=1, thickness_nm=325, wavelength_nm=1050)
    assert r["R"] == 0 and r["T"] == pytest.approx(1) and r["cross"] == 0
    assert b.observed_orders(
        [{"h": 1 / n, "error": 1 / n**2} for n in (20, 40, 80)], [1.8, 2.2]
    )["inside_supplied_band"]


@pytest.mark.parametrize("render", [decks.meep_deck, decks.s4_deck])
def test_deck_syntax_and_embedded_spec_without_importing_or_running_solver(render):
    deck = render(action(), hardware(), controls())
    tree = ast.parse(deck["python"])
    spec = next(
        n for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "SPEC"
    )
    assert json.loads(ast.literal_eval(spec.value.args[0]))["action"] == action()
    assert deck["status"] == "UNVERIFIED_DECK_DRAFT" and not deck["dispatchable"]
    assert (
        "rows" in deck["python"]
        and "cross_power" in deck["python"]
        or render == decks.s4_deck
    )
    bad = controls()
    bad["observer_sha256"] = None
    with pytest.raises(b.PreparationError):
        render(action(), hardware(), bad)


def test_memory_hypothesis_is_grid_arithmetic_not_measured_cost():
    r = decks.memory_hypothesis(hardware(), controls(), thickness_nm=325)
    assert r["cells"] > 0 and r["cpu_hours"] == "UNMEASURED"
    assert (
        r["field_storage_GiB_hypothesis"][2] == 4 * r["field_storage_GiB_hypothesis"][0]
    )


@pytest.mark.parametrize(
    "case", ["zero-contrast-periodic-grating", "planar-lossless-slab"]
)
def test_runnable_analytic_decks_do_not_broaden_physical_action_route(case):
    r = decks.verification_decks(case, controls())
    assert r["analytic_truth"]["R"] + r["analytic_truth"]["T"] == pytest.approx(1)
    for route in ("Meep", "S4"):
        ast.parse(r[route]["python"])
        assert not r[route]["dispatchable"]
    assert r["pass_band"] == "HUMAN_INPUT"


def test_analytic_numeric_checker_compares_retained_outputs_not_a_producer_pass_flag():
    case = "planar-lossless-slab"
    expected = decks.verification_decks(case, controls())["analytic_truth"]
    data = rows()
    for row in data:
        if row["order"] == [0, 0]:
            row["co_power"] = expected[row["side"]]
    acceptance = {
        "record_sha256": "a" * 64,
        "absolute_power_fraction": 0.001,
        "energy_residual_fraction": 0.001,
    }
    result = decks.verify_analytic_output(case, data, controls(), acceptance=acceptance)
    assert result["status"] == "WITHIN_SUPPLIED_BANDS" and not result["qualified"]
    data[0]["cross_power"] = 0.02
    assert (
        decks.verify_analytic_output(case, data, controls(), acceptance=acceptance)[
            "status"
        ]
        == "OUTSIDE_SUPPLIED_BANDS"
    )
    with pytest.raises(b.PreparationError):
        decks.verify_analytic_output(case, data[:-1], controls(), acceptance=acceptance)


def test_train_disjointness_ignores_rung_and_domain_is_not_claimed_from_geometry_only():
    h = hardware()
    row = {
        "action": action(),
        "hardware": h,
        "condition": {"wavelength_nm": 1050},
        "scope": "SYNTHETIC_FIXTURE",
        "grammar_digest": "a" * 64,
    }
    other = copy.deepcopy(row)
    other["action"]["thickness_nm"] = 350
    shifted = copy.deepcopy(row)
    shifted["action"]["mask"] = (
        shifted["action"]["mask"][1:] + shifted["action"]["mask"][:1]
    )
    plan = b.train_plan(
        b.FAMILY,
        [{**row, "rung": 2}, shifted, other],
        [row],
        count=1,
        allow_y_reflection=True,
    )
    assert plan["rows"][0]["action"]["thickness_nm"] == 350
    assert plan["rows"][0]["scope"] == "SYNTHETIC_FIXTURE"
    with pytest.raises(b.PreparationError):
        b.train_plan(
            b.FAMILY,
            [{**other, "scope": "HIDDEN_EVAL"}],
            [row],
            count=1,
            allow_y_reflection=True,
        )
    assert not b.domain_coverage(b.FAMILY, [row], {"support": {}})["covered"]


def test_translations_and_resampling_cannot_rescue_a_mask_copy():
    m = action()["mask"]
    shifted = m[1:] + m[:1]
    assert b.mask_distance(shifted, [m], allow_y_reflection=True) == 0
    with pytest.raises(b.PreparationError):
        b.mask_distance(m, [[[0, 1], [1, 0]]], allow_y_reflection=True)
    anchors = {
        "scope": "PUBLIC_DEVELOPMENT",
        "rows": [{"id": "source-1", "custody": "PUBLIC_REFERENCE_ANCHOR"}],
    }
    result = b.decision_novelty(b.FAMILY, anchors)
    assert result["rows"][0]["variant_decision_test"] == "UNRESOLVED_NO_VARIANT_TRUTH"
    anchors["scope"] = "HIDDEN_EVAL"
    with pytest.raises(b.PreparationError):
        b.decision_novelty(b.FAMILY, anchors)


@pytest.mark.parametrize("method", ["library_lookup", "library_rbf"])
def test_heldout_library_reports_decisions_regret_coverage_and_screening_cost(method):
    export, _ = fixture("cooling-cell")
    export.pop("export_digest")
    export.update(family=b.FAMILY, scope="SYNTHETIC_FIXTURE")
    export["export_digest"] = tasks.digest(export)
    material = {
        "export_digest": export["export_digest"],
        "coordinate_fields": ["coordinate"],
        "maximum_distance": 1.1,
        "rows": [],
    }
    for i, r in enumerate(export["questions"][0]["reference"]):
        material["rows"].append(
            {
                **r,
                "coordinates": [i],
                "pattern_group": r["candidate"],
                "library_source": "library" + str(i),
                "fine_source": "fine" + str(i),
                "library_values": r["values"],
            }
        )
    report = baseline.measure(export, material=material, method=method)
    assert report["pointwise"]["predicted_rows"] == (
        5 if method == "library_lookup" else 3
    )
    assert report["equal_budget_screening"]["candidate_rankings"]
    assert report["equal_budget_screening"]["query_cost"]["samples"] == 5
    assert report["v4"].startswith("UNRESOLVED")
    material["rows"][0]["library_source"] = "fine1"
    with pytest.raises(ValueError):
        baseline.measure(export, material=material)


def test_additive_budget_route_keeps_historical_registration_closed_and_enforces_caps():
    from test_design_search_equal_budget import panel

    path = Path(
        "docs/development/challenge_pipeline/benchmark-readiness/mg/equal-budget-proposal.json"
    )
    raw = json.loads(path.read_text())
    registered = metagrating_budget.validate(raw)
    assert (
        registered.cap(b.FAMILY, "half").wall_s
        == registered.cap(b.FAMILY, "base").wall_s / 2
    )
    assert (
        registered.cap(b.FAMILY, "double").core_s
        == registered.cap(b.FAMILY, "base").core_s * 2
    )
    with pytest.raises(budget_registration.BudgetRegistrationError):
        budget_registration.validate(raw)  # never reinterpret EQUAL-BUDGET-V1
    changed = copy.deepcopy(raw)
    changed["challenge_budgets"][b.FAMILY]["tiers"]["base"]["wall_s"] = 1
    with pytest.raises(budget_registration.BudgetRegistrationError):
        metagrating_budget.validate(changed)
    ledger = budget_registration.BudgetLedger(registered.cap(b.FAMILY, "half"))
    assert not ledger.charge_solver_attempt(
        {"wall_s": 8000, "core_s": 1}, {"wall_s": 8000, "core_s": 1}
    )
    report = equal_budget.compare(
        panel(b.FAMILY, direction="max"),
        bootstrap_replicates=100,
        confidence=0.95,
        seed=7,
    )
    assert report["status"] == "OK" and report["independent_clusters"] == 2
    toy = panel(b.FAMILY, direction="max")
    toy.pop("panel_digest")
    toy["budgets"] = [
        registered.cap(b.FAMILY, t).time_compute for t in budget_registration.TIERS
    ]
    toy["registrations"]["cost_plan"] = registered.registration_id
    result = equal_budget.compare(
        equal_budget.seal(toy),
        bootstrap_replicates=100,
        confidence=0.95,
        seed=7,
        registration=raw,
    )
    assert result["status"] == "OK"


def test_execution_lesson_is_in_the_validated_log_not_only_a_document_folder():
    from carbon.challenge_pipeline.lessons import LESSONS, validate

    p = LESSONS / "2026-10-11-mg-preparation.json"
    assert validate(json.loads(p.read_text()), p.stem, {})["challenge"] == b.FAMILY


def test_numeric_verification_requires_a_real_sha256_shape_not_only_length():
    with pytest.raises(b.PreparationError, match="acceptance identity"):
        decks.verify_analytic_output(
            "planar-lossless-slab",
            [],
            controls(),
            acceptance={
                "record_sha256": "z" * 64,
                "absolute_power_fraction": 0.001,
                "energy_residual_fraction": 0.001,
            },
        )


def test_train_cannot_publish_resampled_copies_or_choose_an_unregistered_symmetry():
    row = {
        "action": action(),
        "hardware": hardware(),
        "condition": {"wavelength_nm": 1050},
        "scope": "SYNTHETIC_FIXTURE",
    }
    changed = copy.deepcopy(row)
    changed["action"]["mask"] = [
        [v for v in r for _ in range(2)]
        for r in row["action"]["mask"]
        for _ in range(2)
    ]
    with pytest.raises(b.PreparationError, match="canonical physical mask"):
        b.train_plan(b.FAMILY, [changed], [row], count=1, allow_y_reflection=True)
    with pytest.raises(b.PreparationError):
        b.train_plan(b.FAMILY, [row], [], count=1, allow_y_reflection=None)
