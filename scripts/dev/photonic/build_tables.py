"""Build the photonic coupler's supermode tables: the reference's only solves.

    python scripts/dev/photonic/build_tables.py OUT.json --step-nm 10
        [--gaps 41] [--every 1] [--wavelengths 1.5,1.55] [--workers 2]

For every gap on the ladder and every wavelength, the even and odd TE-like
supermodes of the 500 x 220 nm pair (`carbon.photonic.coupler`), at a mesh
step of `--step-nm`. The ladder is geometric from the population's smallest
gap (150 nm) to the port gap (1,100 nm, where the bends end), so every gap a
case's profile passes through is inside it. `--every K` keeps every K-th
ladder gap, so a refinement table shares its gaps with the full one.

Each entry carries its own reference checks, and the table its verdict:
- both modes TE-like (`te_fraction` above 1/2) and mirror-symmetric
  (|parity| at least 1 - PARITY_TOL);
- each an eigenvector: relative residual of (P Q) v = -n^2 v at most
  RESIDUAL_TOL;
- n_ox < n_odd < n_even < n_si;
- the splitting falls monotonically with the gap at every wavelength, as
  evanescent coupling must.
A table that fails a check is written with `"status": "REFERENCE_INVALID"`
and its reasons; `carbon.photonic.reference` refuses it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA = "carbon.photonic.supermode-tables.v1"
#: Provisional DEVELOPMENT reference checks: a mirror-symmetric mode's
#: parity is +-1 to round-off; an ARPACK eigenvector's residual is far below.
PARITY_TOL = 1e-3
RESIDUAL_TOL = 1e-8
SOURCES = (
    "carbon/photonic/domain.py",
    "carbon/photonic/modes.py",
    "carbon/photonic/coupler.py",
    "scripts/dev/photonic/build_tables.py",
)


def source_digests():
    return {
        path: "sha256:" + hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in SOURCES
    }


def _entry(job):
    """Solve one (gap, wavelength) pair; runs in a worker process."""
    import numpy as np

    from carbon.photonic import coupler, domain, modes

    gap, wl, step = job
    start = time.monotonic()
    width = domain.WIDTH_UM
    eps, (nx, ny) = coupler.cross_section(width, width + gap, step)
    even, odd, _ = coupler.supermodes(width, width + gap, wl, step)
    p, q = modes.operators(eps, step, step, wl)
    result = {"gap_um": gap, "wavelength_um": wl, "shape": [nx, ny]}
    for name, mode in (("even", even), ("odd", odd)):
        v = np.concatenate([mode.ex.ravel(), mode.ey.ravel()])
        lam = -(mode.n_eff**2)
        residual = np.linalg.norm(p @ (q @ v) - lam * v) / (
            abs(lam) * np.linalg.norm(v)
        )
        result[name] = {
            "n_eff": mode.n_eff,
            "parity": coupler.parity(mode),
            "te_fraction": mode.te_fraction,
            "residual": float(residual),
        }
    result["wall_s"] = round(time.monotonic() - start, 2)
    return result


def _checks(table):
    from carbon.photonic import domain

    reasons = []
    for key, row in table["wavelengths"].items():
        for i, gap in enumerate(table["gaps_um"]):
            for name in ("even", "odd"):
                if row[f"te_{name}"][i] <= 0.5:
                    reasons.append(f"{key} um, gap {gap:.4f}: {name} not TE-like")
                if abs(row[f"parity_{name}"][i]) < 1 - PARITY_TOL:
                    reasons.append(
                        f"{key} um, gap {gap:.4f}: {name} parity "
                        f"{row[f'parity_{name}'][i]:.6f}"
                    )
                if row[f"residual_{name}"][i] > RESIDUAL_TOL:
                    reasons.append(
                        f"{key} um, gap {gap:.4f}: {name} residual "
                        f"{row[f'residual_{name}'][i]:.2e}"
                    )
            if not (domain.N_OX < row["n_odd"][i] < row["n_even"][i] < domain.N_SI):
                reasons.append(f"{key} um, gap {gap:.4f}: indices out of order")
        split = [e - o for e, o in zip(row["n_even"], row["n_odd"])]
        if any(b >= a for a, b in pairwise(split)):
            reasons.append(f"{key} um: splitting not monotone in the gap")
    return reasons


def main(argv=None):
    from carbon.photonic import domain

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--step-nm", type=float, required=True)
    parser.add_argument("--gaps", type=int, default=domain.GAP_LADDER_COUNT)
    parser.add_argument("--every", type=int, default=1)
    parser.add_argument("--wavelengths", default="all")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args(argv)
    gaps = domain.ladder(args.gaps)
    if (args.gaps - 1) % args.every:
        parser.error("--every must divide the ladder's intervals")
    gaps = gaps[:: args.every]
    wls = (
        list(domain.WAVELENGTHS_UM)
        if args.wavelengths == "all"
        else [float(w) for w in args.wavelengths.split(",")]
    )
    step = args.step_nm * 1e-3
    jobs = [(g, wl, step) for wl in wls for g in gaps]
    # The code that builds the table is pinned before it runs, and a source
    # edited during the build refuses the table rather than mislabelling it.
    sources = source_digests()
    start = time.monotonic()
    # One BLAS thread per worker: the solves parallelize across workers.
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        entries = list(pool.map(_entry, jobs))
    import numpy
    import scipy

    table = {
        "schema": SCHEMA,
        "contract": "carbon.photonic local-supermode model (CHALLENGE-PHOTONIC-01 D1)",
        "step_um": step,
        "width_um": domain.WIDTH_UM,
        "height_um": domain.HEIGHT_UM,
        "n_si": domain.N_SI,
        "n_ox": domain.N_OX,
        "ladder": {"count": args.gaps, "every": args.every},
        "gaps_um": gaps,
        "wavelengths": {},
    }
    for wl in wls:
        rows = [e for e in entries if e["wavelength_um"] == wl]
        table["wavelengths"][repr(wl)] = {
            f"{field}_{name}": [r[name][key] for r in rows]
            for name in ("even", "odd")
            for field, key in (
                ("n", "n_eff"),
                ("parity", "parity"),
                ("te", "te_fraction"),
                ("residual", "residual"),
            )
        }
    reasons = _checks(table)
    if source_digests() != sources:
        reasons.append("a source changed during the build")
    table["status"] = "REFERENCE_INVALID" if reasons else "OK"
    table["reasons"] = reasons
    table["checks"] = {"parity_tol": PARITY_TOL, "residual_tol": RESIDUAL_TOL}
    table["provenance"] = {
        "sources": sources,
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "solve_wall_s": round(sum(e["wall_s"] for e in entries), 1),
        "wall_s": round(time.monotonic() - start, 1),
        "shapes": sorted({tuple(e["shape"]) for e in entries})[-1:],
    }
    args.out.write_text(json.dumps(table, indent=1) + "\n")
    print(
        json.dumps(
            {
                "status": table["status"],
                "reasons": reasons[:10],
                "wall_s": table["provenance"]["wall_s"],
            }
        )
    )
    return 0 if not reasons else 1


if __name__ == "__main__":
    sys.exit(main())
