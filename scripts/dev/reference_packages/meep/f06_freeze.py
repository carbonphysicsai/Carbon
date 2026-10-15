"""Freeze f06 Meep decks for the triage panel or a bank (DEVELOPMENT).

    python3 f06_freeze.py triage --out DIR [--grid-nm 30] [--image ID]
    python3 f06_freeze.py bank --seed-file OPERATOR_SEED --count B --out DIR [--grid-nm 30]

Triage: the eight public recipe cases of reference-route-panels.json, each a
complete case (one normalization + five geometry runs = 9 vectors x 5
wavelengths), at the registered reference grid; the registered refinement
witnesses (nominal-narrow, nominal-wide) at the next finer rung; the 3D
straight-guide control; a cold repeat of the first primary. Schema
``carbon.reference-triage.frozen-decks.v1``.

Bank: B designs drawn from F06-SCIENCE-VALUES-01's design law (uniform
independent grammar, rejection-conditioned on all nine perturbed geometries
valid) with an operator-held seed. The seed file and the bank output are
operator material: the script refuses an output directory inside the
repository and never prints designs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f06_controls as C
import f06_deck as F

REPO = HERE.parents[3]
COMMAND = "python3 f06_run.py case.json result.json > meep.log 2>&1"
FINER = {40: 30, 30: 20, 20: 15}


def _files(case_dir):
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path(case_dir).iterdir())
        if p.is_file()
    }


def _write(out, family_dir, name, case):
    d = Path(out) / family_dir / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "case.json").write_text(json.dumps(case, indent=1, sort_keys=True) + "\n")
    (d / "f06_run.py").write_bytes(C.RUNNER.read_bytes())
    return d


def _mesh(case, bytes_per_cell):
    devs = [dk for dk in case["decks"] if dk["kind"] == "device"]
    fc = [F.memory_forecast(dk, bytes_per_cell) for dk in devs]
    return {
        "cells_max": max(dk["cells"] for dk in devs),
        "runs": len(case["decks"]),
        "forecast_peak_gib": round(max(f["total_gib"] for f in fc), 2),
        "bytes_per_cell": bytes_per_cell,
    }


def full_case(d, h_um):
    return C.device_case(d, 3, h_um, groups=F.geometry_groups())


def triage(out, grid_nm, image, bytes_per_cell):
    P = C.panel()
    h = grid_nm / 1000
    plan = [
        (label, f"{label}-{grid_nm}nm", full_case(d, h), "primary")
        for label, d in P.items()
    ]
    fine = FINER[grid_nm]
    for label in ("nominal-narrow", "nominal-wide"):
        plan.append(
            (
                label,
                f"{label}-{fine}nm",
                full_case(P[label], fine / 1000),
                "witness_studies",
            )
        )
    norm = F.deck(P["short-narrow"], 3, h, kind="normalization")
    plan.append(("control", f"straight-3d-{grid_nm}nm", C.case_doc([norm]), "controls"))
    first = next(iter(P))
    plan.append(
        (
            first,
            f"{first}-{grid_nm}nm-cold-repeat",
            full_case(P[first], h),
            "cold_repeat",
        )
    )
    entries = []
    for _label, name, case, reservation in plan:
        d = _write(out, "f06", name, case)
        entries.append({"family": "f06", "case": name, "reservation": reservation, "command": COMMAND,
                        "mesh": _mesh(case, bytes_per_cell) if reservation != "controls" else {"cells_max": norm["cells"], "runs": 1},
                        "files": _files(d)})  # fmt: skip
    counts = {}
    for e in entries:
        counts[e["reservation"]] = counts.get(e["reservation"], 0) + 1
    manifest = {
        "schema": "carbon.reference-triage.frozen-decks.v1",
        "ticket": "REFERENCE-PACKAGES-01",
        "authority": "OWNER-SOLVER-READINESS-SCIENCE-DELEGATION-01; F06-SCIENCE-VALUES-01 (DEVELOPMENT, no spend)",
        "image": image,
        "family": "f06",
        "grid_nm": grid_nm,
        "case_unit": "one design: 1 normalization + 5 geometry runs = 9 vectors x 5 wavelengths",
        "limits": {
            "cpus": 1,
            "memory_rule": "forecast_peak_gib x 1.25 (F06-SCIENCE-VALUES-01 headroom)",
        },
        "counts": counts,
        "cases": entries,
    }
    (Path(out) / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def draw_design(rng):
    """One draw from the registered design law (rejection on validity)."""
    lo_hi = F.GRAMMAR
    while True:
        d = F.design(
            rng.randint(*lo_hi["periods"]),
            round(rng.uniform(*lo_hi["pitch_nm"]), 1),
            round(rng.uniform(*lo_hi["duty"]), 4),
            round(rng.uniform(*lo_hi["etch_nm"]), 1),
            round(rng.uniform(*lo_hi["width_um"]), 2),
        )
        if F.valid(d):
            return d


def bank(seed_file, count, out, grid_nm, image, bytes_per_cell):
    out = Path(out).resolve()
    if REPO.resolve() in out.parents or out == REPO.resolve():
        raise SystemExit(
            "bank output is operator material; write it outside the repository"
        )
    seed = Path(seed_file).read_bytes()
    rng = random.Random(hashlib.sha256(b"f06-bank-v1|" + seed).digest())
    h = grid_nm / 1000
    entries = []
    for i in range(count):
        d = draw_design(rng)
        case = full_case(d, h)
        name = f"bank-{i:04d}"
        cd = _write(out, "f06", name, case)
        entries.append({"family": "f06", "case": name, "reservation": "primary", "command": COMMAND,
                        "mesh": _mesh(case, bytes_per_cell), "files": _files(cd)})  # fmt: skip
    manifest = {
        "schema": "carbon.reference-triage.frozen-decks.v1",
        "ticket": "REFERENCE-PACKAGES-01",
        "authority": "F06-SCIENCE-VALUES-01 bank freeze (operator material)",
        "image": image,
        "family": "f06",
        "grid_nm": grid_nm,
        "seed_sha256": hashlib.sha256(seed).hexdigest(),
        "counts": {"primary": count},
        "cases": entries,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"froze {count} bank cases; manifest sha256 "
          f"{hashlib.sha256((out / 'manifest.json').read_bytes()).hexdigest()}")  # fmt: skip


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("triage", "bank"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--grid-nm", type=int, default=30)
    ap.add_argument("--image", default=None)
    ap.add_argument("--bytes-per-cell", type=float, default=None)
    ap.add_argument("--seed-file")
    ap.add_argument("--count", type=int)
    a = ap.parse_args()
    image = a.image or "UNSET"
    if a.action == "triage":
        m = triage(a.out, a.grid_nm, image, a.bytes_per_cell)
        print(json.dumps(m["counts"]))
    else:
        if not a.seed_file or not a.count:
            raise SystemExit("--seed-file and --count are required for a bank")
        bank(a.seed_file, a.count, a.out, a.grid_nm, image, a.bytes_per_cell)


if __name__ == "__main__":
    main()
