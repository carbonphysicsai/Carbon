"""Synthetic fixtures and analytic fields; no CFD or protected inputs."""

import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest

from carbon.challenge_pipeline import micromixer_readiness as m
from carbon.challenge_pipeline.onboarding import evidence_readiness as er
from carbon.design_search import budget_registration as br
from carbon.design_search import equal_budget as eb
from carbon.design_search import micromixer_budget as mb
from carbon.design_search import tasks


def test_actions_full_finite_grammar_and_condition_counts():
    panel = m.proposed_panel()
    assert len(m.conditions()) == 9 and panel["case_count"] == 90
    assert len({tasks.digest(c) for c in panel["cases"]}) == 90
    assert panel["flow_starts_with_proved_reuse"] + panel["scalar_starts"] == 120
    assert panel["starts_without_reuse"] == 180
    assert panel["accepted_manifest_digest"] is None
    geometry = m.geometry_recipe(panel["designs"][4])
    assert geometry["base_box_um"] == [10000, 300, 100]
    assert not geometry["periodic_scalar_reset_allowed"]
    assert "DRAFT" in geometry["status"]


@pytest.mark.parametrize(
    "args",
    [
        (19, 175, 8),
        (41, 175, 8),
        (30, 99, 8),
        (30, 251, 8),
        (30, 175, 8.0),
        (30, 175, True),
        (float("nan"), 175, 8),
    ],
)
def test_invalid_action_is_not_generated(args):
    with pytest.raises(ValueError):
        m.action(*args)


def test_training_cannot_overlap_by_changing_rung_or_name():
    panel, train = m.proposed_panel(), m.train_plan()
    assert len(train["cases"]) == 18
    assert not {m.physical_key(c) for c in train["cases"]} & {
        m.physical_key(c) for c in panel["cases"]
    }
    panel["cases"].append(
        {**train["cases"][0], "rung": {"mesh_um": 2.5}, "id": "alias"}
    )
    with pytest.raises(ValueError, match="overlap"):
        m.train_plan(panel)


def test_kit_needs_raw_flux_and_finite_scalar_history():
    panel = m.proposed_panel()
    kit = {
        "scope": m.SCOPE,
        "physical_keys": [m.physical_key(c) for c in panel["cases"]],
        "observables": list(m.OBSERVABLES),
        "finite_scalar_history": True,
        "raw_flux_concentration": True,
    }
    assert m.kit_domain_check(kit)["covered"]
    kit["finite_scalar_history"] = False
    assert not m.kit_domain_check(kit)["covered"]


def test_flow_cache_binds_all_identities_and_refuses_phi_fallback():
    pins = {
        k: "sha256:" + "a" * 64
        for k in (
            "image",
            "mesh",
            "geometry",
            "bc",
            "schemes",
            "observer",
            "one_way_coupling_proof",
        )
    }
    a = m.action(30, 175, 8)
    key = m.flow_key(a, 5, pins)
    receipt = {
        "flow_key": key,
        **{k: "sha256:" + "b" * 64 for k in ("U", "p", "phi", "converged_receipt")},
    }
    assert (
        m.require_flow_cache(receipt, key)["status"]
        == "DOCUMENTARY_CACHE_MATCH_NOT_ADEQUACY"
    )
    with pytest.raises(ValueError):
        m.require_flow_cache(receipt, m.flow_key(a, 3, pins))
    changed = dict(pins)
    changed["mesh"] = "sha256:" + "c" * 64
    assert m.flow_key(a, 5, changed) != key
    receipt.pop("phi")
    with pytest.raises(ValueError):
        m.require_flow_cache(receipt, key)


def test_dictionary_drafts_units_and_distinct_zero_D_control():
    a, c = m.action(30, 175, 8), m.condition(5, 0.5e-10)
    deck = m.deck_draft(a, c)
    assert deck["solver"]["image_digest"] is None and "HOLD" in deck["status"]
    assert deck["volume_flow_m3_s"] == pytest.approx(5e-9 / 60)
    assert "[0 2 -2 0 0 0 0]" in deck["files"]["0/p"]
    assert "[0 0 0 0 0 0 0]" in deck["files"]["0/T"]
    control = m.deck_draft(a, c, zero_diffusion_control=True)
    assert control["scope"] == "NUMERICAL_DIFFUSION_CONTROL_NOT_P"
    with pytest.raises(ValueError):
        m.condition(5, 0)


def test_outlet_flux_not_area_and_no_clipping_or_backflow():
    report = m.outlet_observer([0, 1], [1e-11, 3e-11], 8e-10, 0.1, 0)
    assert report["mean_c"] == pytest.approx(0.75)
    assert report["mixing"] == pytest.approx(1 - math.sqrt(0.1875 / 0.25))
    assert report["pressure_pa"] == pytest.approx(99.8)
    assert report["residence_s"] == pytest.approx(20)
    adverse = m.outlet_observer([-1, 2], [1, 1], 2, 0, 0)
    assert adverse["mixing"] == -2 and not adverse["reference_bounds_ok"]
    with pytest.raises(ValueError, match="inapplicable"):
        m.outlet_observer([0, 1], [-1, 2], 1, 0, 0)


def test_solute_balance_includes_diffusion_not_the_mixing_weight():
    b = m.balances(
        [-1, 1], [-0.5, 0.6], [0, -0.1], incoming_volume=1, incoming_solute=0.5
    )
    assert b["mass_residual_fraction"] == 0
    assert b["solute_residual_fraction"] == pytest.approx(0)
    with pytest.raises(ValueError):
        m.balances([-1, 1], [0, 0], [0, 0], incoming_volume=1, incoming_solute=0)


def test_analytic_rectangular_pressure_scales_with_flow():
    p = m.rectangular_pressure_pa(1e-9 / 60)
    assert p > 0 and m.rectangular_pressure_pa(5e-9 / 60) == pytest.approx(5 * p)


def test_flow_MMS_has_zero_divergence_and_correct_NS_source():
    x = np.array([[0.2, 0.3, 0.4], [0.6, 0.7, 0.8]])
    field = m.flow_mms(x, 0.01)
    divergence = np.zeros(len(x))
    convection = np.zeros_like(x)
    lap = np.zeros_like(x)
    gradp = np.zeros_like(x)
    h = 1e-4
    for i in range(3):
        shift = np.zeros_like(x)
        shift[:, i] = h
        plus, minus = m.flow_mms(x + shift, 0.01), m.flow_mms(x - shift, 0.01)
        derivative = (plus["velocity"] - minus["velocity"]) / (2 * h)
        divergence += derivative[:, i]
        convection += field["velocity"][:, i, None] * derivative
        lap += (plus["velocity"] - 2 * field["velocity"] + minus["velocity"]) / h**2
        gradp[:, i] = (plus["kinematic_pressure"] - minus["kinematic_pressure"]) / (
            2 * h
        )
    assert np.allclose(divergence, 0, atol=1e-8)
    assert np.allclose(
        convection - 0.01 * lap + gradp, field["source_acceleration"], atol=1e-6
    )


def test_scalar_MMS_source_is_advection_minus_diffusion():
    x = np.array([[0.2, 0.3, 0.4]])
    f = m.scalar_mms(x, 0.1, 0.01)
    h = 1e-4
    lap = np.zeros(len(x))
    for i in range(3):
        shift = np.zeros_like(x)
        shift[:, i] = h
        plus, minus = m.scalar_mms(x + shift, 0.1, 0.01), m.scalar_mms(
            x - shift, 0.1, 0.01
        )
        lap += (
            plus["concentration"] - 2 * f["concentration"] + minus["concentration"]
        ) / h**2
        if i == 0:
            dx = (plus["concentration"] - minus["concentration"]) / (2 * h)
    assert np.allclose(0.1 * dx - 0.01 * lap, f["source"], atol=1e-8)


def export():
    rows = [
        {
            "action": a,
            "condition": c,
            "values": {"mixing": 0.82, "pressure_pa": 100, "residence_s": 10},
            "reference_status": "RESOLVED",
        }
        for a in m.proposed_panel()["designs"]
        for c in m.conditions()
    ]
    return {
        "challenge": m.FAMILY,
        "scope": "SYNTHETIC_FIXTURE",
        "rows": rows,
        "acquisition_cost": {"status": "TOY_NOT_PHYSICAL_COST"},
    }


def registered(report, *, floor=0.8):
    return tasks.task(
        "f17-toy",
        identity={
            "challenge": m.FAMILY,
            "contract_version": "toy",
            "action_grammar": "toy",
            "optimizer": "toy",
            "query_budget": 45,
            "seed": 0,
            "observer_version": "toy",
            "reference_bank": "toy-public",
        },
        conditions=[{"id": tasks.digest(c), "stratum": "toy"} for c in m.conditions()],
        strata={"toy": {"p": 1, "q": 1, "w": 1}},
        candidates=sorted({r["geometry"] for r in report["predictions"]}),
        objective={
            "quantity": "mixing",
            "unit": "1",
            "sense": "max",
            "aggregate": "worst",
        },
        limits=[
            {
                "quantity": "mixing",
                "unit": "1",
                "op": ">=",
                "value": floor,
                "band": 0.001,
            },
            {
                "quantity": "pressure_pa",
                "unit": "Pa",
                "op": "<=",
                "value": 250,
                "band": 1,
            },
            {
                "quantity": "residence_s",
                "unit": "s",
                "op": "<=",
                "value": 20,
                "band": 0.1,
            },
        ],
    )


def test_strong_response_surface_has_geometry_holdouts_and_real_query_cost():
    report = m.measure(export())
    assert report["coverage_rows"] == 9 and report["abstained_rows"] == 36
    assert report["pointwise_mae"]["mixing"] < 1e-7
    assert all(
        f["held_geometry"] not in f["fit_geometry_keys"] for f in report["folds"]
    )
    assert report["screening_cost"]["query_wall_s_per_query"] > 0
    assert (
        report["candidate_ranking"]
        and report["retained_verification_cost"] == "NOT_MEASURED"
    )
    decision = m.decision_report(report, registered(report))
    assert decision["regret_M"] == pytest.approx(0)
    assert decision["reference_resolved"] and decision["abstained_candidates"] == 4
    assert decision["feasibility_agreement"] == 1


def test_no_hidden_scope_duplicate_rows_or_looser_requirements():
    bad = export()
    bad["scope"] = "HIDDEN_EVAL"
    with pytest.raises(ValueError):
        m.measure(bad)
    bad = export()
    bad["rows"].append(bad["rows"][0])
    with pytest.raises(ValueError, match="duplicate"):
        m.measure(bad)
    report = m.measure(export())
    with pytest.raises(ValueError):
        m.decision_report(report, registered(report, floor=0.75))


def test_held_geometry_labels_cannot_change_its_predictions():
    raw = export()
    for row in raw["rows"]:
        a = row["action"]
        row["values"]["mixing"] = 0.7 + 0.002 * a["depth_um"]
        row["values"]["pressure_pa"] = 50 + 0.2 * a["pitch_um"]
    before = m.measure(raw)
    center = tasks.digest(m.action(30, 175, 8))
    for row in raw["rows"]:
        if tasks.digest(row["action"]) == center:
            row["values"] = {"mixing": 0.1, "pressure_pa": 500, "residence_s": 50}
    after = m.measure(raw)
    first = [r["prediction"] for r in before["predictions"] if r["geometry"] == center]
    second = [r["prediction"] for r in after["predictions"] if r["geometry"] == center]
    assert first == second and all(p is not None for p in first)


def test_readiness_inspects_real_routes_and_refuses_unwired_budget():
    class Tree:
        commit = "synthetic-tree-not-main"

        def __init__(self):
            self.files = {
                path: Path(path).read_bytes()
                for path in (
                    "carbon/challenge_pipeline/micromixer_readiness.py",
                    "carbon/design_search/micromixer_budget.py",
                    "carbon/design_search/equal_budget.py",
                )
            }

        def read(self, path):
            return self.files.get(path)

    tree = Tree()
    assert er.code_route(tree, "f17")[0] == "YES"
    assert er.code_route(tree, "f17", optimizer=True)[0] == "YES"
    path = "carbon/design_search/equal_budget.py"
    tree.files[path] = tree.files[path].replace(b"micromixer_budget", b"not_the_budget")
    assert er.code_route(tree, "f17", optimizer=True)[0] == "NO"
    tree.files.pop("carbon/design_search/micromixer_budget.py")
    assert er.code_route(tree, "f17", optimizer=True)[0] == "PLANNED"


def test_missing_fit_or_reference_stays_unresolved_not_none_feasible():
    raw = export()
    for row in raw["rows"]:
        row["reference_status"] = "UNRESOLVED"
    report = m.measure(raw)
    decision = m.decision_report(report, registered(report))
    assert decision["reference_state"] == "UNRESOLVED"
    assert decision["regret_M"] is None and decision["abstained_candidates"] == 5


def test_equal_budget_extension_does_not_reinterpret_historical_registration():
    from test_design_search_equal_budget import panel

    raw = mb.proposal()
    resolved = mb.validate(raw)
    with pytest.raises(br.BudgetRegistrationError):
        br.validate(raw)
    bad = copy.deepcopy(raw)
    bad["challenge_budgets"][m.FAMILY]["basis"] = "MEASURED"
    with pytest.raises(br.BudgetRegistrationError):
        mb.validate(bad)
    toy = panel(m.FAMILY)
    toy.pop("panel_digest")
    toy["budgets"] = [resolved.cap(m.FAMILY, t).time_compute for t in br.TIERS]
    toy["registrations"]["cost_plan"] = resolved.registration_id
    result = eb.compare(
        eb.seal(toy),
        bootstrap_replicates=100,
        confidence=0.95,
        seed=7,
        registration=raw,
    )
    assert result["status"] == "OK"


def test_pilot_no_grant_high_cost_fails_cap_and_verification_not_run():
    pilot = m.pilot_plan()
    assert pilot["grant"] is None and not pilot["dispatch_allowed"]
    assert not pilot["high_fits_cap"]
    assert len(pilot["tuples"]) == 6
    spec = json.loads(Path(m.DOC + "verification.json").read_text())
    assert spec["status"] == "SPECIFIED_NOT_RUN" and spec["image_digest"] is None


def test_cli_only_prints_public_proposal(capsys):
    m.main(["panel"])
    assert json.loads(capsys.readouterr().out)["scope"] == m.SCOPE
