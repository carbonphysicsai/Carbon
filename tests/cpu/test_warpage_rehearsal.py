"""Synthetic preparation and analytic controls only; no physical solver runs."""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from carbon.challenge_pipeline import warpage_rehearsal as w
from carbon.design_search import budget_registration as br
from carbon.design_search import equal_budget as eb
from carbon.design_search import tasks
from carbon.design_search import warpage_budget as wb


def test_full_package_and_source_vs_assumptions_are_not_collapsed():
    geometry = w.architecture(w.action(0.06, 0.3, 1.2))
    assert geometry["body_mm"] == [63, 63]
    assert geometry["hbm_count"] == 6 and geometry["asic_count"] == 1
    assert len([r for r in geometry["regions"] if r["id"].startswith("hbm-")]) == 6
    assert {r["id"] for r in geometry["regions"]} >= {
        "substrate",
        "interposer",
        "lid",
        "asic",
    }
    assert geometry["mesh_status"] == "DRAFT_REGION_LAYOUT_NOT_WATERTIGHT_CAD"
    assert geometry["dimension_basis_except_body"] == "ASSUMPTION_NOT_AMKOR_CAD"


@pytest.mark.parametrize(
    "value", [0, -1, float("nan"), float("inf"), True, "0.06", 0.2]
)
def test_action_fails_outside_support(value):
    with pytest.raises(ValueError):
        w.action(value, 0.3, 1.2)


def test_panel_and_train_physical_identities_cover_complete_histories():
    p = w.proposed_panel()
    assert len(p["cases"]) == 36
    assert len({tasks.digest(c) for c in p["cases"]}) == 36
    assert all(
        {s["stage"] for s in c["condition"]["stages"]}
        >= {"cure", "reflow", "cool", "service"}
        for c in p["cases"]
    )
    assert all(
        c["condition"]["stages"]
        == sorted(c["condition"]["stages"], key=lambda s: s["time_s"])
        for c in p["cases"]
    )
    train = w.train_plan(p)
    physical = lambda c: tasks.digest(
        {"action": c["action"], "condition": c["condition"]}
    )
    assert not {physical(c) for c in train["cases"]} & {physical(c) for c in p["cases"]}
    alias = copy.deepcopy(train["cases"][0])
    alias["condition"]["id"] = "different-label"
    p["cases"].append({**alias, "rung": {"mesh_scale": 0.25}})
    with pytest.raises(ValueError, match="overlap"):
        w.train_plan(p)


def test_kit_must_cover_conditions_observers_and_all_history_features():
    p = w.proposed_panel()
    kit = {
        "scope": w.SCOPE,
        "covered_physical_keys": [w.physical_key(c) for c in p["cases"]],
        "observables": list(w.OBSERVABLES),
        "history_features": list(w.LAW_FIELDS),
    }
    assert w.kit_domain_check(kit)["covered"]
    kit["history_features"].remove("solder_formation_state")
    assert not w.kit_domain_check(kit)["covered"]


def test_draft_never_dispatches_or_replaces_missing_history_by_elasticity():
    assert w.history_hold({})["status"] == "HOLD"
    laws = {
        f: {
            "source_digest": "fixture",
            "accepted_domain": "fixture",
            "implementation_digest": "fixture",
        }
        for f in w.LAW_FIELDS
    }
    assert not w.history_hold(laws)["dispatch_allowed"]
    d = w.deck_draft(w.action(0.06, 0.3, 1.2), w.histories()[1])
    assert d["pins"]["full_history_image"] is None
    assert "HOLD" in d["status"] and "formed-joint-state.inp" in d["required_inputs"]
    assert "*ELASTIC" not in d["calculix_template"]
    with pytest.raises(ValueError):
        w.deck_draft(w.action(0.06, 0.3, 1.2), {"final_temperature": 25})


def test_surface_datum_is_signed_and_rigid_motion_invariant():
    xy = [[-1, -1], [1, -1], [-1, 1], [1, 1], [0, 0]]
    u = np.array([0.1, 0.1, 0.1, 0.1, -0.1])
    a = w.surface_observer(xy, u)
    b = w.surface_observer(xy, u + 3 + np.asarray(xy) @ [0.1, 0.2])
    assert a["warpage_pv_mm"] == pytest.approx(0.2)
    assert b["warpage_pv_mm"] == pytest.approx(a["warpage_pv_mm"])
    assert min(a["signed_residual_mm"]) < 0 < max(a["signed_residual_mm"])
    with pytest.raises(ValueError):
        w.surface_observer([[0, 0], [1, 1], [2, 2]], [0, 1, 2])
    with pytest.raises(ValueError):
        w.surface_observer(xy, [float("nan")] * 5)


def test_history_cannot_hide_an_intermediate_peak_or_drop_a_zone():
    xy = [[0, 0], [1, 0], [0, 1], [1, 1]]
    frames = [
        {"time_s": t, "zones": {"surface": {"xy_mm": xy, "uz_mm": [0, 0, 0, peak]}}}
        for t, peak in ((0, 0), (1, 0.2), (2, 0))
    ]
    assert w.observe_history(frames)["max_warpage_pv_mm"] > 0
    with pytest.raises(ValueError):
        w.observe_history(list(reversed(frames)))
    frames[-1]["zones"] = {}
    with pytest.raises(ValueError):
        w.observe_history(frames)


def layers(alpha1=10e-6, alpha2=20e-6):
    return [
        {"thickness_mm": 0.5, "modulus_mpa": 10000, "alpha_per_k": a}
        for a in (alpha1, alpha2)
    ]


def test_laminate_reproduces_equal_layer_bimetal_and_equal_cte_controls():
    result = w.laminate_estimate(layers(), 100, 20)
    assert result["curvature_per_mm"] == pytest.approx(1.5 * (20e-6 - 10e-6) * 100)
    assert result["signed_midspan_sag_mm"] == pytest.approx(0.075)
    assert w.laminate_estimate(layers(10e-6, 10e-6), 100, 20)[
        "curvature_per_mm"
    ] == pytest.approx(0)
    assert not result["full_task_prediction"]
    candidates = [
        {"id": name, "layers": ll, "delta_t_c": 100, "span_mm": 20}
        for name, ll in (("b", layers()), ("a", layers(10e-6, 10e-6)))
    ]
    report = w.comparator_ranking(candidates)
    assert report["candidate_ranking"] == ["a", "b"]
    assert report["screening_wall_s_per_query"] > 0
    assert report["regret_mm"] is None and report["decision_agreement"] is None


def test_manufactured_source_satisfies_divergence_equilibrium():
    x = np.array([[0.2, 0.3, 0.4], [0.6, 0.7, 0.8]])
    f = w.mms_fields(x, 10000, 0.25)
    divergence = np.zeros_like(x)
    for i in range(3):
        shift = np.zeros_like(x)
        shift[:, i] = 1e-5
        divergence[:, i] = (
            w.mms_fields(x + shift, 10000, 0.25)["stress_diagonal"][:, i]
            - w.mms_fields(x - shift, 10000, 0.25)["stress_diagonal"][:, i]
        ) / 2e-5
    assert np.allclose(divergence + f["body_force"], 0, atol=1e-6)


def test_budget_route_is_additive_shared_and_digest_guarded():
    from test_design_search_equal_budget import panel

    raw = wb.proposal()
    registered = wb.validate(raw)
    with pytest.raises(br.BudgetRegistrationError):
        br.validate(raw)
    damaged = copy.deepcopy(raw)
    damaged["authority"] = "different"
    with pytest.raises(br.BudgetRegistrationError):
        wb.validate(damaged)
    ledger = br.BudgetLedger(registered.cap(w.FAMILY, "half"))
    assert not ledger.charge_solver_attempt(
        {"wall_s": 8000, "core_s": 1}, {"wall_s": 8000, "core_s": 1}
    )
    toy = panel(w.FAMILY)
    toy.pop("panel_digest")
    toy["budgets"] = [registered.cap(w.FAMILY, tier).time_compute for tier in br.TIERS]
    toy["registrations"]["cost_plan"] = registered.registration_id
    result = eb.compare(
        eb.seal(toy),
        bootstrap_replicates=100,
        confidence=0.95,
        seed=7,
        registration=raw,
    )
    assert result["status"] == "OK"


def test_pilot_does_not_pretend_high_cost_fits_or_create_a_grant():
    pilot = w.pilot_plan()
    assert pilot["grant"] is None and not pilot["fits_high_cap"]
    assert pilot["eur_low_base_high"][-1] > pilot["cap_eur"]
    spec = json.loads(Path(w.DOC + "verification.json").read_text())
    assert spec["image_digest"] is None and spec["status"] == "SPECIFIED_NOT_RUN"
    delivery = json.loads(Path(w.DOC + "delivery-measurement.json").read_text())
    assert delivery["delivered_at"] is None and not delivery["customer_result"]


def test_cli_prints_only_representative_proposals(capsys):
    w.main(["panel"])
    out = json.loads(capsys.readouterr().out)
    assert out["scope"] == w.SCOPE and out["registered_manifest_digest"] is None
