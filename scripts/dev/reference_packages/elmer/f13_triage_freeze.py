"""Freeze f13's v2 triage decks (F13-SCIENCE-VALUES-01; REFERENCE-PACKAGES-01).

    python -m scripts.dev.reference_packages.elmer.f13_triage_freeze --out DIR [--proof EVIDENCE.json]

Writes every f13 v2 deck of #787's public panel into DIR/f13/<case>/, meshes
each geometry with the pinned Gmsh image, and writes DIR/manifest.json in the
shared `carbon.reference-triage.frozen-decks.v1` schema (cases[{family, case,
reservation, command, files{relpath: sha256}, mesh}]), bound to the f13 Elmer
pin `silencer_readiness.IMAGE`. The v1 freeze (`triage_freeze.py`, 10 mm
stubs, image 8bcd864d) stays as the historical record and is not rewritten.

v2 decks: 60 mm numerical leads de-embedded to the 10 mm panel planes, 8 mm
second-order mesh, BiCGStabl(4)+ILU2 at 1e-10, one ElmerSolver process per
curve scanning 500-2500 Hz at 10 Hz. Reservations (#787, 16 of 20 launches):
8 primary sweeps; 2 fine sweeps (clearance-boundary at 5 Hz, 401 points;
large-offset on the 4 mm mesh at 100 Hz, 21 points); straight-duct and
coaxial-chamber controls; a cold repeat of the first primary; three
separate single-frequency solves of the nominal primary (500/1500/2500 Hz).

`dispatchable` is true only when the proof file passed with --proof reports
every registered check PASS for this deck and image; otherwise false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.challenge_pipeline import silencer_readiness as sr
from scripts.dev.reference_packages.elmer import f13_deck as f13
from scripts.dev.reference_packages.elmer import f13_proof

SOLVE = (
    "export OPENBLAS_NUM_THREADS=1; "
    "ElmerGrid 14 2 mesh.msh -autoclean -out mesh > grid.log 2>&1 && "
    "ElmerSolver case.sif > solver.log 2>&1"
)
CONTROLS = {
    "control-duct": {"radius1_mm": 25.0, "length1_mm": 100.0, "neck_length_mm": 0,
                     "radius2_mm": 0, "length2_mm": 0, "neck_offset_mm": 0},
    "control-chamber": {"radius1_mm": 62.5, "length1_mm": 75.0, "neck_length_mm": 0,
                        "radius2_mm": 0, "length2_mm": 0, "neck_offset_mm": 0},
}  # fmt: skip


def plan():
    """[(case name, geometry, reservation, write_case kwargs)] in run order."""
    panel = json.loads(f13.PANELS.read_text())["families"]["f13"]
    labels = [c["label"] for c in panel["public_cases"]]
    out = [(f"{lb}-primary", f13.panel_case(lb), "primary_sweeps", {}) for lb in labels]
    out += [(name, geo, "controls", {}) for name, geo in CONTROLS.items()]
    out += [
        (f"nominal-single-{f:g}", f13.panel_case("nominal"), "separate_frequency_smoke",
         {"freqs": [f]})
        for f in (500.0, 1500.0, 2500.0)
    ]  # fmt: skip
    out += [
        ("clearance-boundary-freq5hz", f13.panel_case("clearance-boundary"),
         "fine_sweeps", {"step_hz": 5.0}),
        ("large-offset-mesh4mm", f13.panel_case("large-offset"), "fine_sweeps",
         {"h_mm": 4.0, "step_hz": 100.0}),
        (f"{labels[0]}-cold-repeat", f13.panel_case(labels[0]), "cold_repeat", {}),
    ]  # fmt: skip
    return out


def _digest(case_dir):
    files = sorted(p for p in Path(case_dir).rglob("*") if p.is_file())
    return {
        str(p.relative_to(case_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
    }


def _mesh(case_dir):
    cmd = ["docker", "run", "--rm", "--network", "none", "--cpus", "1", "--memory", "3g",
           "--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp",
           "-v", f"{Path(case_dir).resolve()}:/w", "-w", "/w", f13.MESH_IMAGE,
           "python3", "make_mesh.py"]  # fmt: skip
    subprocess.run(cmd, check=True, capture_output=True)


def _dispatchable(proof):
    if proof is None:
        return False, "no proof file supplied"
    doc = json.loads(Path(proof).read_text())
    if doc.get("image") != sr.IMAGE or doc.get("deck_sha256") != sr.DECK_SHA:
        return False, "proof binds a different image or deck"
    failed = sorted(k for k, v in doc.get("checks", {}).items() if v != "PASS")
    return (not failed and bool(doc.get("checks"))), (
        "all registered checks PASS" if not failed else f"not PASS: {failed}"
    )


def freeze(out, proof=None):
    out = Path(out)
    entries = []
    for name, geometry, reservation, kwargs in plan():
        d = out / "f13" / name
        f13.write_case(geometry, d, **kwargs)
        _mesh(d)
        groups = json.loads((d / "groups.json").read_text())
        entries.append({"family": "f13", "case": name, "reservation": reservation,
                        "command": SOLVE, "files": _digest(d),
                        "mesh": {"nodes": groups["nodes"], "h_mm": kwargs.get("h_mm", 8.0)},
                        "frequency_systems": len(json.loads((d / "deck.json").read_text())["frequencies_hz"])})  # fmt: skip
    for e in entries:
        e.update(f13_proof.estimate(e["mesh"]["nodes"], e["frequency_systems"]))
    ok, why = _dispatchable(proof)
    manifest = {
        "schema": "carbon.reference-triage.frozen-decks.v1",
        "ticket": "REFERENCE-PACKAGES-01",
        "decision": sr.VALUES_DECISION,
        "grant": "OWNER-REFERENCE-ROUTE-TRIAGE-GRANT-01",
        "image": sr.IMAGE,
        "mesh_image_f13": f13.MESH_IMAGE,
        "deck_version": f13.DECK_VERSION,
        "deck_sha256": sr.DECK_SHA,
        "observer": sr.PINS["observer"],
        "cases": entries,
        "counts": {"f13": {r: sum(1 for e in entries if e["reservation"] == r)
                           for r in sorted({e["reservation"] for e in entries})}},
        "frequency_systems": sum(e["frequency_systems"] for e in entries),
        "dispatchable": ok,
        "dispatchable_basis": why,
        "scope": "PUBLIC_DEVELOPMENT recipe panel; no hidden material",
    }  # fmt: skip
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f13_triage_freeze")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--proof", type=Path)
    args = parser.parse_args(argv)
    m = freeze(args.out, args.proof)
    print(json.dumps({"counts": m["counts"], "dispatchable": m["dispatchable"],
                      "basis": m["dispatchable_basis"]}, indent=1))  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
