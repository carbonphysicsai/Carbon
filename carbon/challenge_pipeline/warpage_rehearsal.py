"""Full-3D REPRESENTATIVE preparation, not a reference solver or customer result.

Print proposals only. No solver, image build, store lookup or dispatch capability.
Complete-history constitutive data remain a hard HOLD outside analytic controls.
"""

from __future__ import annotations

import argparse
import copy
import json
import math

import numpy as np

from carbon.design_search import tasks

FAMILY = "package-warpage"
SCOPE = "REPRESENTATIVE_DEVELOPMENT"
DOC = "docs/development/challenge_pipeline/warpage-rehearsal/"
OBSERVABLES = ("warpage_pv_mm", "coplanarity_pv_mm", "stress_mpa", "temperature_c")
LAW_FIELDS = (
    "coherent_material_family",
    "cte_modulus_domain",
    "cure_kinetics_shrinkage",
    "conversion_stiffness",
    "viscoelastic_shear_bulk_shift",
    "solder_solid_law",
    "solder_formation_state",
    "state_restart_mapping",
)


def positive(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError("positive finite physical value required")
    return float(value)


def action(standoff_mm, fillet_mm, lid_mm, material_family="buyer-family-pending"):
    for value, limits in (
        (standoff_mm, (0.04, 0.1)),
        (fillet_mm, (0.1, 0.6)),
        (lid_mm, (0.8, 2.0)),
    ):
        if not limits[0] <= positive(value) <= limits[1]:
            raise ValueError("outside representative geometry support")
    if material_family != "buyer-family-pending":
        raise ValueError("unregistered material action; no inferred calibration")
    return {
        "standoff_mm": standoff_mm,
        "fillet_mm": fillet_mm,
        "lid_mm": lid_mm,
        "material_family": material_family,
    }


def architecture(design):
    design = action(**design)
    # Only body size/topology are sourced; detailed dimensions are assumptions.
    h = design["standoff_mm"]
    regions = [
        {"id": "substrate", "box_mm": [-31.5, -31.5, 0, 63, 63, 0.5]},
        {"id": "interposer", "box_mm": [-25, -26, 0.5, 50, 52, 0.2]},
    ]
    footprints = [("asic", -12.5, -12.5, 25, 25, 0.75)] + [
        (f"hbm-{side}-{i}", x, y, 12, 10, 1.2)
        for side, x in (("left", -28), ("right", 16))
        for i, y in enumerate((-22, -5, 12))
    ]
    for name, x, y, width, depth, height in footprints:
        regions.extend(
            [
                {"id": name, "box_mm": [x, y, 0.7 + h, width, depth, height]},
                {"id": "uf-" + name, "box_mm": [x, y, 0.7, width, depth, h]},
            ]
        )
    regions.append(
        {"id": "lid", "box_mm": [-31.5, -31.5, 2.2, 63, 63, design["lid_mm"]]}
    )
    return {
        "scope": SCOPE,
        "body_mm": [63, 63],
        "asic_count": 1,
        "hbm_count": 6,
        "topology_source": "https://amkor.com/blog/thermal-simulation-of-dsmbga-coupled-thermal-mechanical-simulation-of-large-body-hdfo/",
        "dimension_basis_except_body": "ASSUMPTION_NOT_AMKOR_CAD",
        "regions": regions,
        "joint_and_fillet_grammar": {
            "solder": "Customer pitch/array and pads replace HUMAN_INPUT; subtract joints from underfill, conforming interfaces",
            "fillet_mm": design["fillet_mm"],
            "lid_attachment": "HUMAN_INPUT: adhesive/contact/stiffener geometry and preload",
        },
        "mesh_status": "DRAFT_REGION_LAYOUT_NOT_WATERTIGHT_CAD",
    }


def histories():
    # Reflow/cool-down timing is representative, not a JEDEC/supplier recipe.
    stages = [
        {"stage": "cure", "time_s": 0, "temperature_c": 25},
        {"stage": "cure", "time_s": 900, "temperature_c": 100},
        {"stage": "cure", "time_s": 6300, "temperature_c": 100},
        {"stage": "cure", "time_s": 7200, "temperature_c": 165},
        {"stage": "cure", "time_s": 14400, "temperature_c": 165},
        {"stage": "cool", "time_s": 18000, "temperature_c": 25},
        {"stage": "reflow", "time_s": 18180, "temperature_c": 220},
        {"stage": "reflow", "time_s": 18240, "temperature_c": 250},
        {"stage": "cool", "time_s": 18600, "temperature_c": 25},
        {"stage": "service", "time_s": 22200, "temperature_c": 85},
    ]
    return [
        {"id": "uniform-history", "stages": copy.deepcopy(stages), "asic_delta_c": 0},
        {
            "id": "asymmetric-service",
            "stages": copy.deepcopy(stages),
            "asic_delta_c": 20,
        },
        {
            "id": "slow-cool",
            "stages": [
                {**s, "time_s": s["time_s"] + (3600 if s["time_s"] >= 18600 else 0)}
                for s in stages
            ],
            "asic_delta_c": 0,
        },
    ]


def physical_key(case):
    condition = {k: v for k, v in case["condition"].items() if k != "id"}
    return tasks.digest({"action": action(**case["action"]), "condition": condition})


def proposed_panel():
    designs = [
        action(h, f, lid)
        for h, f, lid in (
            (0.04, 0.1, 0.8),
            (0.06, 0.1, 1.2),
            (0.1, 0.1, 1.2),
            (0.06, 0.3, 1.2),
            (0.06, 0.6, 1.2),
            (0.06, 0.3, 2.0),
        )
    ]
    conditions = histories()
    cases = [
        {"action": d, "condition": c, "rung": {"mesh_scale": r, "time_scale": r}}
        for d in designs
        for c in conditions
        for r in (1.0, 0.5)
    ]
    assert len({tasks.digest(c) for c in cases}) == len(cases)
    return {
        "challenge": FAMILY,
        "scope": SCOPE,
        "status": "PROPOSED_NOT_DISPATCHABLE",
        "designs": designs,
        "conditions": conditions,
        "cases": cases,
        "case_count": len(cases),
        "reuse": "UNKNOWN_NO_RETAINED_OR_SCHEDULED_INDEX",
        "full_history_image_digest": None,
        "registered_manifest_digest": None,
        "P": None,
        "Q": None,
        "w": None,
        "boundary_plan": "At least 5 feasible and 5 infeasible within TWO accepted refinement bands per stratum; adaptive registration, never widened bands",
        "value_measures": [
            "complete feasible action",
            "buyer-unit spread",
            "changing picks",
            "strong cheap-baseline regret",
        ],
        "limits": "HUMAN_INPUT: applicable zone, warpage/stress/temperature and objective",
    }


def train_plan(panel=None):
    panel = proposed_panel() if panel is None else panel
    panel_physical = {physical_key(c) for c in panel["cases"]}
    cases = [
        {
            "action": action(h, f, lid),
            "condition": c,
            "rung": {"mesh_scale": 1.0, "time_scale": 1.0},
        }
        for h, f, lid in ((0.05, 0.2, 1.0), (0.08, 0.4, 1.6))
        for c in histories()
    ]
    if panel_physical & {physical_key(c) for c in cases}:
        raise ValueError("TRAIN physical overlap, regardless of rung or name")
    return {
        "challenge": FAMILY,
        "scope": SCOPE,
        "status": "PROPOSED_NOT_REGISTERED",
        "cases": cases,
        "solved_train_digest": None,
        "rights": "HUMAN_INPUT",
    }


def kit_domain_check(kit, panel=None):
    panel = proposed_panel() if panel is None else panel
    required = {physical_key(c) for c in panel["cases"]}
    covered = set(kit.get("covered_physical_keys", []))
    ok = (
        kit.get("scope") == SCOPE
        and required <= covered
        and set(OBSERVABLES) <= set(kit.get("observables", []))
        and set(LAW_FIELDS) <= set(kit.get("history_features", []))
    )
    return {
        "covered": ok,
        "missing_physical_keys": sorted(required - covered),
        "qualification": False,
        "training_registration_implied": False,
    }


def history_hold(materials):
    missing = [
        f
        for f in LAW_FIELDS
        if not (
            type(materials.get(f)) is dict
            and materials[f].get("source_digest")
            and materials[f].get("accepted_domain")
            and materials[f].get("implementation_digest")
        )
    ]
    # This function reports documentary completeness, never authorizes a solve.
    return {
        "status": "HOLD" if missing else "AWAIT_INDEPENDENT_ACCEPTANCE",
        "missing": missing,
        "dispatch_allowed": False,
    }


def deck_draft(design, condition):
    geometry = architecture(design)
    if condition not in histories():
        raise ValueError("unregistered complete history")
    return {
        "scope": SCOPE,
        "status": "HOLD_MESH_LAWS_STATE_AND_IMAGE",
        "geometry": geometry,
        "condition": condition,
        "units": {
            "length": "mm",
            "force": "N",
            "stress": "MPa",
            "time": "s",
            "temperature": "degC",
        },
        "required_inputs": [
            "mesh.inp",
            "material-history.inp",
            "formed-joint-state.inp",
            "support-release.inp",
            "nodal-temperature-history.inp",
        ],
        "calculix_template": (
            "** DRAFT ONLY: no executable material/state substitute\n"
            "*INCLUDE, INPUT=mesh.inp\n*INCLUDE, INPUT=material-history.inp\n"
            "*INCLUDE, INPUT=formed-joint-state.inp\n*INCLUDE, INPUT=support-release.inp\n"
            "** Data Collection emits one approved *STEP per history segment;\n"
            "** *STATIC with mapped *TEMPERATURE, or a verified coupled procedure.\n"
            "** Activate only newly formed joints, retain all surrounding residual state.\n"
            "** Export *NODE FILE U,NT and *EL FILE S,E plus raw integration-point\n"
            "** history/constitutive state; averaged FRD stress is not local truth.\n"
        ),
        "observer": "Signed z-displacement minus least-squares datum at each time/zone, extrema over full history; stress at approved integration points",
        "pins": {
            "source_lock": "reference_packages/calculix/sources.lock.json",
            "full_history_image": None,
        },
    }


def surface_observer(xy_mm, uz_mm):
    xy, u = np.asarray(xy_mm, dtype=float), np.asarray(uz_mm, dtype=float)
    if (
        xy.ndim != 2
        or xy.shape[1] != 2
        or len(xy) < 3
        or u.shape != (len(xy),)
        or not np.isfinite(xy).all()
        or not np.isfinite(u).all()
        or len(np.unique(xy, axis=0)) != len(xy)
    ):
        raise ValueError(
            "finite distinct 2D surface coordinates and signed displacements required"
        )
    plane = np.column_stack((np.ones(len(xy)), xy))
    if np.linalg.matrix_rank(plane) != 3:
        raise ValueError("noncollinear datum support required")
    residual = u - plane @ np.linalg.lstsq(plane, u, rcond=None)[0]
    return {
        "warpage_pv_mm": float(np.ptp(residual)),
        "coplanarity_pv_mm": float(np.ptp(residual)),
        "signed_residual_mm": residual.tolist(),
        "datum": "unweighted least-squares z plane; registered sampling/zone required",
        "qualification": False,
    }


def observe_history(frames):
    if not frames or len(frames) > 10000:
        raise ValueError("bounded complete history required")
    result = []
    previous = -math.inf
    zones = None
    for frame in frames:
        t = frame["time_s"]
        if type(t) not in (int, float) or not math.isfinite(t) or t <= previous:
            raise ValueError("strictly ordered finite time history required")
        current_zones = set(frame["zones"])
        if not current_zones or (zones is not None and zones != current_zones):
            raise ValueError("same registered zones at every time required")
        zones, previous = current_zones, t
        result.append(
            {
                "time_s": t,
                "zones": {
                    name: surface_observer(raw["xy_mm"], raw["uz_mm"])
                    for name, raw in frame["zones"].items()
                },
            }
        )
    return {
        "scope": SCOPE,
        "frames": result,
        "max_warpage_pv_mm": max(
            z["warpage_pv_mm"] for f in result for z in f["zones"].values()
        ),
        "adequacy": "NOT_DEMONSTRATED",
        "stress_and_temperature": "require separate raw integration-point/nodal history export; not inferred from displacement",
    }


def mms_fields(xyz, modulus_mpa, poisson):
    """Analytic linear-elastic manufactured displacement/stress/body force."""
    e = positive(modulus_mpa)
    if type(poisson) not in (int, float) or not -1 < poisson < 0.5:
        raise ValueError("stable isotropic Poisson ratio required")
    x = np.asarray(xyz, dtype=float)
    if x.ndim != 2 or x.shape[1] != 3 or not np.isfinite(x).all():
        raise ValueError("finite three-dimensional quadrature points required")
    lam, mu = e * poisson / ((1 + poisson) * (1 - 2 * poisson)), e / (2 * (1 + poisson))
    strain = 3 * x**2
    stress_diagonal = lam * strain.sum(axis=1)[:, None] + 2 * mu * strain
    return {
        "u": x**3,
        "stress_diagonal": stress_diagonal,
        "body_force": -(6 * lam + 12 * mu) * x,
    }


def laminate_estimate(layers, delta_t_c, span_mm):
    """Scalar free-strip laminate A/B/D balance; not full 3D process truth.

    Layers: thickness_mm, modulus_mpa (uniaxial), alpha_per_k. No Poisson
    plate correction is silently inserted. Returns signed curvature and sag.
    """
    positive(span_mm)
    if type(delta_t_c) not in (int, float) or not math.isfinite(delta_t_c):
        raise ValueError("finite temperature change required")
    if type(layers) is not list or not 2 <= len(layers) <= 50:
        raise ValueError("bounded multilayer strip required")
    z = -sum(positive(l["thickness_mm"]) for l in layers) / 2
    a = b = d = n = m = 0.0
    for layer in layers:
        if set(layer) != {"thickness_mm", "modulus_mpa", "alpha_per_k"}:
            raise ValueError("closed strip material required")
        e, h, alpha = (
            positive(layer["modulus_mpa"]),
            positive(layer["thickness_mm"]),
            layer["alpha_per_k"],
        )
        if type(alpha) not in (int, float) or not math.isfinite(alpha):
            raise ValueError("finite expansion coefficient required")
        end = z + h
        aa, bb, dd = e * h, e * (end**2 - z**2) / 2, e * (end**3 - z**3) / 3
        a += aa
        b += bb
        d += dd
        n += aa * alpha * delta_t_c
        m += bb * alpha * delta_t_c
        z = end
    determinant = a * d - b * b
    if determinant <= 0:
        raise ValueError("singular laminate stiffness")
    curvature = (a * m - b * n) / determinant
    return {
        "curvature_per_mm": curvature,
        "signed_midspan_sag_mm": curvature * span_mm**2 / 8,
        "scope": "ELASTIC_FREE_STRIP_SCREEN_ONLY",
        "full_task_prediction": False,
    }


def comparator_ranking(candidates):
    """Cheap-screen export; every candidate needs explicitly mapped strip inputs.

    No feasibility/decision-agreement claim without held-out full-history truth.
    """
    if not candidates or len({c["id"] for c in candidates}) != len(candidates):
        raise ValueError("distinct candidates required")
    import time

    start = time.perf_counter()
    rows = [
        {
            "candidate": c["id"],
            **laminate_estimate(c["layers"], c["delta_t_c"], c["span_mm"]),
        }
        for c in candidates
    ]
    rows.sort(key=lambda r: (abs(r["signed_midspan_sag_mm"]), r["candidate"]))
    elapsed = time.perf_counter() - start
    return {
        "challenge": FAMILY,
        "candidate_ranking": [r["candidate"] for r in rows],
        "predictions": rows,
        "screening_wall_s_per_query": elapsed / len(rows),
        "screening_cost_basis": "NATIVE_TIMING_NOT_BUYER_BENCHMARK",
        "decision_agreement": None,
        "regret_mm": None,
        "abstention": "FULL_HISTORY_UNSUPPORTED",
        "fit_and_retained_verification_cost": "NOT_MEASURED",
        "strong_baseline_gap": "cached full-history FE/response surface not yet supplied",
    }


def pilot_plan():
    return {
        "challenge": FAMILY,
        "scope": SCOPE,
        "grant": None,
        "status": "PROPOSED_HOLD_FULL_HISTORY_INPUTS",
        "cap_eur": 10,
        "rate_eur_node_hour": 1.37,
        "jobs": [
            "free expansion",
            "bimetal curvature",
            "restart material-point history",
            "one full-3D history at two rungs",
        ],
        "equivalent_starts_assumption": 5,
        "node_hours_low_base_high": [1, 4, 8],
        "eur_low_base_high": [1.37, 5.48, 10.96],
        "cost_basis": "ASSUMPTION_NOT_MEASURED_NOT_QUOTE",
        "fits_high_cap": False,
        "stop": "No dispatch until exact pins/rights/laws/state and all prerequisites, quote/all-in cap enforced; reserve before each attempt, no automatic retry",
        "return": [
            "whole-history CPU/wall/RSS",
            "mesh/time steps",
            "all attempts and setup",
            "state continuity",
            "convergence and verification",
            "actual spend and receipts",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("section", choices=("panel", "train", "decks", "pilot"))
    section = parser.parse_args(argv).section
    panel = proposed_panel()
    values = {
        "panel": panel,
        "train": train_plan(panel),
        "pilot": pilot_plan,
        "decks": lambda: [
            deck_draft(d, c) for d in panel["designs"] for c in panel["conditions"]
        ],
    }
    result = values[section]
    print(
        json.dumps(result() if callable(result) else result, indent=2, allow_nan=False)
    )


if __name__ == "__main__":
    main()
