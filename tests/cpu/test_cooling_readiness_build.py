"""Synthetic preparation/observer arithmetic; no solver or purchased evidence."""

import copy

import pytest

from carbon.challenge_pipeline import cooling_readiness as cr
from carbon.cold_plate import domain, openfoam
from carbon.design_search import budget_registration as br
from carbon.design_search import cooling_budget, equal_budget, tasks


def registration():
    service = {
        "id": "fixture-warm",
        "stratum": "fixture-only",
        "plane": cr.PLANE,
        "coolant": "PG25",
        "lid_id": "fixture-vapour-chamber",
        "inlet_c": 40,
        "heat_load_w": 900,
        "hotspot_ratio": 1,
        "hotspot_center_mm": 15,
        "hotspot_width_mm": 2.5,
        "map_digest": "sha256:" + "a" * 64,
        "characterization_digest": "sha256:" + "b" * 64,
        "inlet_source_digest": "sha256:" + "c" * 64,
        "tim2_m2k_w": 5e-6,
        "map_uncertainty_k": 0.5,
        "cell_pressure_limit_pa": None,
        "objective": None,
    }
    return cr.seal(
        {
            "schema": cr.SCHEMA,
            "scope": "SYNTHETIC_FIXTURE",
            "authority": "synthetic arithmetic only",
            "pins": {
                "solver_image": openfoam.IMAGE.split("@")[1],
                "solver_source": "sha256:" + "d" * 64,
                "materials": "sha256:" + "e" * 64,
                "observer": "sha256:" + "f" * 64,
            },
            "grammar": {
                "channel_width_mm": {"min": 0.2, "max": 0.4, "step": 0.1},
                "fin_width_mm": {"min": 0.2, "max": 0.4, "step": 0.1},
                "channel_depth_mm": {"min": 1, "max": 3, "step": 1},
                "flow_lpm_per_kw": {"min": 1.25, "max": 1.75, "step": 0.25},
            },
            "services": [service],
            "P": {service["id"]: 1},
            "Q": {service["id"]: 1},
            "w": {service["id"]: 1},
        }
    )


def reseal(r):
    return cr.seal({k: v for k, v in r.items() if k != "digest"})


def action():
    return {
        "channel_width_mm": 0.3,
        "fin_width_mm": 0.3,
        "channel_depth_mm": 2,
        "flow_lpm_per_kw": 1.5,
    }


def faces(r, temperatures=(74, 80)):
    c = cr.case(r, action(), "fixture-warm", resolution=2)
    return [
        {
            "x_m": x,
            "y_m": 0.00015,
            "area_m2": 4.5e-6,
            "plate_c": t,
            "q_w_m2": domain.heat_flux(c["inputs"], x * 1000),
        }
        for x, t in zip((0.0075, 0.0225), temperatures)
    ]


def observation(r, temperatures=(74, 80), **options):
    return cr.observe(
        r,
        action(),
        "fixture-warm",
        faces(r, temperatures),
        numerical_uncertainty_k=0.1,
        pressure_drop_pa=1000,
        fluid_min_c=40,
        fluid_max_c=42,
        **options,
    )


def test_action_generator_has_unique_deterministic_supported_coordinates():
    r = registration()
    a = cr.actions(r, count=40, seed=31)
    assert a == cr.actions(r, count=40, seed=31)
    assert len({tasks.digest(x) for x in a}) == 40
    assert all(set(x) == set(cr.ACTION) for x in a)
    assert all(
        cr.case(r, x, "fixture-warm", resolution=2)["scope"] == "SYNTHETIC_FIXTURE"
        for x in a
    )
    with pytest.raises(ValueError, match="not enough"):
        cr.actions(r, count=1000, seed=1)


@pytest.mark.parametrize(
    "field,value",
    [
        ("inlet_c", 25),
        ("hotspot_ratio", 4),
        ("plane", "die-TIM1"),
        ("coolant", "water"),
        ("lid_id", None),
        ("tim2_m2k_w", -1),
        ("map_uncertainty_k", None),
    ],
)
def test_missing_or_unsupported_buyer_service_is_not_silently_reframed(field, value):
    r = registration()
    r["services"][0][field] = value
    with pytest.raises(ValueError):
        cr.validate(reseal(r))


def test_P_Q_w_and_flow_actions_do_not_move_buyer_settings():
    r = registration()
    draws = cr.conditions(r, count=20, seed=4, law="Q")
    assert all(
        d["service"] == r["services"][0] and d["p"] == d["q"] == d["w"] == 1
        for d in draws
    )
    r["P"] = {"fixture-warm": 0.9}
    with pytest.raises(ValueError, match="P/Q/w"):
        cr.conditions(reseal(r), count=1, seed=1, law="P")


def test_panel_dedup_reuse_requires_exact_inputs_pins_and_explicit_inventories():
    r = registration()
    retained = cr.case(r, action(), "fixture-warm", resolution=2)
    result = cr.panel(
        r, [action(), action()], rungs=[2, 2, 4], retained=[retained], scheduled=[]
    )
    assert [x["reuse"] for x in result["cases"]] == ["COMPLETED", "NEW"]
    assert not result["dispatchable"]
    retained["inputs"]["inlet_c"] = 35
    with pytest.raises(ValueError, match="tuple differs"):
        cr.panel(r, [action()], rungs=[2], retained=[retained], scheduled=[])


def test_reference_deck_is_real_supported_in_memory_text_but_not_verified():
    result = cr.deck(registration(), action(), "fixture-warm", resolution=2)
    assert "chtMultiRegionSimpleFoam" in result["files"]["system/controlDict"]
    assert (
        "q               uniform 1000000.0"
        in result["files"]["system/solid/changeDictionaryDict"]
    )
    assert result["image"] == openfoam.IMAGE
    assert result["observer"] == cr.PLANE
    assert result["status"] == "UNVERIFIED_DECK_DRAFT" and not result["dispatchable"]


def test_correct_case_plane_no_die_or_lid_drop_and_close_call_is_unresolved():
    r = registration()
    result = observation(r)
    assert result["peak_case_c"] == 85
    assert result["thermal_verdict"] == "UNRESOLVED"
    assert result["pressure_verdict"] == "HUMAN_INPUT"
    assert result["best_pick"] == "UNRESOLVED_BUYER_OBJECTIVE"
    assert observation(r, (72, 78))["thermal_verdict"] == "FEASIBLE"
    assert observation(r, (75, 81))["thermal_verdict"] == "INFEASIBLE"
    assert result["half_cell_hydraulic_power_w"] == 1000 * result["half_cell_flow_m3_s"]


def test_local_hotspot_flux_not_mean_flux_times_unrelated_maximum():
    r = registration()
    r["services"][0].update(hotspot_ratio=2, hotspot_center_mm=7.5)
    r = reseal(r)
    result = observation(r, (77, 80))
    local = faces(r, (77, 80))
    expected = max(f["plate_c"] + 5e-6 * f["q_w_m2"] for f in local)
    assert result["peak_case_c"] == pytest.approx(expected)
    assert result["peak_case_c"] != pytest.approx(80 + 5)


def test_mismatched_flux_or_missing_patch_coverage_refused():
    r = registration()
    fs = faces(r)
    fs[0]["q_w_m2"] += 1
    with pytest.raises(ValueError, match="frozen"):
        cr.observe(
            r,
            action(),
            "fixture-warm",
            fs,
            numerical_uncertainty_k=0,
            pressure_drop_pa=1,
            fluid_min_c=40,
            fluid_max_c=42,
        )
    with pytest.raises(ValueError, match="whole half-cell"):
        cr.observe(
            r,
            action(),
            "fixture-warm",
            faces(r)[:1],
            numerical_uncertainty_k=0,
            pressure_drop_pa=1,
            fluid_min_c=40,
            fluid_max_c=42,
        )
    assert (
        cr.observe(
            r,
            action(),
            "fixture-warm",
            faces(r),
            numerical_uncertainty_k=0,
            pressure_drop_pa=1,
            fluid_min_c=29,
            fluid_max_c=42,
        )["status"]
        == "REFERENCE_INVALID"
    )


def test_train_excludes_same_physics_despite_rung_and_service_rename():
    r = registration()
    s = copy.deepcopy(r["services"][0])
    s.update(id="fixture-renamed", stratum="new-label")
    r["services"].append(s)
    r.update(
        P={"fixture-warm": 0.5, "fixture-renamed": 0.5},
        Q={"fixture-warm": 0.5, "fixture-renamed": 0.5},
        w={"fixture-warm": 0.5, "fixture-renamed": 0.5},
    )
    r = reseal(r)
    test = cr.case(r, action(), "fixture-warm", resolution=2)
    duplicate = cr.case(r, action(), "fixture-renamed", resolution=4)
    assert cr.train_plan(r, [duplicate], [test])["cases"] == []
    other = action()
    other["channel_depth_mm"] = 3
    plan = cr.train_plan(r, [cr.case(r, other, "fixture-warm", resolution=2)], [test])
    assert len(plan["cases"]) == 1 and plan["scope"] == "SYNTHETIC_FIXTURE"


def test_kit_hook_compares_plane_maps_actions_observables_and_nonempty_basis():
    r = registration()
    c = cr.case(r, action(), "fixture-warm", resolution=2)
    kit = {
        "registration_digest": r["digest"],
        "plane": cr.PLANE,
        "observables": [
            "peak_case_c",
            "cell_pressure_drop_pa",
            "half_cell_flow_m3_s",
            "half_cell_hydraulic_power_w",
        ],
        "services": ["fixture-warm"],
        "action_bounds": {k: [v["min"], v["max"]] for k, v in r["grammar"].items()},
    }
    assert cr.kit_domain(r, kit, [c])["covered"]
    assert not cr.kit_domain(r, kit, [])["covered"]
    kit["plane"] = "die-TIM1"
    assert not cr.kit_domain(r, kit, [c])["covered"]


def test_manufactured_fields_balance_constant_property_energy_equation():
    opts = {
        "height_m": 0.01,
        "gradient_pa_m": 1,
        "mu_pa_s": 0.001,
        "rho_cp": 4e6,
        "k_w_mk": 0.5,
        "t0_k": 310,
        "axial_k_m": 3,
        "amplitude_k": 2,
    }
    x, y, h = 0.02, 0.004, 1e-6
    field = cr.manufactured_channel(x, y, **opts)
    txx = (
        cr.manufactured_channel(x + h, y, **opts)["temperature_k"]
        - 2 * field["temperature_k"]
        + cr.manufactured_channel(x - h, y, **opts)["temperature_k"]
    ) / h**2
    tyy = (
        cr.manufactured_channel(x, y + h, **opts)["temperature_k"]
        - 2 * field["temperature_k"]
        + cr.manufactured_channel(x, y - h, **opts)["temperature_k"]
    ) / h**2
    assert field["energy_source_w_m3"] == pytest.approx(
        opts["rho_cp"] * field["u_m_s"] * opts["axial_k_m"]
        - opts["k_w_mk"] * (txx + tyy),
        rel=1e-5,
    )
    assert (
        cr.manufactured_channel(x, 0, **opts)["u_m_s"]
        == cr.manufactured_channel(x, 0.01, **opts)["u_m_s"]
        == 0
    )


def test_additive_budget_leaves_old_contract_closed_and_enforces_caps():
    raw = cooling_budget.proposal()
    validated = cooling_budget.validate(raw)
    cap = validated.cap(cr.FAMILY, "base")
    assert cap == br.BudgetCap(8, 14400, 28800)
    with pytest.raises(br.BudgetRegistrationError):
        br.validate(raw)
    ledger = br.BudgetLedger(cap)
    assert not ledger.charge_solver_attempt(
        {"wall_s": 14401, "core_s": 1}, {"wall_s": 1, "core_s": 1}
    )
    raw["challenge_budgets"][cr.FAMILY]["basis"] = "MEASURED"
    raw = br.seal({k: v for k, v in raw.items() if k != "registration_digest"})
    with pytest.raises(br.BudgetRegistrationError):
        cooling_budget.validate(raw)


def test_equal_budget_compare_uses_cooling_specific_validator():
    from test_design_search_equal_budget import panel as toy_panel

    raw = cooling_budget.proposal()
    p = toy_panel("cooling-cell")
    caps = cooling_budget.validate(raw)
    p["budgets"] = [caps.cap(cr.FAMILY, tier).time_compute for tier in br.TIERS]
    p["registrations"]["cost_plan"] = cooling_budget.ID
    p = equal_budget.seal({k: v for k, v in p.items() if k != "panel_digest"})
    result = equal_budget.compare(
        p, bootstrap_replicates=100, confidence=0.95, seed=2, registration=raw
    )
    assert result["budget_registration_id"] == cooling_budget.ID
    assert result["challenge"] == cr.FAMILY


def test_comparator_refuses_legacy_plate_observer_or_changed_map():
    with pytest.raises(ValueError, match="case-plane"):
        cr.compare(
            registration(),
            {"family": "cooling-cell"},
            {"observer_versions": ["legacy-plate-peak"]},
        )


def test_real_held_geometry_map_exports_decisions_abstention_and_screen_cost():
    from test_portfolio_baselines import fixture

    from carbon.design_search import producer_panels
    from carbon.development_comparison import portfolio_baselines as pb

    r = registration()
    r["grammar"]["channel_width_mm"]["step"] = 0.05
    r = reseal(r)
    observer = cr.OBSERVER + ":" + r["digest"]
    export, material = fixture("cooling-cell")
    old = export["questions"][0]["task"]
    identity = copy.deepcopy(old["identity"])
    identity["observer_version"] = observer
    identity["action_grammar"]["variables"] = [
        {"name": k, "type": "number", **v} for k, v in r["grammar"].items()
    ]
    coordinates = {}
    for i, candidate in enumerate(old["candidates"]):
        coordinates[candidate] = {
            **action(),
            "channel_width_mm": round(0.2 + i * 0.05, 2),
        }
    export["questions"][0]["task"] = tasks.task(
        old["task_id"],
        identity=identity,
        conditions=old["conditions"],
        strata=old["strata"],
        candidates=old["candidates"],
        actions=coordinates,
        objective={
            "quantity": "cell_pressure_drop_pa",
            "unit": "Pa",
            "sense": "min",
            "aggregate": "worst",
        },
        limits=[{"quantity": "peak_case_c", "unit": "degC", "op": "<=", "value": 85}],
    )
    for i, row in enumerate(export["questions"][0]["reference"]):
        row["values"] = {
            "cell_pressure_drop_pa": 1000 + i * 100,
            "peak_case_c": 75 + i * 3,
        }
    export = producer_panels.seal_export(
        {k: v for k, v in export.items() if k != "export_digest"}
    )
    material.update(export_digest=export["export_digest"], observer_versions=[observer])
    material["settings"].update(
        coordinate_fields=list(cr.ACTION),
        reducers=[
            {"quantity": "cell_pressure_drop_pa", "unit": "Pa", "kind": "surface"},
            {"quantity": "peak_case_c", "unit": "degC", "kind": "surface"},
        ],
    )
    for row in material["rows"]:
        row["coordinates"] = [coordinates[row["candidate"]][k] for k in cr.ACTION]
        row["context_sha256"] = tasks.digest(r["services"][0])[7:]
    material = pb.seal_materials(
        {k: v for k, v in material.items() if k != "materials_digest"}
    )
    result = cr.compare(r, export, material)
    assert result["reference_solves_launched"] == 0
    assert result["held_out"]["status"] == "MEASURED"
    assert result["equal_budget_screening"]["query_cost"]["samples"] == 5
    assert result["equal_budget_screening"]["candidate_rankings"]
    assert result["claims"]["tested_challenge"] is False
    material["rows"][0]["context_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="crosses frozen"):
        cr.compare(r, export, material)
