"""Public f08 preparation; text/fixture algebra only, never solver or dispatch."""

from __future__ import annotations

import argparse
import functools
import hashlib
import importlib.util
import itertools
import json
import math
import random
from pathlib import Path

from carbon.design_search import tasks

FAMILY = "f08"
SCHEMA = "carbon.f08-preparation.v1"
ROOT = Path(__file__).resolve().parents[2]
SOURCE = "scripts/dev/reference_packages/calculix/f08_deck.py"
# Re-pinned 2026-10-15 to the local rebuild of the same sources.lock.json after
# smoke, feature proof, MMS and closed-form rod verification passed on it
# (docs/development/evidence/reference-packages-01/calculix.json local_rebuilds).
# The original build was sha256:d9ef68d016226a945c7eefcb6b2261c60a11249ee0f93458ae6c3aca956fd6f8.
IMAGE = "sha256:16869c9cb7f14994f3bed3152809efdec14c5b3ec1849730d7b6c8f689d9642b"
MESH_IMAGE = "ghcr.io/carbonphysicsai/carbon-motor-reference@sha256:599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05"
FIELDS = (
    "length_mm",
    "width_mm",
    "thickness_mm",
    "rib_height_mm",
    "rib_thickness_mm",
    "relief_length_mm",
)
BOUNDS = ((180, 260), (60, 100), (4, 8), (8, 16), (3, 5), (20, 60))
DAMPING = (0.005, 0.01, 0.02)
OBSERVABLES = (
    "mass_kg",
    "static_tip_mm_per_n",
    "tip_frf_complex_mm_per_n",
    "probe_frf_complex_mm_per_n",
    "eigen_hz",
    "tip_peak_mm_per_n",
    "tip_peak_hz",
)
MATERIAL = {
    "E_mpa": 70000,
    "nu": 0.33,
    "rho_t_mm3": 2.7e-9,
    "scope": "SYNTHETIC_AL_LIKE_DEVELOPMENT",
}


def finite(value, positive=False):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or (positive and value <= 0)
    ):
        raise ValueError("finite supported physical number required")
    return float(value)


def pin(value):
    if (
        type(value) is not str
        or not value.startswith("sha256:")
        or len(value) != 71
        or any(c not in "0123456789abcdef" for c in value[7:])
    ):
        raise ValueError("complete immutable identity required")
    return value


def seal(body):
    return {**body, "registration_digest": tasks.digest(body)}


def validate(r):
    if type(r) is not dict or set(r) != {
        "schema",
        "family",
        "scope",
        "authority",
        "grammar",
        "P",
        "Q",
        "w",
        "pins",
        "registration_digest",
    }:
        raise ValueError("closed public preparation registration required")
    if (
        r["schema"] != SCHEMA
        or r["family"] != FAMILY
        or r["scope"] not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
    ):
        raise ValueError("public f08 preparation only")
    if (
        r["registration_digest"]
        != tasks.digest({k: v for k, v in r.items() if k != "registration_digest"})
        or not r["authority"]
    ):
        raise ValueError("digest-bound authority required")
    if set(r["grammar"]) != set(FIELDS):
        raise ValueError("six-coordinate packet grammar required")
    for field, bounds in zip(FIELDS, BOUNDS):
        g = r["grammar"][field]
        if set(g) != {"min", "max", "step"}:
            raise ValueError("registered quantization required")
        lo, hi, step = finite(g["min"]), finite(g["max"]), finite(g["step"], True)
        if not bounds[0] <= lo <= hi <= bounds[1] or not math.isclose(
            (hi - lo) / step, round((hi - lo) / step)
        ):
            raise ValueError("packet envelope/lattice required")
    for law in ("P", "Q", "w"):
        values = r[law]
        if (
            set(values) != {str(v) for v in DAMPING}
            or any(finite(v) < 0 for v in values.values())
            or not math.isclose(sum(values.values()), 1)
        ):
            raise ValueError("separate P/Q/w over supported damping required")
    if any(r["P"][k] > 0 and r["Q"][k] <= 0 for k in r["P"]):
        raise ValueError("Q must support P")
    if set(r["pins"]) != {
        "image",
        "mesh_image",
        "deck",
        "proof",
        "material",
        "observer",
    }:
        raise ValueError("complete environment/material/observer pins required")
    if r["pins"]["image"] != IMAGE or r["pins"]["mesh_image"] != MESH_IMAGE:
        raise ValueError("repinning requires prospective verification")
    for key in ("deck", "proof", "material", "observer"):
        pin(r["pins"][key])
    if r["pins"]["material"] != tasks.digest(MATERIAL):
        raise ValueError("packet synthetic material law required")
    return r


def action(r, values):
    validate(r)
    if type(values) is not dict or set(values) != set(FIELDS):
        raise ValueError("complete physical coordinates required")
    result = {}
    for field in FIELDS:
        g, v = r["grammar"][field], finite(values[field])
        if not g["min"] <= v <= g["max"] or not math.isclose(
            (v - g["min"]) / g["step"], round((v - g["min"]) / g["step"])
        ):
            raise ValueError("action outside registered lattice")
        result[field] = v
    L, W, _, _, tr, relief = (result[k] for k in FIELDS)
    if W / 4 - tr / 2 <= 10 or min((L - relief) / 2, W / 2 - 10) < 6:
        raise ValueError("rib/relief intersection or insufficient ligament")
    return result


def actions(r, *, seed, count):
    validate(r)
    if type(seed) is not int or type(count) is not int or not 1 <= count <= 1000:
        raise ValueError("bounded own-seed public generation required")
    rng, found = random.Random(seed), {}
    for _ in range(count * 100):
        row = {
            k: g["min"]
            + g["step"] * rng.randint(0, round((g["max"] - g["min"]) / g["step"]))
            for k, g in r["grammar"].items()
        }
        try:
            row = action(r, row)
        except ValueError:
            continue
        found[tasks.digest(row)] = row
        if len(found) == count:
            return list(found.values())
    raise ValueError("not enough valid unique registered actions")


def conditions(r, *, seed, count, law="P"):
    validate(r)
    if (
        law not in ("P", "Q")
        or type(count) is not int
        or not 1 <= count <= 10000
        or type(seed) is not int
    ):
        raise ValueError("bounded registered law required")
    rng = random.Random(seed)
    return [
        {"damping_ratio": float(v), "band_hz": [80, 600]}
        for v in rng.choices(list(r[law]), weights=list(r[law].values()), k=count)
    ]


def case(r, coordinates, damping, *, h_mm=3, modes=48):
    validate(r)
    if (
        finite(damping) not in DAMPING
        or finite(h_mm) not in (3, 2.25, 1.7)
        or type(modes) is not int
        or modes not in (12, 24, 48)
    ):
        raise ValueError("supported damping/mesh/mode rung required")
    body = {
        "family": FAMILY,
        "scope": r["scope"],
        "action": action(r, coordinates),
        "condition": {"damping_ratio": damping, "band_hz": [80, 600]},
        "rung": {"h_mm": h_mm, "modes": modes},
        "pins": r["pins"],
        "registration_digest": r["registration_digest"],
    }
    return {**body, "case_digest": tasks.digest(body)}


def verify_case(c):
    if (
        type(c) is not dict
        or set(c)
        != {
            "family",
            "scope",
            "action",
            "condition",
            "rung",
            "pins",
            "registration_digest",
            "case_digest",
        }
        or c["family"] != FAMILY
        or c["scope"] not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
    ):
        raise ValueError("closed public case required")
    if c["case_digest"] != tasks.digest(
        {k: v for k, v in c.items() if k != "case_digest"}
    ):
        raise ValueError("case identity differs")
    pin(c["registration_digest"])
    if set(c["action"]) != set(FIELDS) or any(
        not lo <= finite(c["action"][k]) <= hi for k, (lo, hi) in zip(FIELDS, BOUNDS)
    ):
        raise ValueError("case outside six-coordinate packet envelope")
    L, W, _, _, tr, relief = (c["action"][k] for k in FIELDS)
    if W / 4 - tr / 2 <= 10 or min((L - relief) / 2, W / 2 - 10) < 6:
        raise ValueError("invalid physical shape")
    if (
        set(c["condition"]) != {"damping_ratio", "band_hz"}
        or c["condition"]["band_hz"] != [80, 600]
        or finite(c["condition"]["damping_ratio"]) not in DAMPING
    ):
        raise ValueError("unsupported service condition")
    if (
        set(c["rung"]) != {"h_mm", "modes"}
        or finite(c["rung"]["h_mm"]) not in (3, 2.25, 1.7)
        or type(c["rung"]["modes"]) is not int
        or c["rung"]["modes"] not in (12, 24, 48)
    ):
        raise ValueError("unsupported refinement rung")
    if (
        set(c["pins"])
        != {"image", "mesh_image", "deck", "proof", "material", "observer"}
        or c["pins"]["image"] != IMAGE
        or c["pins"]["mesh_image"] != MESH_IMAGE
        or c["pins"]["material"] != tasks.digest(MATERIAL)
    ):
        raise ValueError("case pins/law differ")
    for k in ("deck", "proof", "material", "observer"):
        pin(c["pins"][k])
    return c


def physical(c):
    verify_case(c)
    # Whole-geometry holdout: renaming conditions or changing rungs cannot renew it.
    return tasks.digest(c["action"])


def panel(cases, *, completed, scheduled):
    if (
        type(cases) is not list
        or not 1 <= len(cases) <= 3000
        or type(completed) is not list
        or type(scheduled) is not list
        or len(completed) > 20000
        or len(scheduled) > 20000
    ):
        raise ValueError("explicit completed AND scheduled inventories required")
    key = lambda c: tasks.digest(
        {k: verify_case(c)[k] for k in ("action", "condition", "rung", "pins")}
    )
    prior = {key(c): c for c in completed + scheduled}
    rows, seen = [], set()
    for c in cases:
        verify_case(c)
        if key(c) in seen:
            continue
        seen.add(key(c))
        rows.append({"case": c, "reuse": key(c) in prior})
    return {
        "status": "DRAFT_NOT_REGISTERED",
        "dispatch_allowed": False,
        "inventory_coverage": ["COMPLETED", "SCHEDULED"],
        "tuples": rows,
    }


@functools.lru_cache(maxsize=1)
def source():
    # Trusted repo source: importing defines helpers only. Never call runners.
    spec = importlib.util.spec_from_file_location("carbon_f08_deck", ROOT / SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def deck(c):
    verify_case(c)
    for key, path in (
        ("deck", ROOT / SOURCE),
        ("proof", ROOT / "scripts/dev/reference_packages/calculix/f08_proof.py"),
    ):
        if c["pins"][key] != "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError("current source differs from registered deck/proof")
    s = source()
    mesh_script = s.gmsh_script(c["action"], c["rung"]["h_mm"])
    # Template intentionally cannot execute before mesh+consistent nodal-load assembly.
    text = f"""*HEADING
f08 UNVERIFIED TEMPLATE {c['case_digest']}
*INCLUDE,INPUT=mesh.inp
*BOUNDARY
ROOT,1,3
*MATERIAL,NAME=AL
*ELASTIC
70000,0.33
*DENSITY
2.7e-9
*SOLID SECTION,ELSET=EALL,MATERIAL=AL
*STEP
*FREQUENCY,STORAGE=YES
{c['rung']['modes']}
*NODE PRINT,NSET=OBS
U
*END STEP
*STEP
*STEADY STATE DYNAMICS
80,600,20,3
*MODAL DAMPING
1,{c['rung']['modes']},{c['condition']['damping_ratio']}
*CLOAD,OP=NEW
__CONSISTENT_TRI6_UNIT_FORCE_LOADS__
*NODE PRINT,NSET=OBS
U
*END STEP
*STEP
*STATIC
*CLOAD,OP=NEW
__CONSISTENT_TRI6_UNIT_FORCE_LOADS__
*NODE PRINT,NSET=OBS
U
*END STEP
"""
    return {
        "case_digest": c["case_digest"],
        "status": "DRAFT_UNVERIFIED_NOT_RUNNABLE",
        "dispatch_allowed": False,
        "mesh_python": mesh_script,
        "ccx_template": text,
        "assembly": "Use existing f08_deck.face_weights on imprinted pad/probe; normalize pad resultant to 1 N, OBS includes tip centroid and probe nodes. Data Collection owns actual mesh/deck assembly and proof.",
        "phase": "exp(+i omega t)",
        "material_scope": "SYNTHETIC_AL_LIKE_DEVELOPMENT",
    }


def observe(c, data, *, uncertainty=None):
    verify_case(c)
    if (
        type(data) is not dict
        or set(data)
        != {
            "case_digest",
            "phase",
            "mass_kg",
            "static_tip_mm_per_n",
            "frequency_hz",
            "tip_real",
            "tip_imag",
            "probe_real",
            "probe_imag",
            "eigen_hz",
        }
        or data["case_digest"] != c["case_digest"]
        or data["phase"] != "exp(+i omega t)"
    ):
        raise ValueError("matched complete signed observer contract required")
    f = data["frequency_hz"]
    if (
        type(f) is not list
        or not 2 <= len(f) <= 20000
        or f[0] != 80
        or f[-1] != 600
        or any(finite(b) <= finite(a) for a, b in itertools.pairwise(f))
    ):
        raise ValueError("complete increasing 80-600 Hz curve required")
    for k in ("tip_real", "tip_imag", "probe_real", "probe_imag"):
        if type(data[k]) is not list or len(data[k]) != len(f):
            raise ValueError("full complex tip/probe curves required")
        for v in data[k]:
            finite(v)
    eigen = data["eigen_hz"]
    if (
        type(eigen) is not list
        or len(eigen) != c["rung"]["modes"]
        or any(finite(v, True) <= 0 for v in eigen)
        or any(b < a for a, b in itertools.pairwise(eigen))
    ):
        raise ValueError("complete ordered retained-mode frequencies required")
    zeta = c["condition"]["damping_ratio"]
    resolved_grid = True
    for mode in eigen:
        width = 2 * zeta * mode
        if 80 <= mode <= 600:
            lo, hi = max(80, mode - width / 2), min(600, mode + width / 2)
            gaps = [b - a for a, b in itertools.pairwise(f) if b > lo and a < hi]
            resolved_grid &= bool(gaps) and max(gaps) <= width / 10 * (1 + 1e-9)
    tip = [math.hypot(re, im) for re, im in zip(data["tip_real"], data["tip_imag"])]
    probe = [
        math.hypot(re, im) for re, im in zip(data["probe_real"], data["probe_imag"])
    ]
    values = {
        "mass_kg": finite(data["mass_kg"], True),
        "static_tip_mm_per_n": finite(data["static_tip_mm_per_n"], True),
        "tip_peak_mm_per_n": max(tip),
    }
    verdict = "UNRESOLVED"
    margins = None
    if uncertainty is not None:
        if (
            type(uncertainty) is not dict
            or set(uncertainty)
            != {
                "case_digest",
                "accepted_receipt_digest",
                "mass_kg",
                "static_tip_mm_per_n",
                "tip_peak_mm_per_n",
            }
            or uncertainty["case_digest"] != c["case_digest"]
        ):
            raise ValueError("case-bound accepted numerical uncertainty required")
        pin(uncertainty["accepted_receipt_digest"])
        if any(finite(uncertainty[k]) < 0 for k in values):
            raise ValueError("nonnegative uncertainty required")
        limits = {
            "mass_kg": 0.45,
            "static_tip_mm_per_n": 0.03,
            "tip_peak_mm_per_n": 0.15,
        }
        margins = {k: limits[k] - v for k, v in values.items()}
        if resolved_grid:
            if any(margins[k] < -uncertainty[k] for k in values):
                verdict = "INFEASIBLE"
            elif all(margins[k] > uncertainty[k] for k in values):
                verdict = "FEASIBLE"
    return {
        "values": values,
        "tip_peak_hz": f[tip.index(max(tip))],
        "probe_peak_mm_per_n": max(probe),
        "grid_resolved": resolved_grid,
        "margins": margins,
        "verdict": verdict,
        "scope": c["scope"],
        "qualified": False,
        "signed_curves": {
            k: data[k]
            for k in (
                "frequency_hz",
                "tip_real",
                "tip_imag",
                "probe_real",
                "probe_imag",
            )
        },
    }


def train_plan(cases, test_cases):
    if (
        type(cases) is not list
        or type(test_cases) is not list
        or len(cases) > 3000
        or not 1 <= len(test_cases) <= 3000
    ):
        raise ValueError("bounded candidate TRAIN and nonempty test panel required")
    forbidden = {physical(c) for c in test_cases}
    selected = {c["case_digest"]: c for c in cases if physical(c) not in forbidden}
    return {
        "status": "DRAFT_NOT_REGISTERED",
        "cases": list(selected.values()),
        "holdout": "WHOLE_GEOMETRY_ALL_DAMPING_AND_RUNGS",
    }


def design_verdict(rows):
    """One common support over all mandatory damping; no compensating averages."""
    if type(rows) is not list or not rows or len(rows) > 3:
        raise ValueError("bounded whole-support observer panel required")
    geometry, conditions_seen, reports = None, set(), []
    for row in rows:
        if type(row) is not dict or set(row) != {"case", "data", "uncertainty"}:
            raise ValueError("matched case/data/uncertainty row required")
        c = verify_case(row["case"])
        identity = tasks.digest({k: c[k] for k in ("action", "pins", "scope")})
        if geometry is not None and geometry != identity:
            raise ValueError("different supports cannot compose one answer")
        geometry = identity
        zeta = c["condition"]["damping_ratio"]
        if zeta in conditions_seen:
            raise ValueError("duplicate damping condition")
        conditions_seen.add(zeta)
        reports.append(observe(c, row["data"], uncertainty=row["uncertainty"]))
    statuses = {r["verdict"] for r in reports}
    verdict = (
        "INFEASIBLE"
        if "INFEASIBLE" in statuses
        else (
            "FEASIBLE"
            if conditions_seen == set(DAMPING) and statuses == {"FEASIBLE"}
            else "UNRESOLVED"
        )
    )
    return {
        "verdict": verdict,
        "worst_tip_mm_per_n": max(r["values"]["tip_peak_mm_per_n"] for r in reports),
        "missing_damping": sorted(set(DAMPING) - conditions_seen),
        "reports": reports,
        "qualified": False,
    }


def kit_hook(r, cases, kit):
    validate(r)
    if (
        set(kit) != {"scope", "grammar", "damping", "band_hz", "observables", "pins"}
        or kit["scope"] != r["scope"]
        or kit["pins"] != r["pins"]
        or kit["band_hz"] != [80, 600]
        or not set(OBSERVABLES) <= set(kit["observables"])
        or set(kit["damping"]) != set(DAMPING)
    ):
        raise ValueError("complete kit physics/observable/pin coverage required")
    if not cases or kit["grammar"] != r["grammar"]:
        raise ValueError("full lattice coverage and nonempty panel required")
    for c in cases:
        rebuilt = case(r, c["action"], c["condition"]["damping_ratio"], **c["rung"])
        if rebuilt != c:
            raise ValueError("kit/panel registration differs")
    return {"covered": True, "case_count": len(cases), "registered_kit": False}


def manufactured(x, y, z, *, amplitude=1e-4, length=1):
    """3D small-strain elastic MMS: u_i=a*x_i^3/L^2, f=-div(sigma)."""
    xyz = [finite(v) for v in (x, y, z)]
    a, L = finite(amplitude, True), finite(length, True)
    lam = 70000 * 0.33 / ((1 + 0.33) * (1 - 2 * 0.33))
    mu = 70000 / (2 * (1 + 0.33))
    return {
        "u_mm": [a * v**3 / L**2 for v in xyz],
        "body_force_n_mm3": [-6 * a * (lam + 2 * mu) * v / L**2 for v in xyz],
    }


def compare(export, *, operators):
    from carbon.development_comparison import reduced_baselines

    if export.get("family") != FAMILY:
        raise ValueError("f08 full-output panel required")
    return reduced_baselines.measure(export, operators=operators)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("actions", "conditions", "deck"))
    p.add_argument("input", type=Path)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--count", type=int, default=8)
    args = p.parse_args()
    data = json.loads(args.input.read_text())
    result = (
        deck(data)
        if args.command == "deck"
        else (
            actions(data, seed=args.seed, count=args.count)
            if args.command == "actions"
            else conditions(data, seed=args.seed, count=args.count)
        )
    )
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
