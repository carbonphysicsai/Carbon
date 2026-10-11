"""Public DEVELOPMENT BFS preparation. No solver, network or protected-data access.

All generated material is a draft until source-backed registration on main.
Missing physical support is an error, never a default or candidate failure.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import re
from pathlib import Path

from carbon.design_search import tasks

FAMILY = "backward-facing-step"
SU2_SOURCE = "bc15466602a687d6fb796d5df7a12ce3fde0949a"
Q = {"nominal": 0.4, "corners": 0.2, "frontier": 0.3, "transition": 0.1}


class PreparationError(ValueError):
    """Unsupported or incomplete reference preparation; not model failure."""


def number(value, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise PreparationError("finite physical value required")
    if positive and value <= 0:
        raise PreparationError("positive physical value required")
    return float(value)


def interval(value):
    if type(value) is not list or len(value) != 2:
        raise PreparationError("explicit registered interval required")
    lo, hi = map(number, value)
    if lo > hi:
        raise PreparationError("reversed interval")
    return lo, hi


def registration(data):
    if (
        data.get("family") != FAMILY
        or data.get("scope") not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
        or data.get("registration_digest")
        != tasks.digest({k: v for k, v in data.items() if k != "registration_digest"})
    ):
        raise PreparationError(
            "digest-bound public/fixture family registration required"
        )
    return data


def actions(data, *, seed, count):
    """Quantized monotone Bezier recovery contours; precision is caller registered.

    Monotone control ordinates imply a monotone spline. Coordinates are in H.
    Endpoints, clearance and dimensions must be registered, not inferred from
    NASA's source point. No claim of catalogue novelty or manufacturing fitness.
    """
    registration(data)
    if type(count) is not int or not 1 <= count <= 1000:
        raise PreparationError("bounded count required")
    g = data["grammar"]
    n = g["interior_dofs"]
    if type(n) is not int or not 1 <= n <= 32:
        raise PreparationError("exact bounded spline DOFs required")
    step = number(g["ordinate_step_over_H"], positive=True)
    start, end = interval(g["wall_ordinates_over_H"])
    if start == end or not math.isclose(
        (end - start) / step, round((end - start) / step)
    ):
        raise PreparationError("distinct lattice-aligned wall endpoints required")
    length_lo, length_hi = interval(g["recovery_length_over_H"])
    length_step = number(g["length_step_over_H"], positive=True)
    if length_lo <= 0 or not math.isclose(
        (length_hi - length_lo) / length_step,
        round((length_hi - length_lo) / length_step),
    ):
        raise PreparationError("positive lattice-aligned length envelope required")
    rng, seen, result = random.Random(seed), set(), []
    attempts = 0
    while len(result) < count and attempts < count * 100:
        attempts += 1
        # Stars-and-bars bijection: uniform weakly increasing lattice vectors,
        # unlike sorting iid discrete samples (which overweights distinct entries).
        ticks = round((end - start) / step)
        ordinates = [
            v - i for i, v in enumerate(sorted(rng.sample(range(ticks + n), n)))
        ]
        length = length_lo + length_step * rng.randint(
            0, round((length_hi - length_lo) / length_step)
        )
        row = {
            "length_over_H": length,
            "control_y_over_H": [start, *[start + step * i for i in ordinates], end],
        }
        key = tasks.digest(row)
        if key not in seen:
            seen.add(key)
            result.append(row)
    if len(result) != count:
        raise PreparationError("action lattice exhausted; no silent duplicate designs")
    return {
        "scope": data["scope"],
        "dispatchable": False,
        "actions": result,
        "attempts": attempts,
        "duplicate_rejections": attempts - count,
        "novelty": "UNRESOLVED_PENDING_CATALOGUE_AND_DECISION_TEST",
    }


def contour(action, samples=65):
    if type(samples) is not int or not 3 <= samples <= 4097:
        raise PreparationError("bounded contour samples required")
    ys = [number(y) for y in action["control_y_over_H"]]
    if len(ys) < 3 or any(a > b for a, b in itertools.pairwise(ys)):
        raise PreparationError("monotone spline required")
    length = number(action["length_over_H"], positive=True)
    degree = len(ys) - 1
    return [
        [
            length * t,
            sum(
                math.comb(degree, i) * t**i * (1 - t) ** (degree - i) * y
                for i, y in enumerate(ys)
            ),
        ]
        for t in (i / (samples - 1) for i in range(samples))
    ]


def conditions(data, *, seed, count, proposal="P"):
    """P uniform joint support; Q allocation distinct from score frequency.

    Frontier/transition pools are preregistered public development proposals,
    not candidate-output adaptation. No settled NONE_FEASIBLE redraw occurs.
    """
    registration(data)
    if type(count) is not int or not 1 <= count <= 10000 or proposal not in ("P", "Q"):
        raise PreparationError("bounded P or Q draw required")
    bounds = {k: interval(v) for k, v in data["conditions"].items()}
    required = {"Re_H", "Mach", "inlet_thickness_over_H"}
    if set(bounds) != required or bounds["Re_H"][0] <= 0 or bounds["Mach"][0] <= 0:
        raise PreparationError("explicit supported Re_H/Mach/inlet envelope required")
    rng = random.Random(seed)

    def uniform():
        return {k: rng.uniform(lo, hi) for k, (lo, hi) in bounds.items()}

    labels = ["population"] * count
    if proposal == "Q":
        if count % 10:
            raise PreparationError(
                "exact 40/20/30/10 allocation needs a multiple of ten"
            )
        labels = [
            label for label, mass in Q.items() for _ in range(round(count * mass))
        ]
        rng.shuffle(labels)
    result = []
    for label in labels:
        if label in ("population", "nominal"):
            row = uniform()
        elif label == "corners":
            row = {k: rng.choice([lo, hi]) for k, (lo, hi) in bounds.items()}
        else:
            pool = data.get("diagnostic_pools", {}).get(label)
            if not pool:
                raise PreparationError("registered frontier/transition pool missing")
            row = dict(rng.choice(pool))
        if set(row) != required or any(
            not lo <= number(row[k]) <= hi for k, (lo, hi) in bounds.items()
        ):
            raise PreparationError("proposal outside registered P support")
        result.append({"condition": row, "draw_role": label})
    return {
        "family": FAMILY,
        "scope": data["scope"],
        "population": "REPRESENTATIVE",
        "dispatchable": False,
        "proposal": proposal,
        "rows": result,
        "Q": Q,
        "w": "BUYER_FREQUENCY_UNDER_P_NOT_Q",
        "none_feasible": "RETAIN_NO_REDRAW",
    }


def calibration_check(strata, *, minimum_useful_improvement, minimum_margin_spread):
    """Audit public calibration before freezing P; never filters exam draws."""
    mui = number(minimum_useful_improvement, positive=True)
    spread = number(minimum_margin_spread, positive=True)
    if not strata:
        raise PreparationError("nonempty complete public strata required")
    rows = []
    feasible_sets, best_sets = [], []
    winners = set()
    inventory = None
    for name, designs in strata.items():
        if not designs or len({d["design"] for d in designs}) != len(designs):
            raise PreparationError("distinct complete designs required")
        current = {d["design"] for d in designs}
        if inventory is not None and current != inventory:
            raise PreparationError(
                "same complete action inventory in every stratum required"
            )
        inventory = current
        if any(type(d["feasible"]) is not bool for d in designs):
            return {"status": "UNRESOLVED", "reason": "unresolved public calibration"}
        passing = {d["design"] for d in designs if d["feasible"]}
        feasible_sets.append(passing)
        margins = [number(d["margin"]) for d in designs]
        near = [d for d in designs if abs(number(d["margin"])) <= 2 * mui]
        ranked = sorted(
            (number(d["objective"]), d["design"]) for d in designs if d["feasible"]
        )
        if ranked:
            winners.add(ranked[0][1])
            best_sets.append(
                {
                    d["design"]
                    for d in designs
                    if d["feasible"]
                    and number(d["objective"]) - ranked[0][0] <= 0.5 * mui
                }
            )
        else:
            best_sets.append(set())
        rate = len(passing) / len(designs)
        rows.append(
            {
                "stratum": name,
                "pass_rate": rate,
                "near_feasible": sum(d["feasible"] for d in near),
                "near_infeasible": sum(not d["feasible"] for d in near),
                "margin_spread": max(margins) - min(margins),
                "rate_rule": 0.2 <= rate <= 0.8,
            }
        )
    passed = all(
        r["rate_rule"]
        and r["near_feasible"] >= 5
        and r["near_infeasible"] >= 5
        and r["margin_spread"] >= spread
        for r in rows
    )
    common = sorted(set.intersection(*feasible_sets))
    common_best = sorted(set.intersection(*best_sets))
    return {
        "status": (
            "CALIBRATION_PASSES"
            if passed and common and not common_best and len(winners) > 1
            else "CALIBRATION_FAILS"
        ),
        "strata": rows,
        "common_feasible": common,
        "distinct_winners": sorted(winners),
        "common_value_equivalent_pick": common_best,
        "dispatchable": False,
        "requires_frozen_requirement_intervals": True,
    }


def questions(data, *, seed, count):
    """Continuous requirements and full service briefs from a frozen public law.

    This is a DEVELOPMENT rehearsal, not hidden bank generation. Requirement
    intervals cannot be supplied by candidate outcomes. Calibration witness
    identity is retained but a producer digest alone does not qualify the law.
    """
    registration(data)
    if type(count) is not int or not 1 <= count <= 1000:
        raise PreparationError("bounded question count required")
    law = data["requirement_law"]
    if not re.fullmatch(r"[0-9a-f]{64}", law["public_calibration_sha256"]):
        raise PreparationError("measured public calibration identity required")
    bounds = interval(law["reattachment_max_over_H"])
    points = law["service_points_per_brief"]
    if type(points) is not int or not 1 <= points <= 64:
        raise PreparationError("registered complete service-brief size required")
    weights = law["duty_weights"]
    if (
        type(weights) is not list
        or len(weights) != points
        or any(number(w, positive=True) <= 0 for w in weights)
        or not math.isclose(sum(weights), 1)
    ):
        raise PreparationError("positive normalized per-brief buyer frequency required")
    draws = conditions(data, seed=seed, count=count * points)["rows"]
    rng = random.Random(seed + 1)
    return {
        "family": FAMILY,
        "scope": data["scope"],
        "dispatchable": False,
        "exposure_E": 1,
        "independent_unit": "COMPLETE_SERVICE_BRIEF",
        "none_feasible": "RETAIN_NO_REDRAW",
        "questions": [
            {
                "conditions": draws[i * points : (i + 1) * points],
                "requirements": {
                    "reattachment_max_over_H": rng.uniform(*bounds),
                    "exit_reverse_flow_allowed": False,
                },
                "objective": "DUTY_WEIGHTED_MEAN_LOSS_PA",
                "calibration_source": law["public_calibration_sha256"],
                "duty_weights": law["duty_weights"],
            }
            for i in range(count)
        ],
    }


def plane_observer(rows, *, gamma):
    """Compressible ideal-gas stagnation pressure, signed mass-flux weighting.

    Reverse flow is reported, never dropped from integration. Supplied samples
    must be the registered complete plane quadrature, not surface shifted Cp.
    """
    gamma = number(gamma, positive=True)
    if gamma <= 1 or not rows:
        raise PreparationError("gas gamma and nonempty plane quadrature required")
    mass = reverse = total = 0.0
    for r in rows:
        rho = number(r["rho_kg_m3"], positive=True)
        p = number(r["p_static_pa"], positive=True)
        vx, vy = number(r["u_m_s"]), number(r["v_m_s"])
        un, area = number(r["u_normal_m_s"]), number(r["area_m2"], positive=True)
        m2 = (vx * vx + vy * vy) / (gamma * p / rho)
        pt = p * (1 + (gamma - 1) * m2 / 2) ** (gamma / (gamma - 1))
        flux = rho * un * area
        mass += flux
        total += flux * pt
        reverse += max(0, -flux)
    if mass <= 0:
        raise PreparationError("nonpositive net flow is unresolved reference")
    return {
        "mass_flow_kg_s": mass,
        "total_pressure_pa": total / mass,
        "reverse_mass_kg_s": reverse,
        "reverse_flow_detected": reverse > 0,
        "coverage": "REGISTERED_SAMPLED_PLANE_ONLY",
    }


def reattachment(x_over_H, signed_cf):
    x, cf = [number(v) for v in x_over_H], [number(v) for v in signed_cf]
    if len(x) != len(cf) or len(x) < 3 or any(a >= b for a, b in itertools.pairwise(x)):
        raise PreparationError("ordered complete downstream wall samples required")
    if x[0] < 0 or any(v == 0 for v in cf) or cf[-1] < 0:
        return {"status": "UNRESOLVED", "reattachment_over_H": None}
    crossings = [
        x[i] - cf[i] * (x[i + 1] - x[i]) / (cf[i + 1] - cf[i])
        for i in range(len(x) - 1)
        if cf[i] < 0 < cf[i + 1]
    ]
    if not crossings and any(v < 0 for v in cf):
        return {"status": "UNRESOLVED", "reattachment_over_H": None}
    return {
        "status": "RESOLVED_SAMPLED",
        "reattachment_over_H": max(crossings, default=0.0),
        "crossings_over_H": crossings,
        "policy": "LAST_NEGATIVE_TO_POSITIVE_THROUGH_WINDOW",
    }


def observe(inlet, outlet, wall, *, gamma, rho_ref, u_ref):
    up, down = plane_observer(inlet, gamma=gamma), plane_observer(outlet, gamma=gamma)
    if up["reverse_flow_detected"]:
        raise PreparationError("developed inlet has reverse flow; unresolved reference")
    loss = up["total_pressure_pa"] - down["total_pressure_pa"]
    norm = number(rho_ref, positive=True) * number(u_ref, positive=True) ** 2 / 2
    return {
        "loss_pa": loss,
        "loss_dynamic_normalized": loss / norm,
        "exit_reverse_flow": down["reverse_flow_detected"],
        "mass_residual_fraction": abs(up["mass_flow_kg_s"] - down["mass_flow_kg_s"])
        / up["mass_flow_kg_s"],
        **reattachment(wall["x_over_H"], wall["signed_cf"]),
        "reference_acceptance": "UNRESOLVED_PENDING_REGISTERED_CONSERVATION_AND_REFINEMENT",
    }


def deck(action, condition, physical):
    """Render SU2 inputs without launching it. Full inlet/mesh pins are required.

    Mesh materialization and NASA SSTm equation audit remain operator tasks.
    A renderable config is not proof its solver package or fields are adequate.
    """
    contour(action)
    for name in ("Re_H", "Mach", "inlet_thickness_over_H"):
        number(condition[name], positive=True)
    for name in ("mesh_file", "inlet_file"):
        if not re.fullmatch(r"[A-Za-z0-9_-]+\.(su2|dat)", physical[name]):
            raise PreparationError("plain registered asset filename required")
    for name in ("mesh_sha256", "inlet_sha256", "sst_mapping_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", physical[name]):
            raise PreparationError("immutable mesh/inlet/SSTm mapping required")
    if physical["sst_options"] not in ("V1994m", "V2003m"):
        raise PreparationError("explicit source-audited SST variant required")
    values = {
        "SOLVER": "RANS",
        "KIND_TURB_MODEL": "SST",
        "SST_OPTIONS": physical["sst_options"],
        "MESH_FILENAME": physical["mesh_file"],
        "MACH_NUMBER": condition["Mach"],
        "REYNOLDS_NUMBER": condition["Re_H"],
        "REYNOLDS_LENGTH": number(physical["H_m"], positive=True),
        "SPECIFIED_INLET_PROFILE": "YES",
        "INLET_FILENAME": physical["inlet_file"],
        "MARKER_INLET": f"(inlet, {number(physical['inlet_total_temperature_k'], positive=True)}, {number(physical['inlet_total_pressure_pa'], positive=True)}, 1.0, 0.0, 0.0)",
        "MARKER_OUTLET": f"(outlet, {number(physical['outlet_static_pa'], positive=True)})",
        "MARKER_HEATFLUX": "(lower_wall, 0.0, upper_wall, 0.0)",
        "MUSCL_FLOW": "YES",
        "CONV_NUM_METHOD_FLOW": "ROE",
        "OUTPUT_FILES": "(PARAVIEW_ASCII, SURFACE_PARAVIEW_ASCII)",
    }
    # Profile pins supply developed velocity AND turbulence; do not synthesize
    # a freestream turbulence intensity as a substitute for the NASA profile.
    return {
        "family": FAMILY,
        "dispatchable": False,
        "status": "UNVERIFIED_DECK_DRAFT",
        "source_commit": SU2_SOURCE,
        "contour_over_H": contour(action),
        "condition": condition,
        "asset_pins": physical,
        "config": "\n".join(f"{k}= {v}" for k, v in values.items()) + "\n",
        "observer": {
            "inlet_plane_x_over_H": number(physical["inlet_plane_x_over_H"]),
            "exit_plane_x_over_H": number(physical["exit_plane_x_over_H"]),
            "plane_fields": ["rho", "pressure", "velocity_x", "velocity_y"],
            "wall_fields": ["x_over_H", "signed_cf"],
            "function": "observe",
        },
        "holds": [
            "COMPLETE_DEPENDENCY_IMAGE_PIN",
            "MESH_PROFILE_MATCH",
            "NASA_SSTm_EQUATION_AUDIT",
            "CODE_SOLUTION_CONSERVATION_ACCEPTANCE",
        ],
    }


def train_plan(challenge, generated, panel, *, count):
    """Physical disjointness ignores refinement rung and candidate labels."""
    if challenge != FAMILY or type(count) is not int or count <= 0:
        raise PreparationError("explicit family and positive TRAIN count required")

    def key(row):
        if row.get("scope") not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE"):
            raise PreparationError("explicit public TRAIN/panel custody required")
        return tasks.digest({"action": row["action"], "condition": row["condition"]})

    excluded = {key(r) for r in panel}
    seen, retained = set(), []
    for row in generated:
        k = key(row)
        if k not in excluded and k not in seen:
            retained.append(row)
            seen.add(k)
    if len(retained) < count:
        raise PreparationError("insufficient distinct disjoint public proposals")
    return {
        "family": challenge,
        "scope": "PUBLIC_DEVELOPMENT",
        "status": "PLAN_NOT_TRAINED",
        "cases": retained[:count],
        "panel_physical_keys": sorted(excluded),
        "dispatchable": False,
        "registration_on_main": "REQUIRED",
    }


def domain_coverage(challenge, cases, domain):
    if challenge != FAMILY or not cases:
        raise PreparationError("nonempty explicit family panel required")
    gaps = []
    for row in cases:
        for group in ("action", "condition"):
            for name, value in row[group].items():
                if name not in domain.get(group, {}):
                    gaps.append(f"{group}.{name}: missing kit support")
                else:
                    lo, hi = interval(domain[group][name])
                    values = value if type(value) is list else [value]
                    if any(not lo <= number(v) <= hi for v in values):
                        gaps.append(f"{group}.{name}: outside kit support")
    required = {"loss_pa", "reattachment_over_H", "exit_reverse_flow"}
    if not required <= set(domain.get("observables", [])):
        gaps.append("missing decision observable")
    return {
        "covered": not gaps,
        "coverage_fraction": 1.0 if not gaps else None,
        "gaps": sorted(set(gaps)),
        "evidence_authority": False,
    }


def geometry_distance_audit(descriptor, catalogue, measurement):
    """Registered normalized descriptors; explicit equivalents belong in catalogue.

    A measured cutoff is still supplied evidence, not an earned qualification.
    Source hashes bind the measurement and complete rights-audited catalogue.
    Resampling/remeshing never changes this physical descriptor.
    """
    if not catalogue or not measurement:
        raise PreparationError("complete catalogue and measured cutoff required")
    cutoff = number(measurement["cutoff"], positive=True)
    for key in ("measurement_sha256", "catalogue_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", measurement[key]):
            raise PreparationError("measurement/catalogue identity required")
    if not descriptor or any(not 0 <= number(v) <= 1 for v in descriptor):
        raise PreparationError("normalized registered descriptor required")
    if any(
        len(d) != len(descriptor) or any(not 0 <= number(v) <= 1 for v in d)
        for d in catalogue
    ):
        raise PreparationError("matched normalized catalogue descriptors required")
    distance = min(math.dist(descriptor, d) for d in catalogue)
    return {"distance": distance, "cutoff": cutoff, "outside": distance > cutoff}


def decision_novelty(challenge, witnesses):
    """Decision-based novelty audit over explicit PUBLIC_DEVELOPMENT witnesses.

    Geometry distance is necessary, never sufficient. No solver or redraw.
    Incomplete anchors/variant truth or measured cutoff keep novelty unresolved.
    """
    if challenge != FAMILY or witnesses.get("scope") != "PUBLIC_DEVELOPMENT":
        raise PreparationError("explicit public non-hidden witnesses required")
    reports = []
    for row in witnesses.get("rows", []):
        if row.get("custody") == "PUBLIC_REFERENCE_ANCHOR":
            reports.append(
                {
                    "id": row["id"],
                    "status": "PUBLIC_ANCHOR_EXCLUDED",
                    "variant_decision_test": "UNRESOLVED_NO_VARIANT_TRUTH",
                    "scored": False,
                }
            )
            continue
        try:
            geometry = geometry_distance_audit(
                row.get("descriptor"),
                row.get("catalogue_descriptors"),
                row.get("threshold_measurement"),
            )
        except (PreparationError, KeyError, TypeError):
            reports.append({"id": row["id"], "status": "UNRESOLVED_GEOMETRY_RULE"})
            continue
        if not geometry["outside"]:
            reports.append({"id": row["id"], "status": "GEOMETRY_COPY_EXCLUDED"})
            continue
        task, reference, shortcut = (
            row.get("task"),
            row.get("reference"),
            row.get("shortcut_values"),
        )
        if not task or reference is None or shortcut is None:
            reports.append(
                {"id": row["id"], "status": "UNRESOLVED_MISSING_PUBLIC_DECISIONS"}
            )
            continue
        tasks._verify_task_digest(task)
        truth = tasks.assess(
            task,
            {(r["candidate"], r["condition"]): r["values"] for r in reference},
            reference=True,
        )
        cached = tasks.assess(
            task, {(r["candidate"], r["condition"]): r["values"] for r in shortcut}
        )
        actual, predicted = tasks.select(task, truth), tasks.select(task, cached)
        if any(r["feasible"] is None for r in truth.values()):
            status = "UNRESOLVED_REFERENCE"
        elif (
            predicted is None
            and tasks.reference_state(task, cached) == "NONE_FEASIBLE"
            and actual is None
        ):
            status = "SHORTCUT_STILL_WORKS_NOT_NOVEL"
        elif predicted is None:
            status = "UNRESOLVED_SHORTCUT_ABSTENTION"
        elif truth[predicted]["feasible"] is True and actual is not None:
            tie = row.get("value_equivalence")
            if tie is None:
                status = "UNRESOLVED_MEASURED_VALUE_EQUIVALENCE"
            else:
                regret = abs(truth[predicted]["objective"] - truth[actual]["objective"])
                status = (
                    "SHORTCUT_STILL_WORKS_NOT_NOVEL"
                    if regret <= number(tie, positive=True)
                    else "DECISION_NOVELTY_PASSES_PUBLIC_ONLY"
                )
        else:
            status = "DECISION_NOVELTY_PASSES_PUBLIC_ONLY"
        reports.append(
            {
                "id": row["id"],
                "status": status,
                "reference_pick": actual,
                "shortcut_pick": predicted,
                "geometry": geometry,
                "scored": False,
            }
        )
    return {
        "family": challenge,
        "rows": reports,
        "status": "DESCRIPTIVE" if reports else "UNRESOLVED_NO_VARIANT_TRUTH",
        "hidden_bank_authorized": False,
    }


def observed_orders(rows, band):
    """Numerical evidence checker; band must be explicitly registered externally."""
    lo, hi = interval(band)
    if len(rows) < 3:
        raise PreparationError("three or more independently solved rungs required")
    orders = []
    for left, right in itertools.pairwise(rows):
        h0, h1 = number(left["h"], positive=True), number(right["h"], positive=True)
        e0, e1 = number(left["error_l2"], positive=True), number(
            right["error_l2"], positive=True
        )
        if h0 <= h1:
            raise PreparationError("strict refinement required")
        orders.append(math.log(e0 / e1) / math.log(h0 / h1))
    return {
        "orders": orders,
        "inside_supplied_band": all(lo <= p <= hi for p in orders),
        "reference_adequacy": "NOT_INFERRED",
    }


def manufactured_sources():
    """Symbolic laminar compressible NS fields matching SU2's pinned built-in.

    This verifies derivation, not execution or the SST turbulence equations.
    mu, R, gamma and Pr remain explicit positive symbolic inputs.
    """
    import sympy as s

    x, y = s.symbols("x y", real=True)
    mu, gas, gamma, pr = s.symbols("mu R gamma Pr", positive=True)
    pi = s.pi
    rho = (
        1
        + s.Rational(1, 10) * s.sin(s.Rational(3, 4) * pi * x)
        + s.Rational(3, 20) * s.cos(pi * y)
        + s.Rational(2, 25) * s.cos(s.Rational(5, 4) * pi * x * y)
    )
    u = (
        70
        + 4 * s.sin(s.Float("1.6666666667") * pi * x)
        - 12 * s.cos(s.Rational(3, 2) * pi * y)
        + 7 * s.cos(s.Rational(3, 5) * pi * x * y)
    )
    v = (
        90
        - 20 * s.cos(s.Rational(3, 2) * pi * x)
        + 4 * s.sin(pi * y)
        - 11 * s.cos(s.Rational(9, 10) * pi * x * y)
    )
    p = (
        100000
        - 30000 * s.cos(pi * x)
        + 20000 * s.sin(s.Rational(5, 4) * pi * y)
        - 25000 * s.sin(s.Rational(3, 4) * pi * x * y)
    )
    vel = s.Matrix([u, v])
    grad = vel.jacobian([x, y])
    stress = mu * (grad + grad.T) - s.Rational(2, 3) * mu * s.trace(grad) * s.eye(2)
    energy = p / (gamma - 1) + rho * (u * u + v * v) / 2
    temperature = p / (rho * gas)
    conductivity = mu * gamma * gas / (pr * (gamma - 1))
    momentum = rho * vel * vel.T + p * s.eye(2) - stress
    energy_flux = (
        (energy + p) * vel
        - stress * vel
        - conductivity * s.Matrix([s.diff(temperature, x), s.diff(temperature, y)])
    )
    sources = [
        s.diff(rho * u, x) + s.diff(rho * v, y),
        *[s.diff(momentum[i, 0], x) + s.diff(momentum[i, 1], y) for i in range(2)],
        s.diff(energy_flux[0], x) + s.diff(energy_flux[1], y),
    ]
    return {
        "coordinates": (x, y),
        "parameters": (mu, gas, gamma, pr),
        "primitive": (rho, u, v, p),
        "sources": tuple(sources),
        "boundary": "EXACT_PRIMITIVE_ON_UNIT_QUAD",
        "scope": "LAMINAR_SUBSYSTEM_ONLY",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("actions", "conditions", "novelty"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--seed", type=int, default=0, help="public rehearsal seed only"
    )
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--proposal", choices=("P", "Q"), default="P")
    args = parser.parse_args(argv)
    raw = args.input.read_bytes()
    if len(raw) > 16 * 1024 * 1024:
        raise PreparationError("bounded explicit public file required")
    data = json.loads(raw)
    result = (
        actions(data, seed=args.seed, count=args.count)
        if args.operation == "actions"
        else (
            conditions(data, seed=args.seed, count=args.count, proposal=args.proposal)
            if args.operation == "conditions"
            else decision_novelty(FAMILY, data)
        )
    )
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
