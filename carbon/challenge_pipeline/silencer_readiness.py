"""Bounded public f13 preparation. No writes, reference calls or dispatch."""

from __future__ import annotations

import argparse
import cmath
import hashlib
import importlib.util
import json
import math
import random
from pathlib import Path

FAMILY = "f13"
RHO, C = 1.2, 343.0
S_PORT = math.pi * 0.025**2
AMPLITUDE = math.sqrt(2 * RHO * C / S_PORT)
MESH_IMAGE = "ghcr.io/carbonphysicsai/carbon-motor-reference@sha256:599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05"
SCHEMA = "carbon.f13-preparation.v1"
FIELDS = (
    "radius1_mm",
    "radius2_mm",
    "length1_mm",
    "length2_mm",
    "neck_length_mm",
    "neck_offset_mm",
)
BOUNDS = ((55, 70), (55, 70), (40, 110), (40, 110), (10, 50), (0, 25))
#: The one f13 Elmer image pin (local 2026-10-15 rebuild, f13-rebuild.json).
#: f13_deck/f13_proof/f13_power_probe/f13_triage_freeze read it from here,
#: so a later accepted pin is this one line plus a re-run.
IMAGE = "sha256:61be1cb77c51fcdd822250e372754a9ce728a5bb42f39b7ba03cdf5e70901add"
DECK_SHA = "sha256:696d81d7275d349c441edcd80b209032a6abf0c69cfe4113878f576fb84890fb"
PINS = {
    "image": IMAGE,
    "mesh_image": MESH_IMAGE,
    "deck_sha256": DECK_SHA,
    "deck_version": "f13-deck.v2",
    "observer": "f13-panel-planes.v1",
    "phasor": "exp(+i*omega*t)",
    "linear_solver": "bicgstabl4-ilu2-1e-10",
}
OBSERVABLES = ("p10_tl_db", "minimum_tl_db", "power_residual", "complex_r", "complex_t")


def digest(value):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
    )


def number(value):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError("finite numeric value required")
    return float(value)


def geometry(action):
    if type(action) is not dict or set(action) != set(FIELDS):
        raise ValueError("closed six-coordinate geometry required")
    out = {key: number(action[key]) for key in FIELDS}
    if any(not low <= out[key] <= high for key, (low, high) in zip(FIELDS, BOUNDS)):
        raise ValueError("action outside packet support")
    if out["neck_offset_mm"] + 20 + 10 > min(out["radius1_mm"], out["radius2_mm"]):
        raise ValueError("neck wall clearance required")
    # Original panel/package planes include the two 10 mm physical stubs.
    if out["length1_mm"] + out["length2_mm"] + out["neck_length_mm"] + 20 > 300:
        raise ValueError("buyer package exceeds 300 mm")
    return out


def _count(count, seed):
    if type(count) is not int or not 1 <= count <= 4096 or type(seed) is not int:
        raise ValueError("bounded public count and integer seed required")


def actions(count, seed):
    """The registered geometry law (F13-SCIENCE-VALUES-01 F7): uniform
    independent parameters conditioned on clearance/packaging; refuse, never
    clip. A public seed gives public designs; a bank uses the operator seed."""
    _count(count, seed)
    rng, out, seen = random.Random(seed), [], set()
    for _ in range(count * 20):
        a = dict(zip(FIELDS, (rng.uniform(lo, hi) for lo, hi in BOUNDS)))
        try:
            a = geometry(a)
        except ValueError:
            continue
        key = digest(a)
        if key not in seen:
            out.append(a)
            seen.add(key)
        if len(out) == count:
            return out
    raise ValueError(
        "bounded geometry proposal exhausted; no clipped/redrawn questions"
    )


def questions(count, seed):
    """Public draws from the registered DEVELOPMENT requirement law P
    (F13-SCIENCE-VALUES-01 F1-F3): independent uniform p10 floor [5, 7] dB,
    length cap [240, 300] mm, diameter cap [120, 140] mm; Q3 = P; unit outer
    weight. A public seed gives public practice draws, never a hidden bank."""
    _count(count, seed)
    rng = random.Random(seed)
    return [
        {
            "p10_floor_db": rng.uniform(5, 7),
            "package_length_cap_mm": rng.uniform(240, 300),
            "package_diameter_cap_mm": rng.uniform(120, 140),
            "P": "REGISTERED_DEVELOPMENT_UNIFORM",
            "Q": "Q3=P",
            "w": 1.0,
            "decision": VALUES_DECISION,
            "none_feasible": "RETAIN_NO_REDRAW",
        }
        for _ in range(count)
    ]


def frequency_grid(rung):
    if type(rung) is not int or rung not in (1, 2):
        raise ValueError("registered mesh/frequency rung 1 or 2 required")
    return [500 + i * 10 / rung for i in range(200 * rung + 1)]


def case(action, rung):
    action = geometry(action)
    return {
        "action": action,
        "condition": "air-rigid-no-flow-500-2500",
        "rung": rung,
        "frequencies_hz": frequency_grid(rung),
        "pins": PINS.copy(),
    }


def validate_case(row):
    if type(row) is not dict or set(row) != {
        "action",
        "condition",
        "rung",
        "frequencies_hz",
        "pins",
    }:
        raise ValueError("exact physical case required")
    if row != case(row["action"], row["rung"]):
        raise ValueError("case condition/grid/pins mismatch")
    return row


def physical_key(row):
    validate_case(row)
    return digest({"action": row["action"], "condition": row["condition"]})


def panel(designs, rungs, *, completed, scheduled):
    """Explicit inventories required; empty inventories assert no known reuse."""
    if not designs or not rungs or len(designs) * len(rungs) > 10000:
        raise ValueError("bounded nonempty panel required")
    known = {}
    for state, rows in (("COMPLETED", completed), ("SCHEDULED", scheduled)):
        for row in rows:
            key = digest(validate_case(row))
            if key in known:
                raise ValueError("duplicate retained/scheduled identity")
            known[key] = state
    entries = {}
    for a in designs:
        for rung in rungs:
            row = case(a, rung)
            key = digest(row)
            entries[key] = {"case": row, "reuse": known.get(key, "NEW")}
    body = {
        "schema": SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT",
        "family": FAMILY,
        "cases": list(entries.values()),
        "reuse_inventory_count": len(known),
        "status": "PROPOSED_NOT_REGISTERED",
        "dispatchable": False,
    }
    return {**body, "panel_digest": digest(body)}


def train_plan(designs, test_cases):
    if not test_cases:
        raise ValueError("explicit nonempty test-panel inventory required")
    excluded = {physical_key(r) for r in test_cases}
    rows = {physical_key(case(a, 1)): case(a, 1) for a in designs}
    return {
        "scope": "PUBLIC_DEVELOPMENT",
        "status": "PROPOSED_NOT_REGISTERED",
        "cases": [r for key, r in rows.items() if key not in excluded],
        "excluded": len(set(rows) & excluded),
        "dispatchable": False,
    }


def deck(row):
    validate_case(row)
    # Importable wheel stays independent of non-packaged scripts. Rendering
    # needs the repository's exact hash-checked owner-authored source only.
    source = (
        Path(__file__).resolve().parents[2]
        / "scripts/dev/reference_packages/elmer/f13_deck.py"
    )
    if not source.is_file() or digest_bytes(source.read_bytes()) != DECK_SHA:
        raise ValueError("Elmer deck source changed; prospective repin required")
    spec = importlib.util.spec_from_file_location("pinned_f13_deck", source)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    return {
        "status": "UNVERIFIED_DECK_DRAFT",
        "pins": row["pins"],
        "files": {
            "make_mesh.py": reference.gmsh_script(row["action"], 8 / row["rung"], 60),
            "case.sif": reference.sif(row["frequencies_hz"]),
            "ELMERSOLVER_STARTINFO": "case.sif\n1\n",
        },
        "reference_stub_mm": 10,
        "computational_stub_mm": 60,
        "frequency_systems": len(row["frequencies_hz"]),
        "solver_processes": 1,
        "dispatchable": False,
    }


def digest_bytes(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


#: F13-SCIENCE-VALUES-01 C1/C2: signed plane power residual band (derived
#: from the 0.25 dB p10 band at TL 15 dB) and the packet's 1 % outer gate,
#: applied to the saved |p|^2 integral (Robin) residual.
POWER_PLANE_BAND = 0.0018
POWER_INTEGRAL_BAND = 0.01
VALUES_DECISION = "F13-SCIENCE-VALUES-01"
#: Numerical lead added to each 10 mm panel stub by the v2 deck (60 mm).
LEAD_M = 0.05


def deembed(frequency, reflection, transmission, lead_m=LEAD_M):
    """Both equal leads d=lead_m, p+ travels exp(-ikz), exp(+iwt)."""
    phase = cmath.exp(2j * (2 * math.pi * number(frequency) / C) * number(lead_m))
    return reflection * phase, transmission * phase


INTEGRAL_KEYS = {
    "f_hz",
    "in_real",
    "in_imag",
    "out_real",
    "out_imag",
    "in_abs2",
    "out_abs2",
}


def observe_rows(frequencies, integrals, *, lead_m=LEAD_M):
    """Per-frequency de-embedded observer for any ordered frequency list.

    Returns (rows, finding). Raw values are never clipped or normalised.
    """
    if not isinstance(integrals, list) or len(integrals) != len(frequencies):
        raise ValueError("complete ordered frequency coverage required")
    s, z, a = S_PORT, RHO * C, AMPLITUDE
    pin = a * a * s / (2 * z)
    out, finding = [], False
    for f, raw in zip(frequencies, integrals):
        if set(raw) != INTEGRAL_KEYS:
            raise ValueError("closed mapped port integral row required")
        values = {k: number(v) for k, v in raw.items()}
        if values["f_hz"] != f:
            raise ValueError("missing/reordered/duplicate frequencies")
        ii = complex(values["in_real"], values["in_imag"])
        io = complex(values["out_real"], values["out_imag"])
        hin, hout = values["in_abs2"], values["out_abs2"]
        vin, vout = hin - abs(ii) ** 2 / s, hout - abs(io) ** 2 / s
        eps = 64 * math.ulp(1.0) * max(hin, hout, abs(ii) ** 2 / s, abs(io) ** 2 / s)
        if min(hin, hout) < 0 or min(vin, vout) < -eps:
            finding = True
        r, t = deembed(f, (ii / s - a) / a, io / s / a, lead_m)
        pr, pt = abs(r) ** 2 * pin, abs(t) ** 2 * pin
        residual = (pin - pr - pt) / pin
        robin = (hin - 2 * a * ii.real + a * a * s) / (2 * z)
        residual_integral = (pin - robin - hout / (2 * z)) / pin
        if (
            abs(residual) > POWER_PLANE_BAND
            or abs(residual_integral) > POWER_INTEGRAL_BAND
            or pt <= 0
            or max(pr, pt) > pin * (1 + POWER_PLANE_BAND)
        ):
            finding = True
        tl = -10 * math.log10(pt / pin) if pt > 0 else None
        out.append(
            {
                "frequency_hz": f,
                "r": [r.real, r.imag],
                "t": [t.real, t.imag],
                "tl_db": tl,
                "incident_w": pin,
                "reflected_w": pr,
                "transmitted_w": pt,
                "signed_plane_residual": residual,
                "signed_integral_residual": residual_integral,
                "in_variance_pa2_m2": vin,
                "out_variance_pa2_m2": vout,
            }
        )
    return out, finding


def interval_mean(frequencies, values):
    """Trapezoidal frequency-interval-weighted mean (same weights as p10)."""
    total = weight = 0.0
    for i in range(len(frequencies) - 1):
        df = frequencies[i + 1] - frequencies[i]
        total += df * (values[i] + values[i + 1]) / 2
        weight += df
    return total / weight if weight else values[0]


def observe(row, integrals, *, uncertainty_db=None):
    """Explicit mapped mean-pressure port integrals; no column-order guesses.

    raw row: f_hz, in_real/in_imag/out_real/out_imag, in_abs2/out_abs2.
    H=integral(|p|^2), I=integral(p), SI units, exact equal port area.
    Uncertainty is a supplied refinement estimate, not an accepted tolerance.
    """
    validate_case(row)
    if uncertainty_db is not None and number(uncertainty_db) < 0:
        raise ValueError("nonnegative uncertainty required")
    out, finding = observe_rows(row["frequencies_hz"], integrals)
    curve = [v["tl_db"] for v in out]
    from carbon.development_comparison.portfolio_baselines import interval_p10

    p10 = (
        None
        if any(v is None for v in curve)
        else interval_p10(row["frequencies_hz"], curve)
    )
    return {
        "status": "REFERENCE_FINDING" if finding else "OBSERVED_NOT_QUALIFIED",
        "case_digest": digest(row),
        "observer": PINS["observer"],
        "rows": out,
        "p10_tl_db": p10,
        "mean_tl_db": (
            None if p10 is None else interval_mean(row["frequencies_hz"], curve)
        ),
        "minimum_tl_db": min(curve) if p10 is not None else None,
        "p10_interval_db": (
            None
            if p10 is None or uncertainty_db is None
            else [p10 - uncertainty_db, p10 + uncertainty_db]
        ),
        "power_bands": {
            "plane": POWER_PLANE_BAND,
            "integral": POWER_INTEGRAL_BAND,
            "decision": VALUES_DECISION,
        },
        "buyer_verdict": "UNRESOLVED",
        "full_band_refinement": "ACCEPTANCE_REQUIRED",
        "frequency_systems": len(out),
        "qualified": False,
    }


def manufactured_helmholtz(x, y, z, wavenumber):
    """p=sin(pi x)sin(pi y)sin(pi z); (laplacian+k^2)p=s in unit cube."""
    x, y, z, k = map(number, (x, y, z, wavenumber))
    p = math.sin(math.pi * x) * math.sin(math.pi * y) * math.sin(math.pi * z)
    return {
        "pressure_real": p,
        "pressure_imag": 0.0,
        "source_real": (k * k - 3 * math.pi**2) * p,
        "source_imag": 0.0,
    }


def kit_domain(domain, cases):
    """Coverage hook, not a registered training kit or proof of solver support."""
    if not cases or set(domain) != {
        "action_bounds",
        "conditions",
        "observables",
        "observer",
    }:
        raise ValueError("nonempty cases and explicit kit domain required")
    if set(domain["action_bounds"]) != set(FIELDS):
        return False
    for row in cases:
        validate_case(row)
        if row["condition"] not in domain["conditions"]:
            return False
        for key, value in row["action"].items():
            lo, hi = map(number, domain["action_bounds"][key])
            if not lo <= value <= hi:
                return False
    return domain["observer"] == PINS["observer"] and set(OBSERVABLES) <= set(
        domain["observables"]
    )


def compare(export, *, material=None, operators=None):
    """Full-curve decision/cost/ranking reports from both existing arms.

    Plane-wave arm abstains above cutoff or for offsets. The reduced/modal arm
    needs charged independently prepared common-basis operators and holdouts.
    """
    if export.get("family") != FAMILY:
        raise ValueError("f13 public export required")
    from carbon.design_search import producer_panels
    from carbon.development_comparison import cheap_baselines as cb
    from carbon.development_comparison import portfolio_baselines, reduced_baselines

    producer_panels.adapt_export(export)
    for entry in export["questions"]:
        for _, task, _ in cb._panels(entry):
            if task["identity"]["observer_version"] != PINS["observer"]:
                raise ValueError("matched de-embedded panel-plane observer required")
    return {
        "plane_wave": portfolio_baselines.measure(export, material=material),
        "strongest_reduced": reduced_baselines.measure(export, operators=operators),
        "V4": "NOT_DEMONSTRATED",
    }


def budget_registration(root):
    """Reuse the adopted #1047 f13 row without changing its historical identity."""
    from carbon.design_search import budget_registration as br

    raw = json.loads(
        (
            Path(root)
            / "docs/development/challenge_pipeline/equal-budget-registration-v1.json"
        ).read_text()
    )
    br.validate(raw).cap(FAMILY, "base")
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("actions", "questions", "deck", "panel", "train", "observe")
    )
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--input", type=Path)
    args = parser.parse_args(argv)
    if args.command in ("actions", "questions"):
        result = (actions if args.command == "actions" else questions)(
            args.count, args.seed
        )
    else:
        if args.input is None:
            parser.error("explicit public JSON input required")
        if args.input.stat().st_size > 4 * 1024 * 1024:
            parser.error("input exceeds 4 MiB")
        data = json.loads(args.input.read_text(encoding="utf-8"))
        if data.get("scope") != "PUBLIC_DEVELOPMENT":
            parser.error("only explicit public development input permitted")
        if args.command == "deck":
            result = deck(data["case"])
        elif args.command == "panel":
            result = panel(
                data["designs"],
                data["rungs"],
                completed=data["completed"],
                scheduled=data["scheduled"],
            )
        elif args.command == "train":
            result = train_plan(data["designs"], data["test_cases"])
        else:
            result = observe(
                data["case"],
                data["integrals"],
                uncertainty_db=data.get("uncertainty_db"),
            )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
