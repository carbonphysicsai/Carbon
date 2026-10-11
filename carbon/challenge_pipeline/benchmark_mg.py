"""Full-vector 3D metagrating PUBLIC DEVELOPMENT preparation, never dispatch.

Source pins and generated syntax are not an installed or adequate reference.
All physical laws/limits need an explicit digest-bound registration; missing
measured values remain closed. No protected-data or solver imports at import.
"""

from __future__ import annotations

import argparse
import cmath
import itertools
import json
import math
import random
import re
from pathlib import Path

from carbon.design_search import tasks

FAMILY = "metagrating-3d"
MEEP_SOURCE = "b08d226ba311a04e59c984e97f3e88dd82bc56d1"
S4_SOURCE = "7fd00a231610bff51f5c7de5f723e3956eab7453"
Q = {"nominal": 0.4, "corners": 0.2, "frontier": 0.3, "transition": 0.1}
REQUIREMENTS = {"efficiency_min", "reflection_max", "unwanted_max"}


class PreparationError(ValueError):
    """Invalid/incomplete preparation, not candidate scientific failure."""


def number(v, *, positive=False):
    if type(v) not in (int, float) or not math.isfinite(v) or (positive and v <= 0):
        raise PreparationError("explicit finite physical number required")
    return float(v)


def interval(v):
    if type(v) is not list or len(v) != 2:
        raise PreparationError("registered supported interval required")
    lo, hi = map(number, v)
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
        raise PreparationError("digest-bound explicit public/fixture MG law required")
    return data


def binary_mask(mask):
    if (
        type(mask) is not list
        or not 2 <= len(mask) <= 256
        or type(mask[0]) is not list
        or not 2 <= len(mask[0]) <= 256
        or any(len(row) != len(mask[0]) for row in mask)
        or any(type(v) is not int or v not in (0, 1) for row in mask for v in row)
    ):
        raise PreparationError("bounded explicit two-direction binary mask required")
    return mask


def _runs_periodic(row):
    if len(set(row)) == 1:
        return [len(row)]
    boundary = next(i for i in range(len(row)) if row[i] != row[i - 1])
    ordered = row[boundary:] + row[:boundary]
    return [len(list(g)) for _, g in itertools.groupby(ordered)]


def feature_check(mask, *, periods_nm, minimum_feature_nm):
    """Conservative orthogonal run-width rule, not fabrication qualification.

    Both phases and periodic boundary runs are checked. Euclidean corner,
    curvature and etch-process constraints need a separately registered rule.
    """
    binary_mask(mask)
    px, py = (number(v, positive=True) for v in periods_nm)
    minimum = number(minimum_feature_nm, positive=True)
    widths = [min(_runs_periodic(list(row))) * py / len(mask[0]) for row in mask] + [
        min(_runs_periodic(list(col))) * px / len(mask) for col in zip(*mask)
    ]
    return {
        "minimum_run_nm": min(widths),
        "passes_registered_run_rule": min(widths) >= minimum,
    }


def actions(data, *, seed, count, periods_nm):
    """Registered binary tiled grammar, finite z; does not narrow fields to 2D.

    A tile grammar changes action freedom and must itself be registered. Source
    masks are not generated or reused as novel actions; novelty is a later check.
    """
    registration(data)
    if type(count) is not int or not 1 <= count <= 1000:
        raise PreparationError("bounded action count required")
    g = data["grammar"]
    nx, ny, tile = g["nx"], g["ny"], g["tile_cells"]
    if any(type(v) is not int or v < 2 or v > 128 for v in (nx, ny)):
        raise PreparationError("explicit bounded mask DOFs required")
    if type(tile) is not int or tile < 1 or nx % tile or ny % tile:
        raise PreparationError("registered tile precision must divide both axes")
    if type(g["reflection_y"]) is not bool:
        raise PreparationError("registered reflection convention required")
    if g["reflection_y"] and ny % 2:
        raise PreparationError(
            "even canonical y grid required for this reflection grammar"
        )
    lo, hi = interval(g["thickness_nm"])
    step = number(g["thickness_step_nm"], positive=True)
    if lo <= 0 or not math.isclose((hi - lo) / step, round((hi - lo) / step)):
        raise PreparationError("positive lattice-aligned thickness envelope required")
    minimum = number(g["minimum_feature_nm"], positive=True)
    rng, seen, result = random.Random(seed), set(), []
    attempted = 0
    while len(result) < count and attempted < count * 200:
        attempted += 1
        coarse = [
            [rng.randrange(2) for _ in range(ny // tile)] for _ in range(nx // tile)
        ]
        mask = [[coarse[i // tile][j // tile] for j in range(ny)] for i in range(nx)]
        if g["reflection_y"]:
            mask = [row[: ny // 2] + list(reversed(row[: ny // 2])) for row in mask]
        if (
            len({tuple(row) for row in mask}) < 2
            or len({tuple(col) for col in zip(*mask)}) < 2
        ):
            continue  # no constant/stripe-only family in this grammar
        if not feature_check(mask, periods_nm=periods_nm, minimum_feature_nm=minimum)[
            "passes_registered_run_rule"
        ]:
            continue
        action = {
            "mask": mask,
            "thickness_nm": lo + step * rng.randint(0, round((hi - lo) / step)),
        }
        key = tasks.digest(action)
        if key not in seen:
            seen.add(key)
            result.append(action)
    if len(result) != count:
        raise PreparationError(
            "registered mask proposal exhausted; no relaxation/redraw of settled questions"
        )
    return {
        "scope": data["scope"],
        "dispatchable": False,
        "actions": result,
        "attempts": attempted,
        "rejected_proposals": attempted - count,
        "novelty": "UNRESOLVED_PENDING_CATALOGUE_AND_PUBLIC_DECISION_TEST",
    }


def briefs(data, *, seed, count, proposal="P"):
    """One fixed-period hardware brief. Only SOURCE-supported monochromatic model.

    P includes service/hardware briefs and continuous buyer requirements. Q
    enriches public frontier/transition draws, never score weighting or redraws.
    Half of transition (5% total) is preregistered library-failure diagnostics.
    """
    registration(data)
    if type(count) is not int or not 1 <= count <= 10000 or proposal not in ("P", "Q"):
        raise PreparationError("bounded P/Q brief draw required")
    law = data["requirement_law"]
    if not re.fullmatch(r"[0-9a-f]{64}", law["public_calibration_sha256"]):
        raise PreparationError("public calibration identity required")
    if set(law["intervals"]) != REQUIREMENTS:
        raise PreparationError("all buyer requirement intervals required")
    bounds = {k: interval(v) for k, v in law["intervals"].items()}
    if any(lo < 0 or hi > 1 for lo, hi in bounds.values()):
        raise PreparationError("normalized power requirements must lie in [0,1]")
    angle = interval(data["deflection_angle_deg"])
    if not 0 < angle[0] <= angle[1] < 90:
        raise PreparationError("supported forward deflection range required")
    if (
        data["wavelength_nm"] != 1050
        or data["n_silicon"] != 3.45
        or data["n_substrate"] != 1.45
    ):
        raise PreparationError(
            "source model is fixed-wavelength ideal lossless, not arbitrary dispersion"
        )
    rng = random.Random(seed)
    labels = ["population"] * count
    if proposal == "Q":
        if count % 20:
            raise PreparationError(
                "40/20/30/10 plus 5% library-failure needs a multiple of twenty"
            )
        labels = [
            label for label, mass in Q.items() for _ in range(round(count * mass))
        ]
        rng.shuffle(labels)
    rows, transitions = [], 0
    for label in labels:
        if label in ("population", "nominal", "corners"):
            draw = (
                (lambda bound: rng.choice(bound))
                if label == "corners"
                else (lambda bound: rng.uniform(*bound))
            )
            a, req = draw(angle), {k: draw(v) for k, v in bounds.items()}
            library_failure = False
        else:
            pool_name = label
            if label == "transition":
                pool_name = "library_failure" if transitions % 2 == 0 else "transition"
                transitions += 1
            pool = data.get("diagnostic_pools", {}).get(pool_name)
            if not pool:
                raise PreparationError("registered public diagnostic pool missing")
            choice = rng.choice(pool)
            a, req = choice["angle_deg"], dict(choice["requirements"])
            library_failure = pool_name == "library_failure"
        if (
            not angle[0] <= number(a) <= angle[1]
            or set(req) != REQUIREMENTS
            or any(
                not bounds[k][0] <= number(v) <= bounds[k][1] for k, v in req.items()
            )
        ):
            raise PreparationError("diagnostic draw outside P support")
        rows.append(
            {
                "hardware": {
                    "periods_nm": [1050 / math.sin(math.radians(a)), 525],
                    "deflection_deg": a,
                },
                "conditions": [
                    {
                        "wavelength_nm": 1050,
                        "incident_angle_deg": 0,
                        "polarization": "Ex",
                        "n_in": 1.45,
                        "n_out": 1.0,
                    }
                ],
                "requirements": req,
                "draw_role": label,
                "library_failure_diagnostic": library_failure,
            }
        )
    return {
        "family": FAMILY,
        "scope": data["scope"],
        "dispatchable": False,
        "population": "REPRESENTATIVE",
        "proposal": proposal,
        "Q": Q,
        "w": "BUYER_FREQUENCY_UNDER_P_NOT_Q",
        "exposure_E": 1,
        "independent_unit": "COMPLETE_FIXED_HARDWARE_BRIEF",
        "none_feasible": "RETAIN_NO_REDRAW",
        "briefs": rows,
    }


def calibration_check(strata, *, minimum_useful_improvement, minimum_margin_spread):
    """Prospective public P calibration, never selective exam-question rejection."""
    mui = number(minimum_useful_improvement, positive=True)
    spread = number(minimum_margin_spread, positive=True)
    if not strata:
        raise PreparationError("complete public strata required")
    reports, passing_sets, best_sets, winners, inventory = [], [], [], set(), None
    for name, designs in strata.items():
        current = {d["design"] for d in designs}
        if (
            not designs
            or len(current) != len(designs)
            or (inventory is not None and current != inventory)
        ):
            raise PreparationError(
                "same complete distinct action inventory required in all strata"
            )
        inventory = current
        if any(type(d["feasible"]) is not bool for d in designs):
            return {"status": "UNRESOLVED"}
        passing = {d["design"] for d in designs if d["feasible"]}
        passing_sets.append(passing)
        ranked = sorted(
            (-number(d["efficiency"]), d["design"]) for d in designs if d["feasible"]
        )
        if ranked:
            winners.add(ranked[0][1])
            best = -ranked[0][0]
            best_sets.append(
                {
                    d["design"]
                    for d in designs
                    if d["feasible"] and best - number(d["efficiency"]) <= 0.5 * mui
                }
            )
        else:
            best_sets.append(set())
        margins = [number(d["margin"]) for d in designs]
        near = [d for d in designs if abs(number(d["margin"])) <= 2 * mui]
        rate = len(passing) / len(designs)
        reports.append(
            {
                "stratum": name,
                "pass_rate": rate,
                "near_feasible": sum(d["feasible"] for d in near),
                "near_infeasible": sum(not d["feasible"] for d in near),
                "margin_spread": max(margins) - min(margins),
                "rate_rule": 0.2 <= rate <= 0.8,
            }
        )
    common = sorted(set.intersection(*passing_sets))
    common_best = sorted(set.intersection(*best_sets))
    passed = (
        common
        and not common_best
        and len(winners) > 1
        and all(
            r["rate_rule"]
            and r["near_feasible"] >= 5
            and r["near_infeasible"] >= 5
            and r["margin_spread"] >= spread
            for r in reports
        )
    )
    return {
        "status": "CALIBRATION_PASSES" if passed else "CALIBRATION_FAILS",
        "strata": reports,
        "common_feasible": common,
        "distinct_winners": sorted(winners),
        "common_value_equivalent_pick": common_best,
        "dispatchable": False,
    }


def propagating_orders(*, periods_nm, wavelength_nm, index):
    """Normal incidence isotropic half-space; grazing is unresolved, not omitted."""
    px, py = (number(v, positive=True) for v in periods_nm)
    k = number(index, positive=True) / number(wavelength_nm, positive=True)
    orders = []
    if max(k * px, k * py) > 100:
        raise PreparationError("order enumeration outside bounded source family")
    for m in range(-math.ceil(k * px), math.ceil(k * px) + 1):
        for n in range(-math.ceil(k * py), math.ceil(k * py) + 1):
            kz2 = k * k - (m / px) ** 2 - (n / py) ** 2
            if abs(kz2) <= 8 * math.ulp(k * k):
                raise PreparationError(
                    "grazing/Wood-anomaly order needs refined unresolved policy"
                )
            if kz2 > 0:
                orders.append([m, n])
    return orders


def observe(
    rows, *, periods_nm, wavelength_nm, n_in, n_out, desired=(1, 0), flux_totals=None
):
    """Normalized outgoing power, complete R/T orders and orthogonal polarization.

    Missing channels are reference failures, not zeros. No clipping negative
    powers, renormalization or automatic adopted conservation tolerance.
    """
    expected = {
        (side, *o)
        for side, index in (("R", n_in), ("T", n_out))
        for o in propagating_orders(
            periods_nm=periods_nm, wavelength_nm=wavelength_nm, index=index
        )
    }
    actual = [(r["side"], *r["order"]) for r in rows]
    if len(set(actual)) != len(actual) or set(actual) != expected:
        raise PreparationError("every propagating R/T order exactly once required")
    sums = {"R": 0.0, "T": 0.0}
    cross, wanted, invalid = 0.0, None, False
    for r in rows:
        co, xp = number(r["co_power"]), number(r["cross_power"])
        invalid |= co < 0 or xp < 0
        sums[r["side"]] += co + xp
        cross += xp
        if r["side"] == "T" and tuple(r["order"]) == tuple(desired):
            wanted = co + xp  # total desired-order power; no invented polarization gate
            wanted_co = co
    if wanted is None:
        raise PreparationError("desired transmitted order is not propagating")
    differences = None
    if flux_totals is not None:
        differences = {s: sums[s] - number(flux_totals[s]) for s in sums}
    return {
        "desired_efficiency": wanted,
        "desired_co_efficiency": wanted_co,
        "desired_efficiency_pp": 100 * wanted,
        "reflection": sums["R"],
        "transmission": sums["T"],
        "unwanted_power": sums["T"] - wanted,
        "reflection_pp": 100 * sums["R"],
        "unwanted_power_pp": 100 * (sums["T"] - wanted),
        "cross_polarization": cross,
        "energy_residual": 1 - sums["R"] - sums["T"],
        "invalid_negative_power": invalid,
        "order_vs_plane_flux": differences,
        "reference_acceptance": "UNRESOLVED_NUMERICAL_BANDS_AND_CONVERGENCE",
    }


def powers_from_fields(e, h, *, periods_nm, wavelength_nm, index, side, incident_power):
    """Fourier projection of outgoing homogeneous-plane fields (S4 witness).

    E/H must already have incident fields subtracted on the reflection plane.
    No 1/2 time-average factor: S4's incident flux uses the same convention.
    Orthogonal polarization basis is defined by k and the y axis, matching
    Meep DiffractedPlanewave; co=s gives Ex at normal incidence.
    """
    import numpy as np

    e, h = np.asarray(e, dtype=complex), np.asarray(h, dtype=complex)
    if (
        e.shape != h.shape
        or e.ndim != 3
        or e.shape[2] != 3
        or not np.isfinite(e).all()
        or not np.isfinite(h).all()
    ):
        raise PreparationError("matched finite complex Nx by Ny by 3 fields required")
    orders = propagating_orders(
        periods_nm=periods_nm, wavelength_nm=wavelength_nm, index=index
    )
    if min(e.shape[:2]) < 2 or any(
        2 * abs(m) >= e.shape[0] or 2 * abs(n) >= e.shape[1] for m, n in orders
    ):
        raise PreparationError(
            "field grid cannot resolve all propagating Fourier orders"
        )
    if side not in ("R", "T"):
        raise PreparationError("outgoing side R or T required")
    normalization = number(incident_power, positive=True)
    ef, hf = (np.fft.fft2(v, axes=(0, 1)) / (e.shape[0] * e.shape[1]) for v in (e, h))
    px, py = periods_nm
    k0 = index / wavelength_nm
    sign, rows = (-1 if side == "R" else 1), []
    for m, n in orders:
        kz = sign * math.sqrt(k0 * k0 - (m / px) ** 2 - (n / py) ** 2)
        khat = np.array([m / px, n / py, kz]) / k0
        s = np.cross(khat, [0, 1, 0])
        s /= np.linalg.norm(s)
        p = np.cross(s, khat)
        ev, hv = ef[m % e.shape[0], n % e.shape[1]], hf[m % e.shape[0], n % e.shape[1]]
        co = (
            sign
            * float(np.cross(np.dot(ev, s) * s, np.conj(np.dot(hv, p) * p))[2].real)
            / normalization
        )
        xp = (
            sign
            * float(np.cross(np.dot(ev, p) * p, np.conj(np.dot(hv, s) * s))[2].real)
            / normalization
        )
        rows.append({"side": side, "order": [m, n], "co_power": co, "cross_power": xp})
    return rows


def slab_truth(*, n_in, n_layer, n_out, thickness_nm, wavelength_nm):
    """Exact normal-incidence coherent lossless Fresnel slab, not patterned truth."""
    a, b, c, d, wavelength = (
        number(v, positive=True)
        for v in (n_in, n_layer, n_out, thickness_nm, wavelength_nm)
    )
    r01, r12 = (a - b) / (a + b), (b - c) / (b + c)
    phase = cmath.exp(2j * math.pi * b * d / wavelength)
    denominator = 1 + r01 * r12 * phase**2
    r = (r01 + r12 * phase**2) / denominator
    t = (2 * a / (a + b)) * (2 * b / (b + c)) * phase / denominator
    return {
        "R": abs(r) ** 2,
        "T": (c / a) * abs(t) ** 2,
        "cross": 0.0,
        "scope": "ANALYTIC_PLANAR_SLAB_ONLY",
    }


def observed_orders(rows, band):
    lo, hi = interval(band)
    if len(rows) < 3:
        raise PreparationError("three or more independently solved rungs required")
    values = []
    for a, b in itertools.pairwise(rows):
        h0, h1 = number(a["h"], positive=True), number(b["h"], positive=True)
        e0, e1 = number(a["error"], positive=True), number(b["error"], positive=True)
        if h0 <= h1:
            raise PreparationError("strict refinement required")
        values.append(math.log(e0 / e1) / math.log(h0 / h1))
    return {
        "orders": values,
        "inside_supplied_band": all(lo <= v <= hi for v in values),
        "reference_adequacy": "NOT_INFERRED",
    }


def train_plan(challenge, cases, panel, *, count, allow_y_reflection):
    """Disjoint physical masks, not only different JSON labels or origins.

    Source-supported normal incidence admits periodic translations. A valid
    y-reflection convention must be registered explicitly; x reflection is
    never admitted because it changes the desired order. Canonical-grid
    mismatch is unresolved, not a way to publish resampled panel copies.
    """
    if (
        challenge != FAMILY
        or type(count) is not int
        or not 1 <= count <= 10000
        or type(allow_y_reflection) is not bool
        or type(cases) is not list
        or type(panel) is not list
        or len(cases) > 10000
        or len(panel) > 10000
    ):
        raise PreparationError("explicit MG public TRAIN count required")
    grids = {}

    def physical(row):
        if row.get("scope") not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE"):
            raise PreparationError("explicit public TRAIN/panel custody required")
        a, h, c = row["action"], row["hardware"], row["condition"]
        if set(a) != {"mask", "thickness_nm"} or set(c) != {"wavelength_nm"}:
            raise PreparationError(
                "closed physical action and supported service point required"
            )
        if len(h["periods_nm"]) != 2 or h["wavelength_nm"] != c["wavelength_nm"]:
            raise PreparationError(
                "matched two-period hardware and service wavelength required"
            )
        mask = binary_mask(a["mask"])
        group = tasks.digest(
            {
                "thickness_nm": number(a["thickness_nm"], positive=True),
                "periods_nm": [number(v, positive=True) for v in h["periods_nm"]],
                "n_in": number(h["n_in"], positive=True),
                "n_out": number(h["n_out"], positive=True),
                "n_layer": number(h.get("n_layer", 3.45), positive=True),
                "wavelength_nm": number(c["wavelength_nm"], positive=True),
            }
        )
        shape = (len(mask), len(mask[0]))
        if grids.setdefault(group, shape) != shape:
            raise PreparationError(
                "canonical physical mask mapping required before resampling"
            )
        return (group, sum(sum(r) for r in mask)), mask

    forbidden, seen, result = {}, {}, []
    for row in panel:
        key, mask = physical(row)
        forbidden.setdefault(key, []).append(mask)
    for row in cases:
        key, mask = physical(row)
        prior = forbidden.get(key, []) + seen.get(key, [])
        if (
            not prior
            or mask_distance(mask, prior, allow_y_reflection=allow_y_reflection) > 0
        ):
            seen.setdefault(key, []).append(mask)
            result.append(dict(row))  # Synthetic fixtures never become public evidence.
        if len(result) == count:
            break
    if len(result) != count:
        raise PreparationError("insufficient disjoint public TRAIN tuples")
    return {
        "family": challenge,
        "status": "PLAN_NOT_TRAINED",
        "dispatchable": False,
        "scope": (
            "SYNTHETIC_FIXTURE"
            if any(r["scope"] == "SYNTHETIC_FIXTURE" for r in result)
            else "PUBLIC_DEVELOPMENT"
        ),
        "disjointness_basis": "MATCHED_HARDWARE_CONDITION_TRANSLATION_AND_REGISTERED_Y_REFLECTION",
        "allow_y_reflection": allow_y_reflection,
        "rows": result,
    }


def domain_coverage(challenge, cases, domain):
    if challenge != FAMILY:
        raise PreparationError("explicit MG Challenge required")
    gaps = []
    for row in cases:
        for key, value in (
            ("thickness_nm", row["action"]["thickness_nm"]),
            ("Px_nm", row["hardware"]["periods_nm"][0]),
            ("Py_nm", row["hardware"]["periods_nm"][1]),
            ("wavelength_nm", row["condition"]["wavelength_nm"]),
        ):
            if key not in domain.get("support", {}):
                gaps.append(key + ": missing kit range")
            else:
                lo, hi = interval(domain["support"][key])
                if not lo <= number(value) <= hi:
                    gaps.append(key + ": outside kit support")
        if row.get("grammar_digest") != domain.get("grammar_digest") or not row.get(
            "grammar_digest"
        ):
            gaps.append("mask grammar/feature domain missing or mismatched")
    required = {
        "desired_efficiency",
        "reflection",
        "unwanted_power",
        "cross_polarization",
        "energy_residual",
        "all_order_powers",
    }
    if not required <= set(domain.get("observables", [])):
        gaps.append("missing decision/order/conservation observable")
    return {
        "covered": bool(cases) and not gaps,
        "gaps": sorted(set(gaps)),
        "evidence_authority": False,
    }


def mask_distance(mask, catalogue, *, allow_y_reflection):
    """Periodic translations and explicitly valid y reflection only, never x mirror.

    Catalogue is the registered canonical physical grid. A resampled copy must
    canonicalize back to this grid before comparison; shape mismatch is a hold.
    """
    binary_mask(mask)
    import numpy as np

    if type(allow_y_reflection) is not bool:
        raise PreparationError("registered valid symmetry Boolean required")
    nx, ny = len(mask), len(mask[0])
    if not catalogue:
        raise PreparationError("complete rights-audited canonical catalogue required")
    distances = []
    for other in catalogue:
        binary_mask(other)
        if len(other) != nx or len(other[0]) != ny:
            raise PreparationError(
                "canonical material mapping missing; resampling is not novelty"
            )
        variants = [other]
        if allow_y_reflection:
            variants.append([list(reversed(r)) for r in other])
        for variant in variants:
            # Cyclic binary cross-correlation: exact integer overlaps rounded
            # after FFT. Avoid quadratic translation-by-pixel enumeration.
            overlaps = np.rint(
                np.fft.ifft2(np.fft.fft2(mask) * np.conj(np.fft.fft2(variant))).real
            )
            distances.append(
                float((np.sum(mask) + np.sum(variant) - 2 * overlaps.max()) / (nx * ny))
            )
    return min(distances)


def decision_novelty(challenge, witnesses):
    if challenge != FAMILY or witnesses.get("scope") != "PUBLIC_DEVELOPMENT":
        raise PreparationError("explicit public non-hidden MG witnesses required")
    result = []
    for row in witnesses.get("rows", []):
        if row.get("custody") == "PUBLIC_REFERENCE_ANCHOR":
            result.append(
                {
                    "id": row["id"],
                    "status": "PUBLIC_ANCHOR_EXCLUDED",
                    "variant_decision_test": "UNRESOLVED_NO_VARIANT_TRUTH",
                    "scored": False,
                }
            )
            continue
        measured = row.get("threshold_measurement")
        if not measured or any(
            not re.fullmatch(r"[0-9a-f]{64}", measured.get(k, ""))
            for k in ("measurement_sha256", "catalogue_sha256")
        ):
            result.append({"id": row["id"], "status": "UNRESOLVED_MEASURED_MASK_RULE"})
            continue
        distance = mask_distance(
            row["mask"],
            row["catalogue_masks"],
            allow_y_reflection=row["allow_y_reflection"],
        )
        if distance <= number(measured["cutoff"], positive=True):
            result.append(
                {
                    "id": row["id"],
                    "status": "MASK_COPY_EXCLUDED",
                    "mask_distance": distance,
                }
            )
            continue
        task, refs, cache = (
            row.get("task"),
            row.get("reference"),
            row.get("shortcut_values"),
        )
        if (
            not task
            or refs is None
            or cache is None
            or row.get("value_equivalence") is None
        ):
            result.append(
                {"id": row["id"], "status": "UNRESOLVED_MISSING_PUBLIC_DECISIONS"}
            )
            continue
        tasks._verify_task_digest(task)
        truth = tasks.assess(
            task,
            {(r["candidate"], r["condition"]): r["values"] for r in refs},
            reference=True,
        )
        shortcut = tasks.assess(
            task, {(r["candidate"], r["condition"]): r["values"] for r in cache}
        )
        actual, predicted = tasks.select(task, truth), tasks.select(task, shortcut)
        regret = None
        if any(r["feasible"] is None for r in truth.values()):
            status = "UNRESOLVED_REFERENCE"
        elif (
            actual is None and tasks.reference_state(task, shortcut) == "NONE_FEASIBLE"
        ):
            status = "SHORTCUT_STILL_WORKS_NOT_NOVEL"
        elif predicted is None:
            status = "UNRESOLVED_SHORTCUT_ABSTENTION"
        elif actual is not None and truth[predicted]["feasible"] is True:
            regret = abs(truth[predicted]["objective"] - truth[actual]["objective"])
            status = (
                "SHORTCUT_STILL_WORKS_NOT_NOVEL"
                if regret <= number(row["value_equivalence"], positive=True)
                else "DECISION_NOVELTY_PASSES_PUBLIC_ONLY"
            )
        else:
            status = "DECISION_NOVELTY_PASSES_PUBLIC_ONLY"
        result.append(
            {
                "id": row["id"],
                "status": status,
                "mask_distance": distance,
                "reference_pick": actual,
                "shortcut_pick": predicted,
                "regret_buyer_unit": regret,
                "scored": False,
            }
        )
    return {
        "family": challenge,
        "rows": result,
        "status": "DESCRIPTIVE" if result else "UNRESOLVED_NO_VARIANT_TRUTH",
        "hidden_bank_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("briefs", "novelty"))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument(
        "--seed", type=int, default=0, help="public rehearsal seed only"
    )
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--proposal", choices=("P", "Q"), default="P")
    args = parser.parse_args(argv)
    if args.input.stat().st_size > 16 * 1024 * 1024:
        parser.error("bounded public input required")
    data = json.loads(args.input.read_text(encoding="utf-8"))
    report = (
        decision_novelty(FAMILY, data)
        if args.operation == "novelty"
        else briefs(data, seed=args.seed, count=args.count, proposal=args.proposal)
    )
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
