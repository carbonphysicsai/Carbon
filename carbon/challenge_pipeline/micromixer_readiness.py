"""Public DEVELOPMENT f17 preparations; no solver/build/dispatch capability."""

from __future__ import annotations

import argparse
import json
import math
import re
import time

import numpy as np
from scipy.interpolate import RBFInterpolator
from scipy.spatial import Delaunay, QhullError

from carbon.design_search import tasks

FAMILY = "f17"
SCOPE = "PUBLIC_DEVELOPMENT"
OBSERVABLES = ("mixing", "pressure_pa", "residence_s")
DOC = "docs/development/challenge_pipeline/micromixer-readiness/"
SOLVER_COMMIT = "615aae61d7e95e110ca842ca105c799d10f59178"
HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("finite numeric value required")
    return float(value)


def action(depth_um, pitch_um, reversal):
    if not 20 <= finite(depth_um) <= 40 or not 100 <= finite(pitch_um) <= 250:
        raise ValueError("outside packet action support")
    if type(reversal) is not int or not 6 <= reversal <= 10:
        raise ValueError("registered integer half-cycle required")
    return {
        "depth_um": float(depth_um),
        "pitch_um": float(pitch_um),
        "reversal": reversal,
    }


def condition(flow_ul_min, diffusion_m2_s):
    if finite(flow_ul_min) not in (1, 3, 5) or finite(diffusion_m2_s) not in (
        0.5e-10,
        1e-10,
        2e-10,
    ):
        raise ValueError("all and only the supported nine service conditions")
    return {"flow_ul_min": float(flow_ul_min), "diffusion_m2_s": float(diffusion_m2_s)}


def conditions():
    return [condition(q, d) for q in (1, 3, 5) for d in (0.5e-10, 1e-10, 2e-10)]


def physical_key(case):
    return tasks.digest(
        {
            "action": action(**case["action"]),
            "condition": condition(**case["condition"]),
        }
    )


def geometry_recipe(design):
    design = action(**design)
    n = int((10000 - 500) // design["pitch_um"]) + 1
    return {
        "action": design,
        "base_box_um": [10000, 300, 100],
        "groove_width_um": 50,
        "angle_deg": 45,
        "corner_y_um": 100,
        "wall_clearance_um": 10,
        "groove_stations_um": [250 + i * design["pitch_um"] for i in range(n)],
        "half_cycles": [i // design["reversal"] % 2 for i in range(n)],
        "status": "DRAFT_NOT_CAD_VERIFIED",
        "required": [
            "freeze half-cycle orientation/endpoint convention",
            "recess Boolean union clipped to finite floor",
            "reject overlaps/intersections and clipped-width defects",
            "volume includes grooves",
            "two equal-flow inlet patches and true outlet",
        ],
        "periodic_scalar_reset_allowed": False,
    }


def proposed_panel():
    designs = [
        action(d, p, r)
        for d, p, r in (
            (20, 100, 6),
            (20, 250, 10),
            (40, 100, 10),
            (40, 250, 6),
            (30, 175, 8),
        )
    ]
    cases = [
        {"action": a, "condition": c, "rung": {"mesh_um": h}}
        for a in designs
        for c in conditions()
        for h in (10, 5)
    ]
    return {
        "challenge": FAMILY,
        "scope": SCOPE,
        "status": "PROPOSED_NOT_REGISTERED_OR_DISPATCHABLE",
        "cases": cases,
        "case_count": len(cases),
        "designs": designs,
        "conditions": conditions(),
        "flow_starts_with_proved_reuse": 30,
        "scalar_starts": 90,
        "starts_without_reuse": 180,
        "P_dev": {"service_mass_each": 1 / 9},
        "Q": "diagnostic extremes/nominal/refinement; not adopted question Q",
        "w_dev": {"service_weight_each": 1 / 9},
        "question_P_Q_w": None,
        "accepted_manifest_digest": None,
        "image_digest": None,
        "reuse": "UNKNOWN_COMPLETED_AND_SCHEDULED_INDEX_REQUIRED",
        "boundary": "Register >=5 feasible and >=5 infeasible within TWO accepted bands per stratum after first truth; these five seed actions do not satisfy that check",
        "C1": "UNMEASURED",
    }


def train_plan(panel=None):
    panel = proposed_panel() if panel is None else panel
    cases = [
        {"action": action(d, p, r), "condition": c, "rung": {"mesh_um": 10}}
        for d, p, r in ((25, 140, 7), (35, 210, 9))
        for c in conditions()
    ]
    if {physical_key(c) for c in cases} & {physical_key(c) for c in panel["cases"]}:
        raise ValueError(
            "TRAIN overlaps physical action/condition despite different rung/name"
        )
    return {
        "challenge": FAMILY,
        "scope": SCOPE,
        "status": "PROPOSED_NOT_REGISTERED",
        "cases": cases,
        "public_train_digest": None,
        "source_rights": "HUMAN_INPUT",
    }


def kit_domain_check(kit, panel=None):
    panel = proposed_panel() if panel is None else panel
    required = {physical_key(c) for c in panel["cases"]}
    ok = (
        kit.get("scope") == SCOPE
        and required <= set(kit.get("physical_keys", []))
        and set(OBSERVABLES) <= set(kit.get("observables", []))
        and kit.get("finite_scalar_history") is True
        and kit.get("raw_flux_concentration") is True
    )
    return {"covered": ok, "registered_train_implied": False, "qualified": False}


def flow_key(design, flow_ul_min, pins):
    if finite(flow_ul_min) not in (1, 3, 5):
        raise ValueError("supported flow required")
    if (
        type(pins) is not dict
        or set(pins)
        != {
            "image",
            "mesh",
            "geometry",
            "bc",
            "schemes",
            "observer",
            "one_way_coupling_proof",
        }
        or any(not isinstance(v, str) or not HASH.fullmatch(v) for v in pins.values())
    ):
        raise ValueError("exact flow/one-way proof pins required")
    return tasks.digest(
        {
            "action": action(**design),
            "flow_ul_min": float(flow_ul_min),
            "rho_kg_m3": 998,
            "mu_pa_s": 0.001,
            "pins": pins,
        }
    )


def require_flow_cache(receipt, expected_key):
    if (
        type(receipt) is not dict
        or set(receipt) != {"flow_key", "U", "p", "phi", "converged_receipt"}
        or receipt["flow_key"] != expected_key
    ):
        raise ValueError("exact same geometry/Q/mesh/image/BC/numerics flow required")
    if not HASH.fullmatch(expected_key) or any(
        not isinstance(receipt[k], str) or not HASH.fullmatch(receipt[k])
        for k in ("U", "p", "phi", "converged_receipt")
    ):
        raise ValueError("retained U,p,phi and flow convergence identities required")
    return {
        "status": "DOCUMENTARY_CACHE_MATCH_NOT_ADEQUACY",
        "fields": {k: receipt[k] for k in ("U", "p", "phi")},
    }


def deck_draft(design, service, mesh_um=10, *, zero_diffusion_control=False):
    design, service = action(**design), condition(**service)
    if type(zero_diffusion_control) is not bool:
        raise ValueError("explicit numerical-control flag required")
    if zero_diffusion_control:
        service = {**service, "diffusion_m2_s": 0.0}
    if finite(mesh_um) not in (10, 5, 2.5):
        raise ValueError("proposed mesh rung required")
    q = service["flow_ul_min"] * 1e-9 / 60
    speed = q / (300e-6 * 100e-6)
    nu = 0.001 / 998
    header = (
        lambda cls, obj: f"FoamFile {{ version 2.0; format ascii; class {cls}; object {obj}; }}\n"
    )
    return {
        "challenge": FAMILY,
        "scope": (
            "NUMERICAL_DIFFUSION_CONTROL_NOT_P" if zero_diffusion_control else SCOPE
        ),
        "status": "HOLD_CAD_IMAGE_AND_STEADY_CONFIGURATION",
        "solver": {
            "fork": "OpenCFD",
            "release": "v2506",
            "commit": SOLVER_COMMIT,
            "archive_digest": None,
            "dependency_lock": None,
            "image_digest": None,
        },
        "geometry": geometry_recipe(design),
        "condition": service,
        "mesh_um": mesh_um,
        "volume_flow_m3_s": q,
        "equal_inlet_velocity_m_s": speed,
        "files": {
            "constant/transportProperties": header("dictionary", "transportProperties")
            + f"transportModel Newtonian; nu [0 2 -1 0 0 0 0] {nu:.17g}; DT [0 2 -1 0 0 0 0] {service['diffusion_m2_s']:.17g};\n",
            "constant/turbulenceProperties": header(
                "dictionary", "turbulenceProperties"
            )
            + "simulationType laminar;\n",
            "system/flow-controlDict": header("dictionary", "controlDict")
            + "application simpleFoam; startFrom startTime; startTime 0; stopAt endTime; endTime 1000; deltaT 1; writeControl timeStep; writeInterval 100;\n",
            "system/scalar-controlDict": header("dictionary", "controlDict")
            + "application scalarTransportFoam; startFrom startTime; startTime 0; stopAt endTime; endTime 1000; deltaT 1; writeControl timeStep; writeInterval 100;\n",
            "system/fvSchemes": header("dictionary", "fvSchemes")
            + "ddtSchemes { default steadyState; } gradSchemes { default Gauss linear; } divSchemes { default none; div(phi,U) Gauss linearUpwind grad(U); div(phi,T) Gauss limitedLinear 1; } laplacianSchemes { default Gauss linear corrected; } interpolationSchemes { default linear; } snGradSchemes { default corrected; }\n",
            "system/fvSolution": header("dictionary", "fvSolution")
            + "solvers { p { solver GAMG; tolerance 1e-10; relTol 0; smoother GaussSeidel; } U { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-10; relTol 0; } T { solver PBiCGStab; preconditioner DILU; tolerance 1e-10; relTol 0; } } SIMPLE { nNonOrthogonalCorrectors 2; pRefCell 0; pRefValue 0; } relaxationFactors { fields { p 0.3; } equations { U 0.7; T 0.7; } }\n",
            "0/U": header("volVectorField", "U")
            + f"dimensions [0 1 -1 0 0 0 0]; internalField uniform ({speed:.17g} 0 0); boundaryField {{ inlet0 {{ type fixedValue; value uniform ({speed:.17g} 0 0); }} inlet1 {{ type fixedValue; value uniform ({speed:.17g} 0 0); }} outlet {{ type zeroGradient; }} walls {{ type fixedValue; value uniform (0 0 0); }} }}\n",
            "0/p": header("volScalarField", "p")
            + "dimensions [0 2 -2 0 0 0 0]; internalField uniform 0; boundaryField { inlet0 { type zeroGradient; } inlet1 { type zeroGradient; } outlet { type fixedValue; value uniform 0; } walls { type zeroGradient; } }\n",
            "0/T": header("volScalarField", "T")
            + "dimensions [0 0 0 0 0 0 0]; internalField uniform 0.5; boundaryField { inlet0 { type fixedValue; value uniform 0; } inlet1 { type fixedValue; value uniform 1; } outlet { type zeroGradient; } walls { type zeroGradient; } }\n",
        },
        "required_adapter": [
            "exact mesher, checkMesh, nonintersecting recess CAD",
            "prove installed v2506 laminar dictionary and steady scalar configuration",
            "require retained phi; do not allow createPhi fallback",
            "separate flow and scalar folders and stopping receipts",
            "raw boundary advective/diffusive flux plus face U,c,area and fluid volume",
        ],
        "settings_basis": "DRAFT_NUMERICS_NOT_ACCEPTED_TOLERANCES; 1000 iteration ceiling is not a convergence receipt",
    }


def outlet_observer(c, phi_m3_s, volume_m3, inlet_p_kinematic, outlet_p_kinematic):
    c, phi = np.asarray(c, dtype=float), np.asarray(phi_m3_s, dtype=float)
    if (
        c.ndim != 1
        or not len(c)
        or phi.shape != c.shape
        or not np.isfinite(c).all()
        or not np.isfinite(phi).all()
        or np.any(phi < 0)
        or phi.sum() <= 0
    ):
        raise ValueError(
            "observer inapplicable: nonfinite flux/concentration, backflow or zero outlet"
        )
    volume = finite(volume_m3)
    if volume <= 0:
        raise ValueError("actual fluid volume including recesses required")
    mean = float(np.dot(phi, c) / phi.sum())
    variance = float(np.dot(phi, (c - mean) ** 2) / phi.sum())
    return {
        "mixing": 1 - math.sqrt(variance / 0.25),
        "mean_c": mean,
        "variance_c": variance,
        "pressure_pa": 998 * (finite(inlet_p_kinematic) - finite(outlet_p_kinematic)),
        "residence_s": volume / float(phi.sum()),
        "volume_flow_m3_s": float(phi.sum()),
        "raw_c_min_max": [float(c.min()), float(c.max())],
        "reference_bounds_ok": bool(c.min() >= -0.001 and c.max() <= 1.001),
        "residence_definition": "fluid volume/flow, not arrival-time distribution",
    }


def balances(
    volume_flux_outward,
    advective_solute_outward,
    diffusive_solute_outward,
    *,
    incoming_volume,
    incoming_solute,
    storage_rate=0,
    solute_floor=None,
):
    """Boundary mass and solute residuals, outward signs, every boundary face.

    The solute residual is normalised by the incoming solute flux; with an
    explicit ``solute_floor`` (F17-SCIENCE-VALUES-01 B2: 1e-6 x Q in
    concentration units) a zero-solute control is normalised by that floor
    instead of a tiny incoming flux. Without a floor zero incoming solute is
    refused.
    """
    arrays = [
        np.asarray(v, dtype=float)
        for v in (
            volume_flux_outward,
            advective_solute_outward,
            diffusive_solute_outward,
        )
    ]
    if (
        any(a.ndim != 1 or not len(a) or not np.isfinite(a).all() for a in arrays)
        or len({len(a) for a in arrays}) != 1
    ):
        raise ValueError(
            "same complete boundary-face support with outward signs required"
        )
    q, solute = finite(incoming_volume), finite(incoming_solute)
    if solute_floor is not None and finite(solute_floor) > 0:
        solute = max(solute, float(solute_floor))
    if q <= 0 or solute <= 0:
        raise ValueError(
            "nonzero incoming normalization; zero-solute controls need approved absolute floor"
        )
    return {
        "mass_residual_fraction": abs(float(arrays[0].sum())) / q,
        "solute_residual_fraction": abs(
            float(arrays[1].sum() + arrays[2].sum()) + finite(storage_rate)
        )
        / solute,
    }


def rectangular_pressure_pa(flow_m3_s, length_m=0.01, width_m=300e-6, height_m=100e-6):
    q, length, width, height = [
        finite(x) for x in (flow_m3_s, length_m, width_m, height_m)
    ]
    if min(q, length, width, height) <= 0 or width < height:
        raise ValueError(
            "developed rectangular duct, width>=height and positive dimensions required"
        )
    correction = 1 - 192 * height / (math.pi**5 * width) * sum(
        math.tanh(n * math.pi * width / (2 * height)) / n**5 for n in range(1, 202, 2)
    )
    return 12 * 0.001 * length * q / (width * height**3 * correction)


def scalar_mms(xyz, velocity, diffusivity):
    x = np.asarray(xyz, dtype=float)
    u, d = finite(velocity), finite(diffusivity)
    if x.ndim != 2 or x.shape[1] != 3 or not np.isfinite(x).all() or d < 0:
        raise ValueError("finite 3D MMS points and nonnegative diffusion required")
    s = np.sin(math.pi * x)
    c = 0.5 + 0.1 * np.prod(s, axis=1)
    dx = 0.1 * math.pi * np.cos(math.pi * x[:, 0]) * s[:, 1] * s[:, 2]
    return {"concentration": c, "source": u * dx + 3 * d * math.pi**2 * (c - 0.5)}


def flow_mms(xyz, viscosity):
    x = np.asarray(xyz, dtype=float)
    nu = finite(viscosity)
    if x.ndim != 2 or x.shape[1] != 3 or not np.isfinite(x).all() or nu <= 0:
        raise ValueError(
            "finite 3D MMS points and positive kinematic viscosity required"
        )
    sx, sy, sz = np.sin(math.pi * x).T
    cx, cy, cz = np.cos(math.pi * x).T
    u = np.column_stack((sx * cy, -cx * sy, np.zeros(len(x))))
    force = (
        np.column_stack((math.pi * sx * cx, math.pi * sy * cy, 0.1 * math.pi * cz))
        + 2 * nu * math.pi**2 * u
    )
    return {"velocity": u, "kinematic_pressure": 0.1 * sz, "source_acceleration": force}


def _features(a, c):
    return [
        (a["depth_um"] - 20) / 20,
        (a["pitch_um"] - 100) / 150,
        (a["reversal"] - 6) / 4,
        (c["flow_ul_min"] - 1) / 4,
        math.log2(c["diffusion_m2_s"] / 0.5e-10) / 2,
    ]


def measure(export):
    """Fixed-RBF whole-geometry held-out comparator; no calibration/solver runs.

    Requires all nine conditions per geometry and producer adequacy verdicts.
    It carries acquisition cost without validating a physical cost receipt.
    Output is a diagnostic, not accepted reference evidence.
    """
    if (
        type(export) is not dict
        or set(export) != {"challenge", "scope", "rows", "acquisition_cost"}
        or export["challenge"] != FAMILY
        or export["scope"] not in (SCOPE, "SYNTHETIC_FIXTURE")
    ):
        raise ValueError("explicit public/fixture development export required")
    if type(export["rows"]) is not list or not 45 <= len(export["rows"]) <= 10000:
        raise ValueError("at least five complete geometry panels required")
    groups = {}
    for row in export["rows"]:
        if type(row) is not dict or set(row) != {
            "action",
            "condition",
            "values",
            "reference_status",
        }:
            raise ValueError("closed public panel row required")
        a, c = action(**row["action"]), condition(**row["condition"])
        if type(row["values"]) is not dict or set(row["values"]) != set(OBSERVABLES):
            raise ValueError("mixing/pressure/residence observables required")
        values = [finite(row["values"][k]) for k in OBSERVABLES]
        if row["reference_status"] not in ("RESOLVED", "UNRESOLVED"):
            raise ValueError("reference failure never becomes a candidate failure")
        key = tasks.digest(a)
        group = groups.setdefault(key, [])
        if any(r["condition"] == c for r in group):
            raise ValueError("duplicate physical row")
        group.append(
            {
                "action": a,
                "condition": c,
                "values": values,
                "reference_status": row["reference_status"],
            }
        )
    if any(len(g) != 9 for g in groups.values()) or len(groups) < 5:
        raise ValueError("whole-geometry folds need all nine conditions")
    predictions, fits = [], []
    fit_cpu = fit_wall = query_cpu = query_wall = 0.0
    query_count = 0
    begin_cpu, begin_wall = time.process_time(), time.perf_counter()
    for held, group in sorted(groups.items()):
        fit = [
            r
            for key, other in groups.items()
            if key != held
            for r in other
            if r["reference_status"] == "RESOLVED"
        ]
        if len(fit) < 36:
            predictions.extend(
                {
                    "geometry": held,
                    "condition": r["condition"],
                    "prediction": None,
                    "reference": dict(zip(OBSERVABLES, r["values"])),
                    "reference_status": r["reference_status"],
                    "reason": "insufficient resolved fit",
                }
                for r in group
            )
            continue
        x = np.array([_features(r["action"], r["condition"]) for r in fit])
        y = np.array([r["values"] for r in fit])
        cpu, wall = time.process_time(), time.perf_counter()
        try:
            hull = Delaunay(np.unique(x[:, :3], axis=0))
        except QhullError:
            hull = None
        model = RBFInterpolator(x, y, kernel="linear", degree=0, smoothing=1e-8)
        fit_cpu += time.process_time() - cpu
        fit_wall += time.perf_counter() - wall
        fits.append(
            {
                "held_geometry": held,
                "fit_geometry_keys": sorted(set(groups) - {held}),
                "fit_rows": len(fit),
            }
        )
        for row in group:
            cpu, wall = time.process_time(), time.perf_counter()
            query = np.array(_features(row["action"], row["condition"]))
            within = (
                hull is not None
                and hull.find_simplex(query[:3]) >= 0
                and np.all(query[3:] >= x[:, 3:].min(axis=0))
                and np.all(query[3:] <= x[:, 3:].max(axis=0))
            )
            values = model(query[None, :])[0] if within else None
            query_cpu += time.process_time() - cpu
            query_wall += time.perf_counter() - wall
            query_count += 1
            predictions.append(
                {
                    "geometry": held,
                    "condition": row["condition"],
                    "prediction": (
                        None
                        if values is None
                        else dict(zip(OBSERVABLES, values.tolist()))
                    ),
                    "reference": dict(zip(OBSERVABLES, row["values"])),
                    "reference_status": row["reference_status"],
                    "reason": (
                        None
                        if values is not None
                        else "outside fit geometry hull or condition support"
                    ),
                }
            )
    covered = [
        r
        for r in predictions
        if r["prediction"] is not None and r["reference_status"] == "RESOLVED"
    ]
    error = {
        k: (
            sum(abs(r["prediction"][k] - r["reference"][k]) for r in covered)
            / len(covered)
            if covered
            else None
        )
        for k in OBSERVABLES
    }
    ranking = []
    for key in sorted(groups):
        rows = [r for r in predictions if r["geometry"] == key]
        if len(rows) == 9 and all(r["prediction"] is not None for r in rows):
            ranking.append((min(r["prediction"]["mixing"] for r in rows), key))
    return {
        "challenge": FAMILY,
        "scope": export["scope"],
        "method": "fixed linear RBF; leave-one-geometry-out all nine conditions",
        "predictions": predictions,
        "folds": fits,
        "pointwise_mae": error,
        "candidate_ranking": [
            key for _, key in sorted(ranking, key=lambda v: (-v[0], v[1]))
        ],
        "coverage_rows": len(covered),
        "abstained_rows": sum(r["prediction"] is None for r in predictions),
        "screening_cost": {
            "native_fit_and_query_cpu_s": time.process_time() - begin_cpu,
            "native_fit_and_query_wall_s": time.perf_counter() - begin_wall,
            "fit_cpu_s": fit_cpu,
            "fit_wall_s": fit_wall,
            "query_cpu_s_per_query": query_cpu / query_count if query_count else None,
            "query_wall_s_per_query": query_wall / query_count if query_count else None,
            "queries_including_abstentions": query_count,
            "peak_rss": "NOT_MEASURED",
        },
        "acquisition_cost": export["acquisition_cost"],
        "retained_verification_cost": "NOT_MEASURED",
        "decision_agreement": None,
        "regret_M": None,
        "decision_policy": "Use registered neutral tasks + accepted reference bands/settled verdicts; no fitted uncertainty invented",
    }


def decision_report(report, registered):
    """Reuse the neutral v1 judge with supplied requirements and reference bands.

    Candidate IDs are geometry digests; condition IDs are condition digests.
    An incomplete held-out prediction abstains, never gains lookup truth.
    Runnable optimizers remain owned by their separately registered v2 route.
    """
    if (
        report.get("challenge") != FAMILY
        or report.get("scope") not in (SCOPE, "SYNTHETIC_FIXTURE")
        or registered["identity"]["challenge"] != FAMILY
    ):
        raise ValueError("matching development comparator/task required")
    constraints = {r["quantity"]: r for r in registered["limits"]}
    if set(constraints) != set(OBSERVABLES) or any(
        "band" not in r for r in constraints.values()
    ):
        raise ValueError(
            "all three registered buyer constraints with explicit accepted bands required"
        )
    for name, unit in zip(OBSERVABLES, ("1", "Pa", "s")):
        row = constraints[name]
        if row["unit"] != unit or finite(row["band"]) < 0:
            raise ValueError(
                "registered units and nonnegative finite reference bands required"
            )
        finite(row["value"])
    if not (
        0.8 <= constraints["mixing"]["value"] <= 0.85
        and 200 <= constraints["pressure_pa"]["value"] <= 250
        and 15 <= constraints["residence_s"]["value"] <= 20
    ):
        raise ValueError("outside supported question-law requirements")
    if (
        constraints["mixing"]["op"] != ">="
        or constraints["mixing"]["value"] < 0.8
        or constraints["pressure_pa"]["op"] != "<="
        or constraints["pressure_pa"]["value"] > 250
        or constraints["residence_s"]["op"] != "<="
        or constraints["residence_s"]["value"] > 20
    ):
        raise ValueError("do not relax selected buyer constraints")
    if {c["id"] for c in registered["conditions"]} != {
        tasks.digest(c) for c in conditions()
    } or registered["objective"] != {
        "quantity": "mixing",
        "unit": "1",
        "sense": "max",
        "aggregate": "worst",
    }:
        raise ValueError("complete nine-condition worst-M task required")
    keys = {r["geometry"] for r in report["predictions"]}
    if keys != set(registered["candidates"]):
        raise ValueError("exact complete candidate-bank match required")
    pred, ref = {}, {}
    for row in report["predictions"]:
        key = (row["geometry"], tasks.digest(row["condition"]))
        if row["prediction"] is not None:
            pred[key] = row["prediction"]
        if row.get("reference_status") == "RESOLVED":
            ref[key] = row["reference"]
    commitment = tasks.commit(
        registered, pred, model_id="f17-rbf-whole-geometry-holdout"
    )
    judged = tasks.judge(registered, commitment, ref)
    truth, predicted = tasks.assess(registered, ref, reference=True), tasks.assess(
        registered, pred
    )
    resolved = [
        c
        for c in registered["candidates"]
        if truth[c]["feasible"] is not None and predicted[c]["feasible"] is not None
    ]
    return {
        **judged,
        "exact_pick_agreement": judged["reference_resolved"]
        and judged["selected"] == judged["best"],
        "feasibility_agreement": (
            sum(truth[c]["feasible"] == predicted[c]["feasible"] for c in resolved)
            / len(resolved)
            if resolved
            else None
        ),
        "feasibility_compared": len(resolved),
        "abstained_candidates": sum(
            predicted[c]["feasible"] is None for c in predicted
        ),
        "reference_unresolved_candidates": sum(
            truth[c]["feasible"] is None for c in truth
        ),
        "regret_M": judged["regret"],
        "qualified": False,
    }


def pilot_plan():
    return {
        "challenge": FAMILY,
        "scope": SCOPE,
        "status": "PROPOSED_NO_GRANT",
        "cap_eur": 10,
        "rate_eur_node_hour": 1.37,
        "jobs": [
            "smooth developed duct/analytic scalar",
            "full-length nominal grooved channel, one flow/two D",
            "fresh-pair reuse witness",
            "highest-Pe mesh/scheme refinement and zero-D diagnostic",
        ],
        "tuples": [
            {
                "geometry": "smooth-control",
                "flow_ul_min": 1,
                "diffusion_m2_s": 1e-10,
                "mesh_um": 10,
                "fresh_flow": True,
            },
            {
                "geometry": action(30, 175, 8),
                "flow_ul_min": 5,
                "diffusion_m2_s": 0.5e-10,
                "mesh_um": 10,
                "fresh_flow": True,
            },
            {
                "geometry": action(30, 175, 8),
                "flow_ul_min": 5,
                "diffusion_m2_s": 2e-10,
                "mesh_um": 10,
                "fresh_flow": False,
            },
            {
                "geometry": action(30, 175, 8),
                "flow_ul_min": 5,
                "diffusion_m2_s": 0.5e-10,
                "mesh_um": 10,
                "fresh_flow": True,
                "purpose": "reuse-witness-not-duplicate-discount",
            },
            {
                "geometry": action(30, 175, 8),
                "flow_ul_min": 5,
                "diffusion_m2_s": 0.5e-10,
                "mesh_um": 5,
                "fresh_flow": True,
            },
            {
                "geometry": action(30, 175, 8),
                "flow_ul_min": 5,
                "diffusion_m2_s": 0,
                "mesh_um": 5,
                "fresh_flow": False,
                "scope": "NUMERICAL_DIFFUSION_CONTROL_NOT_P",
            },
        ],
        "hypothesis_complete_design_cpu_h": {"p50": 0.75, "p95": 4},
        "hypothesis_peak_rss_gib": {"p50": 4, "p95": 16},
        "pilot_node_h_low_base_high": [1, 4, 8],
        "pilot_eur_low_base_high": [1.37, 5.48, 10.96],
        "basis": "UNMEASURED_HYPOTHESES_NOT_QUOTE",
        "high_fits_cap": False,
        "dispatch_allowed": False,
        "grant": None,
        "requires": [
            "exact image/CAD/mesh/observer pins",
            "all seven readiness items or exact paid-output exception",
            "accepted verification and scope",
            "quote/all-in reserve within EUR10 before every attempt",
            "no retries; preserve partial/failure ledger",
        ],
        "return": [
            "separate flow/scalar starts, CPU/wall/RSS",
            "mesh/extractor/setup/repeats/failures",
            "raw fields, conservation, zero-D/refinement and reuse comparison",
            "bank and baseline cost with no free velocity oracle",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "section", choices=("panel", "train", "decks", "pilot", "compare")
    )
    parser.add_argument("--public-export")
    args = parser.parse_args(argv)
    if args.section == "compare":
        if args.public_export is None:
            parser.error("explicit public DEVELOPMENT export required")
        with open(args.public_export, encoding="utf-8") as source:
            result = measure(json.load(source))
    else:
        p = proposed_panel()
        options = {
            "panel": p,
            "train": train_plan(p),
            "pilot": pilot_plan,
            "decks": lambda: [
                deck_draft(a, c) for a in p["designs"] for c in p["conditions"]
            ],
        }
        result = options[args.section]
        result = result() if callable(result) else result
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
