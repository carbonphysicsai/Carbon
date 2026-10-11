"""Public cooling-cell preparation. No solver, filesystem writes or dispatch.

Only the existing axial-map/PG25 interior-cell route is materialized. Frozen
buyer services are inputs, never actions. Expanded maps/materials need a new
reference route rather than an optimistic reuse of this one.
"""

from __future__ import annotations

import math
import random
import re
from copy import deepcopy

from carbon.cold_plate import domain, openfoam
from carbon.design_search import tasks
from carbon.development_comparison import portfolio_baselines

FAMILY = "cooling-cell"
SCHEMA = "carbon.cooling-cell.preparation.v1"
PLANE = "lid-side-TIM2"
OBSERVER = "cooling-case-TIM2-v3"
ACTION = ("channel_width_mm", "fin_width_mm", "channel_depth_mm", "flow_lpm_per_kw")
SERVICE_VALUES = (
    "inlet_c",
    "heat_load_w",
    "hotspot_ratio",
    "hotspot_center_mm",
    "hotspot_width_mm",
)
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")


def seal(body):
    if type(body) is not dict or "digest" in body:
        raise ValueError("unsealed public body required")
    return {**body, "digest": tasks.digest(body)}


def _finite(v):
    return type(v) in (int, float) and math.isfinite(v)


def _hash(v):
    if type(v) is not str or SHA.fullmatch(v) is None:
        raise ValueError("immutable public source identity required")


def validate(raw):
    if type(raw) is not dict or set(raw) != {
        "schema",
        "scope",
        "authority",
        "pins",
        "grammar",
        "services",
        "P",
        "Q",
        "w",
        "digest",
    }:
        raise ValueError("closed cooling preparation registration required")
    if raw["schema"] != SCHEMA or raw["scope"] not in {
        "PUBLIC_DEVELOPMENT",
        "SYNTHETIC_FIXTURE",
    }:
        raise ValueError("explicit public development or fixture registration required")
    if (
        not isinstance(raw["authority"], str)
        or not raw["authority"]
        or raw["digest"]
        != tasks.digest({k: v for k, v in raw.items() if k != "digest"})
    ):
        raise ValueError("authority and unchanged digest required")
    if type(raw["pins"]) is not dict or set(raw["pins"]) != {
        "solver_image",
        "solver_source",
        "materials",
        "observer",
    }:
        raise ValueError("complete immutable solver/material/observer pins required")
    for pin in raw["pins"].values():
        _hash(pin)
    if raw["pins"]["solver_image"] != openfoam.IMAGE.split("@")[1]:
        raise ValueError("only current source-pinned solver deck supported")
    g = raw["grammar"]
    if type(g) is not dict or set(g) != set(ACTION):
        raise ValueError("four interior-cell action coordinates required")
    for key, rule in g.items():
        if (
            type(rule) is not dict
            or set(rule) != {"min", "max", "step"}
            or not all(_finite(v) for v in rule.values())
        ):
            raise ValueError("finite registered lattice required")
        steps = (
            (rule["max"] - rule["min"]) / rule["step"] if rule["step"] > 0 else math.inf
        )
        lo, hi = domain.INPUT_BOUNDS[key]
        if (
            not lo <= rule["min"] <= rule["max"] <= hi
            or rule["step"] <= 0
            or not math.isfinite(steps)
            or steps > 1_000_000
            or not math.isclose(
                (rule["max"] - rule["min"]) / rule["step"],
                round((rule["max"] - rule["min"]) / rule["step"]),
                abs_tol=1e-8,
            )
        ):
            raise ValueError(
                "action outside current deck support or nonintegral lattice"
            )
    services = raw["services"]
    if type(services) is not list or not 1 <= len(services) <= 100:
        raise ValueError("bounded frozen services required")
    seen = set()
    for s in services:
        if type(s) is not dict or set(s) != {
            "id",
            "stratum",
            *SERVICE_VALUES,
            "plane",
            "coolant",
            "lid_id",
            "map_digest",
            "characterization_digest",
            "inlet_source_digest",
            "tim2_m2k_w",
            "map_uncertainty_k",
            "cell_pressure_limit_pa",
            "objective",
        }:
            raise ValueError("complete frozen buyer service required")
        if (
            any(
                type(s[k]) is not str or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", s[k])
                for k in ("id", "stratum", "lid_id")
            )
            or s["id"] in seen
        ):
            raise ValueError("unique public service and lid identities required")
        seen.add(s["id"])
        if s["plane"] != PLANE or s["coolant"] != "PG25":
            raise ValueError("only supported post-spreader axial PG25 route")
        for key in SERVICE_VALUES:
            lo, hi = domain.INPUT_BOUNDS[key]
            if not _finite(s[key]) or not lo <= s[key] <= hi:
                raise ValueError("buyer service outside current material/map support")
        for key in ("map_digest", "characterization_digest", "inlet_source_digest"):
            _hash(s[key])
        for key in ("tim2_m2k_w", "map_uncertainty_k"):
            if not _finite(s[key]) or s[key] < 0:
                raise ValueError("nonnegative registered TIM2/uncertainty required")
        if s["cell_pressure_limit_pa"] is not None and (
            not _finite(s["cell_pressure_limit_pa"]) or s["cell_pressure_limit_pa"] <= 0
        ):
            raise ValueError(
                "cell pressure limit is supplied positive Pa or HUMAN_INPUT"
            )
        if s["objective"] is not None and s["objective"] not in {
            "min_cell_pressure_pa",
            "min_hydraulic_power_w",
        }:
            raise ValueError("supported buyer objective or HUMAN_INPUT required")
        domain.check_inputs({**domain.NOMINAL, **{k: s[k] for k in SERVICE_VALUES}})
    for law in ("P", "Q", "w"):
        weights = raw[law]
        if (
            type(weights) is not dict
            or set(weights) != seen
            or any(not _finite(v) or v < 0 for v in weights.values())
            or not math.isclose(sum(weights.values()), 1, abs_tol=1e-12)
        ):
            raise ValueError("separate registered P/Q/w service masses required")
    if any(raw["Q"][key] <= 0 for key in seen):
        raise ValueError("every frozen service requires diagnostic support")
    return deepcopy(raw)


def actions(registration, *, count, seed):
    r = validate(registration)
    if (
        type(count) is not int
        or not 1 <= count <= 4096
        or type(seed) is not int
        or seed < 0
    ):
        raise ValueError("bounded public action draw required")
    levels = {
        k: 1 + round((v["max"] - v["min"]) / v["step"]) for k, v in r["grammar"].items()
    }
    size = math.prod(levels.values())
    if size > 10**12:
        raise ValueError("registered action lattice too large for this draft tool")
    if count > size:
        raise ValueError("not enough distinct registered actions")
    result = []
    for index in random.Random(seed).sample(range(size), count):
        a = {}
        for key in ACTION:
            rule = r["grammar"][key]
            index, digit = divmod(index, levels[key])
            a[key] = round(rule["min"] + digit * rule["step"], 12)
        result.append(a)
    return result


def case(registration, action, service_id, *, resolution):
    r = validate(registration)
    if type(action) is not dict or set(action) != set(ACTION):
        raise ValueError("complete action required")
    for key, value in action.items():
        rule = r["grammar"][key]
        if (
            not _finite(value)
            or not rule["min"] <= value <= rule["max"]
            or not math.isclose(
                (value - rule["min"]) / rule["step"],
                round((value - rule["min"]) / rule["step"]),
                abs_tol=1e-8,
            )
        ):
            raise ValueError("action not on registered lattice")
    s = next((s for s in r["services"] if s["id"] == service_id), None)
    if s is None or not _finite(resolution) or not 0.5 <= resolution <= 16:
        raise ValueError("registered service and bounded refinement rung required")
    inputs = domain.check_inputs({**action, **{k: s[k] for k in SERVICE_VALUES}})
    return {
        "scope": r["scope"],
        "registration_digest": r["digest"],
        "pins": r["pins"],
        "action": action,
        "condition": s,
        "rung": {"resolution": resolution},
        "inputs": inputs,
    }


def physical_key(c, *, include_rung=True):
    # Names, strata, limits and provenance labels cannot renew physical truth.
    body = {
        "inputs": c["inputs"],
        "tim2_m2k_w": c["condition"]["tim2_m2k_w"],
        "coolant": c["condition"]["coolant"],
    }
    if include_rung:
        body["rung"] = c["rung"]
        body["pins"] = c["pins"]
    return tasks.digest(body)


def conditions(registration, *, count, seed, law):
    r = validate(registration)
    if (
        law not in ("P", "Q")
        or type(count) is not int
        or not 1 <= count <= 4096
        or type(seed) is not int
        or seed < 0
    ):
        raise ValueError("bounded public P or diagnostic Q draw required")
    by_id = {s["id"]: s for s in r["services"]}
    ids = list(by_id)
    chosen = random.Random(seed).choices(ids, weights=[r[law][i] for i in ids], k=count)
    return [
        {
            "service": deepcopy(by_id[i]),
            "law": law,
            "p": r["P"][i],
            "q": r["Q"][i],
            "w": r["w"][i],
        }
        for i in chosen
    ]


def panel(registration, registered_actions, *, rungs, retained, scheduled):
    """Explicit inventories required; absence is not proof of no reuse."""
    r = validate(registration)
    if (
        not registered_actions
        or len(registered_actions) > 4096
        or not rungs
        or len(rungs) > 8
        or len(registered_actions) * len(r["services"]) * len(rungs) > 10000
    ):
        raise ValueError("bounded panel actions and rungs required")
    if type(retained) is not list or type(scheduled) is not list:
        raise ValueError("explicit completed and scheduled public inventories required")
    known = {}
    for state, rows in (("COMPLETED", retained), ("SCHEDULED", scheduled)):
        for row in rows:
            if (
                row.get("scope") != r["scope"]
                or row.get("registration_digest") != r["digest"]
            ):
                raise ValueError("matched public/fixture inventory required")
            if row != case(
                r,
                row["action"],
                row["condition"]["id"],
                resolution=row["rung"]["resolution"],
            ):
                raise ValueError(
                    "retained/scheduled tuple differs from registered physics"
                )
            known[physical_key(row)] = state
    out, seen = [], set()
    for a in registered_actions:
        for s in r["services"]:
            for rung in rungs:
                c = case(r, a, s["id"], resolution=rung)
                key = physical_key(c)
                if key in seen:
                    continue
                seen.add(key)
                out.append({"case": c, "reuse": known.get(key, "NEW")})
    return seal(
        {
            "schema": "carbon.cooling-cell.panel-proposal.v1",
            "scope": r["scope"],
            "registration_digest": r["digest"],
            "status": "PROPOSED_NOT_REGISTERED",
            "cases": out,
            "dispatchable": False,
        }
    )


def deck(registration, action, service_id, *, resolution):
    """Render the existing supported solver inputs in memory only."""
    c = case(registration, action, service_id, resolution=resolution)
    texts, record = openfoam.files(c["inputs"], resolution=resolution)
    return {
        "files": texts,
        "record": record,
        "physical_case": c,
        "observer": PLANE,
        "image": openfoam.IMAGE,
        "status": "UNVERIFIED_DECK_DRAFT",
        "dispatchable": False,
    }


def observe(
    registration,
    action,
    service_id,
    faces,
    *,
    numerical_uncertainty_k,
    pressure_drop_pa,
    fluid_min_c,
    fluid_max_c,
):
    """Case-plane maximum of CO-LOCATED plate temperature + TIM2*q."""
    c = case(registration, action, service_id, resolution=2)
    s = c["condition"]
    if (
        not faces
        or len(faces) > 1_000_000
        or not _finite(numerical_uncertainty_k)
        or numerical_uncertainty_k < 0
    ):
        raise ValueError("retained faces and numerical uncertainty required")
    if (
        not all(_finite(v) for v in (pressure_drop_pa, fluid_min_c, fluid_max_c))
        or pressure_drop_pa < 0
        or fluid_min_c > fluid_max_c
    ):
        raise ValueError("retained pressure and fluid extrema required")
    if (
        not domain.PG25_VALID_C[0]
        <= fluid_min_c
        <= fluid_max_c
        <= domain.PG25_VALID_C[1]
    ):
        return {
            "status": "REFERENCE_INVALID",
            "reason": "PG25 applicability",
            "candidate_failure": False,
        }
    peaks, heat, area, coordinates = [], 0.0, 0.0, set()
    for face in faces:
        if (
            type(face) is not dict
            or set(face) != {"x_m", "y_m", "area_m2", "plate_c", "q_w_m2"}
            or not all(_finite(v) for v in face.values())
            or face["area_m2"] <= 0
        ):
            raise ValueError("finite co-located face coordinates and fields required")
        xy = (face["x_m"], face["y_m"])
        if (
            xy in coordinates
            or not 0 <= face["x_m"] <= 0.03
            or not 0
            <= face["y_m"]
            <= (action["channel_width_mm"] + action["fin_width_mm"]) * 0.0005
        ):
            raise ValueError("unique interior-cell face coordinates required")
        coordinates.add(xy)
        expected = domain.heat_flux(c["inputs"], face["x_m"] * 1000)
        if not math.isclose(face["q_w_m2"], expected, rel_tol=1e-8, abs_tol=1e-6):
            raise ValueError("retained face flux differs from frozen post-spreader map")
        peaks.append(face["plate_c"] + s["tim2_m2k_w"] * face["q_w_m2"])
        heat += face["area_m2"] * face["q_w_m2"]
        area += face["area_m2"]
    expected_area = (
        (action["channel_width_mm"] + action["fin_width_mm"]) * 0.0005 * 0.03
    )
    if not math.isclose(area, expected_area, rel_tol=1e-8, abs_tol=1e-15):
        raise ValueError("whole half-cell heated-face coverage required")
    peak = max(peaks)
    uncertainty = s["map_uncertainty_k"] + numerical_uncertainty_k
    state = (
        "FEASIBLE"
        if peak + uncertainty <= 85
        else "INFEASIBLE" if peak - uncertainty > 85 else "UNRESOLVED"
    )
    d = domain.derived(c["inputs"])
    width, depth = action["channel_width_mm"] * 1e-3, action["channel_depth_mm"] * 1e-3
    dh = 2 * width * depth / (width + depth)
    reynolds = (
        domain.pg25("rho", s["inlet_c"] + domain.K0)
        * d["inlet_velocity_m_s"]
        * dh
        / domain.pg25("mu", s["inlet_c"] + domain.K0)
    )
    if reynolds > domain.RE_LAMINAR_MAX:
        return {
            "status": "REFERENCE_INVALID",
            "reason": "laminar applicability",
            "reynolds": reynolds,
            "candidate_failure": False,
        }
    local_flow = d["flow_m3_s"] / d["channels"] / 2
    return {
        "status": "OBSERVED_NOT_QUALIFIED",
        "plane": PLANE,
        "peak_case_c": peak,
        "peak_coordinate_m": [faces[peaks.index(peak)][k] for k in ("x_m", "y_m")],
        "thermal_verdict": state,
        "thermal_interval_c": [peak - uncertainty, peak + uncertainty],
        "cell_pressure_drop_pa": pressure_drop_pa,
        "half_cell_flow_m3_s": local_flow,
        "half_cell_hydraulic_power_w": pressure_drop_pa * local_flow,
        "sampled_heat_w": heat,
        "analytic_half_cell_heat_w": d["heat_flux_w_m2"] * expected_area,
        "pressure_verdict": (
            "HUMAN_INPUT"
            if s["cell_pressure_limit_pa"] is None
            else (
                "FEASIBLE"
                if pressure_drop_pa <= s["cell_pressure_limit_pa"]
                else "INFEASIBLE"
            )
        ),
        "best_pick": (
            "UNRESOLVED_BUYER_OBJECTIVE"
            if s["objective"] is None
            else "REQUIRES_COMPLETE_PANEL"
        ),
        "candidate_failure": False,
    }


def train_plan(registration, candidates, panel_cases):
    r = validate(registration)
    blocked = {physical_key(c, include_rung=False) for c in panel_cases}
    result, seen = [], set()
    for c in candidates:
        validated = case(
            r, c["action"], c["condition"]["id"], resolution=c["rung"]["resolution"]
        )
        if c != validated:
            raise ValueError("TRAIN candidate differs from registered physical tuple")
        key = physical_key(c, include_rung=False)
        if key not in blocked and key not in seen:
            result.append(c)
            seen.add(key)
    return {
        "scope": r["scope"],
        "status": "PROPOSED_NOT_REGISTERED",
        "cases": result,
        "dispatchable": False,
    }


def kit_domain(registration, kit, panel_cases):
    r = validate(registration)
    required = {
        "peak_case_c",
        "cell_pressure_drop_pa",
        "half_cell_flow_m3_s",
        "half_cell_hydraulic_power_w",
    }
    if (
        kit.get("registration_digest") != r["digest"]
        or kit.get("plane") != PLANE
        or not required <= set(kit.get("observables", []))
    ):
        return {
            "covered": False,
            "basis": "registration/plane/observable coverage missing",
        }
    for c in panel_cases:
        if (
            case(
                r, c["action"], c["condition"]["id"], resolution=c["rung"]["resolution"]
            )
            != c
        ):
            raise ValueError("unregistered panel tuple")
        if c["condition"]["id"] not in kit.get("services", []):
            return {"covered": False, "basis": "service map not covered"}
        for key, v in c["action"].items():
            bounds = kit.get("action_bounds", {}).get(key)
            if (
                type(bounds) is not list
                or len(bounds) != 2
                or not all(_finite(x) for x in bounds)
                or not bounds[0] <= v <= bounds[1]
            ):
                return {"covered": False, "basis": "action outside kit"}
    return {
        "covered": bool(panel_cases),
        "basis": f"{len(panel_cases)} explicit tuples compared; proposal only",
    }


def compare(registration, export, material):
    """Reuse strongest same-context held-geometry response maps and cost/ranks."""
    if export.get("family") != FAMILY:
        raise ValueError("cooling-cell export required")
    r = validate(registration)
    observer = OBSERVER + ":" + r["digest"]
    if material.get("observer_versions") != [observer] or material.get(
        "settings", {}
    ).get("coordinate_fields") != list(ACTION):
        raise ValueError(
            "matched case-plane observer and physical geometry/flow coordinates required"
        )
    contexts = {tasks.digest(s)[7:] for s in r["services"]}
    if any(
        row.get("context_sha256") not in contexts for row in material.get("rows", [])
    ):
        raise ValueError("response map crosses frozen buyer service identities")
    return portfolio_baselines.measure(export, material=material)


def manufactured_channel(
    x,
    y,
    *,
    height_m,
    gradient_pa_m,
    mu_pa_s,
    rho_cp,
    k_w_mk,
    t0_k,
    axial_k_m,
    amplitude_k,
):
    """Independent constant-property analytic/MMS rung, not PG25 adequacy.

    -mu*u'' = G; div(u)=0. rho*cp*u*T_x - k*laplacian(T)=S.
    Exact traces supply Dirichlet data; pressure is p0-G*x. Source W/m3.
    A separate fvOptions/source implementation is still required and verified.
    """
    if (
        not all(
            _finite(v)
            for v in (
                x,
                y,
                height_m,
                gradient_pa_m,
                mu_pa_s,
                rho_cp,
                k_w_mk,
                t0_k,
                axial_k_m,
                amplitude_k,
            )
        )
        or height_m <= 0
        or mu_pa_s <= 0
        or rho_cp <= 0
        or k_w_mk <= 0
        or not 0 <= y <= height_m
    ):
        raise ValueError("finite supported manufactured coordinates/materials required")
    wave = math.sin(math.pi * y / height_m)
    velocity = gradient_pa_m * y * (height_m - y) / (2 * mu_pa_s)
    return {
        "u_m_s": velocity,
        "pressure_difference_pa": -gradient_pa_m * x,
        "temperature_k": t0_k + axial_k_m * x + amplitude_k * wave,
        "energy_source_w_m3": rho_cp * velocity * axial_k_m
        + k_w_mk * amplitude_k * (math.pi / height_m) ** 2 * wave,
    }
