"""The F08 2.0 smoke: ONE case at a corner of the 1.7 TRAIN box, meshed at the base size, to measure memory and time
before any scale-out (check-before-spend step 3). This module prepares the case and reads the result; it never starts a
container itself, so a rented pod or the Test Lead's box runs the two commands it prints.

    python3 f08_v2_smoke.py prepare OUTDIR --corner stiffest|heaviest [--h 1.7] [--fillet-h 0.5]
    # on the box, in OUTDIR:  python3 make_mesh.py   (the pinned Gmsh image), then
    #                         python3 -c "import f08_deck_v2 as d; ..."  (see `prepare`'s printed `then`), then ccx
    python3 f08_v2_smoke.py report OUTDIR

The new numeric inputs' ranges are registered (OWNER-F08-V2-VALUES-01) and the smoke's stand-ins lie inside them; the
alloys' properties are still HUMAN_INPUT, so the smoke uses a SYNTHETIC alloy and every output is labelled
``tables: TEST_ONLY``. The 1.7 TRAIN box
(length 180-260, width 60-100, thickness 4-8, rib height 8-16, rib thickness 3-5, relief 20-60 mm) is the signed 1.7
region for the old six inputs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f08_deck_v2 as v2

BOX = {
    "length_mm": (180.0, 260.0),
    "width_mm": (60.0, 100.0),
    "thickness_mm": (4.0, 8.0),
    "rib_height_mm": (8.0, 16.0),
    "rib_thickness_mm": (3.0, 5.0),
    "relief_length_mm": (20.0, 60.0),
}
#: Synthetic stand-ins (never registered): the new inputs and the alloy of the smoke.
STAND_IN = {
    "fillet_radius_mm": 1.5,
    "load_angle_deg": 0.0,
    "load_position_in_gap": 0.0,
    "damping_ratio": 0.01,
    "alloy": "SMOKE_STAND_IN",
}
STAND_IN_TABLE = {
    "SMOKE_STAND_IN": {
        "E_mpa": 70000.0,
        "nu": 0.33,
        "rho_t_per_mm3": 2.7e-9,
        "yield_mpa": 100.0,
    }
}
#: stiffest: shortest, thickest, deepest ribs, widest, shortest relief (most stiffness, highest modes in the band);
#: heaviest: the largest volume (the most nodes, so the most memory).
CORNERS = {
    "stiffest": {
        "length_mm": 0,
        "width_mm": 1,
        "thickness_mm": 1,
        "rib_height_mm": 1,
        "rib_thickness_mm": 1,
        "relief_length_mm": 0,
    },
    "heaviest": {
        "length_mm": 1,
        "width_mm": 1,
        "thickness_mm": 1,
        "rib_height_mm": 1,
        "rib_thickness_mm": 1,
        "relief_length_mm": 0,
    },
}


def corner_case(corner):
    if corner not in CORNERS:
        raise v2.Refused("unknown_corner")
    geometry = {name: BOX[name][pick] for name, pick in CORNERS[corner].items()}
    return {**geometry, **STAND_IN}


def prepare(out, corner, *, h_mm=1.7, fillet_h_mm=0.5):
    """Write ``make_mesh.py`` and ``smoke.json`` (the case, the sizes, the label). Returns what the box should run next."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    case = corner_case(corner)
    v2.validate_case(case, test_mode=True)
    script = v2.gmsh_script_v2(case, h_mm, fillet_h_mm)
    v2.script_compiles(script)
    (out / "make_mesh.py").write_text(script)
    plan = {
        "schema": "carbon.f08.v2-smoke.v1",
        "corner": corner,
        "case": case,
        "h_mm": h_mm,
        "fillet_h_mm": fillet_h_mm,
        "tables": "TEST_ONLY",
        "table": STAND_IN_TABLE,
        "then": [
            "python3 make_mesh.py   # in the pinned Gmsh image (f08_deck.MESH_IMAGE)",
            (
                "python3 -c \"import json, f08_deck_v2 as d; p = json.load(open('smoke.json')); "
                "m = d.material('SMOKE_STAND_IN', table=p['table'], test_mode=True); "
                "open('case.inp', 'w').write(d.deck_text(p['case'], json.load(open('mesh.json')), m))\""
            ),
            "the f08_deck.COMMAND line (ccx plus the cgroup counters) in the pinned CalculiX image",
        ],
    }
    (out / "smoke.json").write_text(json.dumps(plan, indent=1, sort_keys=True) + "\n")
    return plan


def parse_cgroup(text):
    """CPU seconds and peak memory (MiB) from the cgroup counters `f08_deck.COMMAND` leaves in ``cgroup.txt``."""
    cpu = re.search(r"usage_usec\s+(\d+)", text)
    ns = re.search(r"cpuacct\.usage:(\d+)", text)
    memory = re.search(r"memory\.peak:(\d+)", text) or re.search(
        r"max_usage_in_bytes:(\d+)", text
    )
    return {
        "cpu_s": (
            int(cpu.group(1)) / 1e6 if cpu else (int(ns.group(1)) / 1e9 if ns else None)
        ),
        "peak_mem_mib": int(memory.group(1)) / 2**20 if memory else None,
    }


def report(out):
    """What the smoke measured: mesh size, fillet elements, CPU seconds, peak memory, and the dynamic fillet value."""
    out = Path(out)
    plan = json.loads((out / "smoke.json").read_text())
    mesh = json.loads((out / "mesh.json").read_text())
    measured = parse_cgroup((out / "cgroup.txt").read_text())
    result = {
        "schema": "carbon.f08.v2-smoke-report.v1",
        "corner": plan["corner"],
        "h_mm": plan["h_mm"],
        "fillet_h_mm": plan["fillet_h_mm"],
        "nodes": mesh["nodes"],
        "elements": mesh["elements"],
        "fillet_elements": mesh["fillet_elements"],
        **measured,
        "tables": "TEST_ONLY",
    }
    (out / "smoke-report.json").write_text(
        json.dumps(result, indent=1, sort_keys=True) + "\n"
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("out")
    p.add_argument("--corner", required=True, choices=sorted(CORNERS))
    p.add_argument("--h", type=float, default=1.7)
    p.add_argument("--fillet-h", type=float, default=0.5)
    r = sub.add_parser("report")
    r.add_argument("out")
    args = parser.parse_args(argv)
    if args.cmd == "prepare":
        print(
            json.dumps(
                prepare(args.out, args.corner, h_mm=args.h, fillet_h_mm=args.fillet_h),
                indent=1,
            )
        )
    else:
        print(json.dumps(report(args.out), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
