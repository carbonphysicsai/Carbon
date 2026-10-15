"""Run f13's remaining verification checks on one single-tenant host (a pod).

    python -m scripts.dev.reference_packages.elmer.f13_pod_checks all --work DIR --out PROOF.json
        [--jobs N] [--budget-s S] [--groups mms,controls,curves,lead,mesh4,coax4]
    python -m scripts.dev.reference_packages.elmer.f13_pod_checks mm --out MM.json

`all` writes every case directory f13_assemble reads (F13-SCIENCE-VALUES-01
B1-B3, C1-C4, D1-D5), solves them N at a time (longest first, one serial
ElmerSolver per vCPU), stops admitting new cases after --budget-s, then
assembles PROOF.json from whatever finished (missing runs stay NOT_RUN /
DEFERRED, never PASS) and prints one JSON line per registered check. The
mode-matching control (`mm`, numpy/scipy, ~20 CPU-min) runs as one pool task
unless a committed `f13-mode-matching.json` exists (then it is copied).

`coax4` (the three panel coaxials on the 4 mm mesh, 21 points) is a B3
DIAGNOSTIC, not a registered check: the 8 mm small-coaxial curve misses the
B3 mean band (0.347 > 0.25 dB) and this measures how the error falls with h.
DEVELOPMENT engineering only: no adequacy, qualification or LIVE claim.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.reference_packages.elmer import f13_assemble as assemble
from scripts.dev.reference_packages.elmer import f13_deck as deck
from scripts.dev.reference_packages.elmer import f13_proof as proof
from scripts.dev.reference_packages.elmer.f13_triage_freeze import CONTROLS

MM_EVIDENCE = (
    ROOT / "docs/development/evidence/reference-packages-01/f13-mode-matching.json"
)
OFFSET = assemble.OFFSET
PANEL_COAXIAL = ("small-coaxial", "short-neck-wide", "long-neck-small")
GROUPS = ("mms", "controls", "curves", "lead", "mesh4", "coax4")


def _labels():
    panel = json.loads(deck.PANELS.read_text())["families"]["f13"]
    return [c["label"] for c in panel["public_cases"]]


def plan():
    """[(group, relative dir, geometry, write_case kwargs, weight)]; weight is
    a relative cost guess used only to start the longest cases first."""
    nominal = deck.panel_case("nominal")
    out = [
        ("curves", f"v2/{lb}-primary", deck.panel_case(lb), {}, 201) for lb in _labels()
    ]
    out += [("curves", "v2/clearance-boundary-freq5hz", deck.panel_case("clearance-boundary"),
             {"step_hz": 5.0}, 401)]  # fmt: skip
    out += [("controls", f"v2/{n}", g, {}, 120) for n, g in CONTROLS.items()]
    out += [("controls", f"v2/nominal-single-{f:g}", nominal, {"freqs": [f]}, 1)
            for f in (500.0, 1500.0, 2500.0)]  # fmt: skip
    out += [("controls", f"solvers/nominal-{s}", nominal,
             {"freqs": [500.0, 1500.0, 2500.0], "solver": s}, 12) for s in ("direct", "iterative")]  # fmt: skip
    out += [("lead", f"lead100/{lb}", deck.panel_case(lb), {"step_hz": 50.0, "stub_mm": 100.0}, 60)
            for lb in OFFSET]  # fmt: skip
    out += [("mesh4", f"mesh4/{lb}", deck.panel_case(lb), {"h_mm": 4.0, "step_hz": 100.0}, 21 * 9)
            for lb in OFFSET]  # fmt: skip
    out += [("coax4", f"coax4/{lb}", deck.panel_case(lb), {"h_mm": 4.0, "step_hz": 100.0}, 21 * 7)
            for lb in PANEL_COAXIAL]  # fmt: skip
    return out


def mode_matching(out, n_low=20, n_high=40):
    """mm.json for every coaxial control/panel geometry: N vs 2N modes."""
    from scripts.dev.reference_packages.elmer import (
        f13_mode_matching as mm,  # numpy/scipy
    )

    geos = {"control-chamber": CONTROLS["control-chamber"]}
    geos.update({lb: deck.panel_case(lb) for lb in PANEL_COAXIAL})
    freqs = deck.frequencies(10.0)
    doc = {}
    for name, geo in geos.items():
        lo, hi = mm.curve(geo, freqs, n_low), mm.curve(geo, freqs, n_high)
        res = [abs(a["tl_db"] - b["tl_db"]) for a, b in zip(lo, hi)
               if a["tl_db"] <= proof.RESOLVED_TL_DB and b["tl_db"] <= proof.RESOLVED_TL_DB]  # fmt: skip
        doc[name] = {
            f"n{n_low}": lo, f"n{n_high}": hi,
            "conv_max_dtl_db_resolved": max(res, default=0.0),
            "conv_max_dpt_w": max(abs(a["transmitted_w"] - b["transmitted_w"]) for a, b in zip(lo, hi)),
            "max_residual": max(abs(r["signed_plane_residual"]) for r in hi),
        }  # fmt: skip
    Path(out).write_text(json.dumps(doc) + "\n")
    return doc


def run_all(work, out, jobs, budget_s, groups, image, recompute_mm=False):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    tasks = []
    if recompute_mm or not MM_EVIDENCE.exists():
        tasks.append((5_000, "mm"))  # ~20 CPU-min, runs beside the solves
    else:
        shutil.copyfile(MM_EVIDENCE, work / "mm.json")
    for group, rel, geo, kwargs, weight in plan():
        if group in groups:
            deck.write_case(geo, work / rel, **kwargs)
            tasks.append((weight, rel))
    if "mms" in groups:
        tasks.append((10_000, "mms"))  # the h 0.025 rung is the longest single task
    tasks.sort(reverse=True)

    def one(rel):
        if time.monotonic() - start > budget_s:
            return rel, "NOT_ADMITTED"
        if rel == "mm":
            mode_matching(work / "mm.json")
            return rel, "COMPLETED"
        if rel == "mms":
            from scripts.dev.reference_packages.elmer import f13_mms as mms  # numpy

            doc = mms.run(
                work / "mms", work / "mms.json", image, lock=None, iterative_below=0.05
            )
            return rel, "PASS" if doc["pass"] else "FAIL"
        cost = proof.run(
            work / rel, image, cpus=1, memory="16g", timeout=7200, lock=None
        )
        return rel, cost.get("solve", {}).get("outcome", "MESH_FAILED")

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for rel, outcome in pool.map(one, [r for _, r in tasks]):
            print(json.dumps({"case": rel, "outcome": outcome}), flush=True)
    doc = assemble.assemble(work, out)
    for name, status in doc["checks"].items():
        print(json.dumps({"check": name, "status": status}), flush=True)
    return doc


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f13_pod_checks")
    parser.add_argument("command", choices=("all", "mm"))
    parser.add_argument("--work", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--budget-s", type=float, default=7200.0)
    parser.add_argument("--groups", default=",".join(GROUPS))
    parser.add_argument("--image", default=proof.IMAGE)
    parser.add_argument("--recompute-mm", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "mm":
        mode_matching(args.out)
        return 0
    groups = set(args.groups.split(","))
    if not args.work or not groups <= set(GROUPS):
        parser.error(f"--work is required and --groups must be a subset of {GROUPS}")
    run_all(
        args.work,
        args.out,
        args.jobs,
        args.budget_s,
        groups,
        args.image,
        args.recompute_mm,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
