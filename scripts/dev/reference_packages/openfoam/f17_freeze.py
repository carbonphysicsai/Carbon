"""Freeze f17 decks in the runner schema `carbon.reference-triage.frozen-decks.v1`.

    python3 f17_freeze.py triage --out DIR [--estimates SIZING.json]
    python3 f17_freeze.py bank --seed-file SEED --out DIR [--count 45]

triage (#787 public panel, `reference-route-panels.json` f17):
    primary (8)          every public geometry, h = 10 um, all nine
                         conditions (3 flows + 9 scalars); the deep-dense and
                         deep-sparse witnesses add the D = 0 diagnostic at Q = 5
    witness_studies (2)  deep-dense and deep-sparse at h = 7.071 um, same panel
    controls (2)         smooth duct h = 10 (Poiseuille, split/uniform/zero-D
                         tracers) and h = 7.071 (Poiseuille order)
    cold_repeat (1)      deep-dense fresh flow + scalar pair (reuse parity)

bank: the registered design bank (F7) drawn from the packet action law with the
OPERATOR's producer seed (read from a file that is never written here); every
design gets the primary nine-condition panel.

One case = one container launch: `bash Allrun` meshes in the case
(snappyHexMesh is deterministic: the proof records equal mesh hashes from two
independent generations), then flows, then scalars on the retained phi.
Every input file is hashed into the manifest; nothing else is generated on the
run host.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f17_deck as deck
import f17_geometry as geo

PANELS = (
    HERE.parents[3]
    / "docs/development/challenge_pipeline/round1/reference-route-panels.json"
)
LOCK = json.loads((HERE / "image.lock.json").read_text())
H_PRIMARY, H_REFINED = 10.0, 10 / 2**0.5
WITNESSES = ("deep-dense", "deep-sparse")
COMMAND = "bash Allrun > Allrun.log 2>&1"
NINE = [(q, d, deck.PRIMARY_SCHEME) for q in deck.FLOWS for d in deck.DIFFUSIVITIES]
ZERO_D = [(5, 0.0, deck.PRIMARY_SCHEME)]


def _files(case_dir):
    return {
        str(p.relative_to(case_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path(case_dir).rglob("*"))
        if p.is_file()
    }


def _design(params):
    d, p, r = params
    return {"depth_um": float(d), "pitch_um": float(p), "reversal": int(r)}


def _entry(out, name, reservation, design, h, specs, flows=deck.FLOWS, label=None,
           estimates=None):  # fmt: skip
    case = Path(out) / "f17" / name
    info = deck.write_case(
        case, design, h, flows=flows, scalar_specs=specs, label=label
    )
    kind = f"{reservation}:h{h:.3f}:{len(flows)}f{len(specs)}s"
    entry = {
        "family": "f17",
        "case": name,
        "reservation": reservation,
        "command": COMMAND,
        "files": _files(case),
        "mesh": {
            "h_um": round(h, 6),
            "grooves": None if design is None else info["geometry"]["grooves"],
            "analytic_volume_m3": info["analytic_volume_m3"],
        },
        "solver_starts": len(flows) + len(specs),
        "kind": kind,
    }
    est = (estimates or {}).get(_estimate_key(reservation, h, design))
    if est:
        entry.update(
            {
                k: est[k]
                for k in (
                    "estimate_cpu_s",
                    "estimate_wall_s",
                    "estimate_mem_mib",
                    "estimate_basis",
                )
            }
        )
    return entry


def _estimate_key(reservation, h, design):
    rung = "refined" if abs(h - H_REFINED) < 1e-6 else "primary"
    return "control" if design is None else f"{rung}-panel"


def triage(out, estimates=None):
    out = Path(out)
    est = json.loads(Path(estimates).read_text())["per_case_kind"] if estimates else {}
    labels = json.loads(PANELS.read_text())["families"]["f17"]["public_cases"]
    cases = []
    for item in labels:
        lab, params = item["label"], item["parameters"]
        specs = NINE + (ZERO_D if lab in WITNESSES else [])
        cases.append(
            _entry(
                out,
                f"{lab}-primary",
                "primary",
                _design(params),
                H_PRIMARY,
                specs,
                label=lab,
                estimates=est,
            )
        )
    for item in labels:
        if item["label"] in WITNESSES:
            cases.append(
                _entry(
                    out,
                    f"{item['label']}-h7.071",
                    "witness_studies",
                    _design(item["parameters"]),
                    H_REFINED,
                    NINE + ZERO_D,
                    label=item["label"],
                    estimates=est,
                )
            )
    cases.append(
        _entry(
            out,
            "smooth-controls-h10",
            "controls",
            None,
            H_PRIMARY,
            [
                (1, 2e-10, deck.PRIMARY_SCHEME),
                (5, 0.5e-10, deck.PRIMARY_SCHEME),
                (5, 0.0, deck.PRIMARY_SCHEME),
                (5, 1e-10, deck.PRIMARY_SCHEME, (1, 1)),
            ],
            flows=(1, 5),
            label="smooth-controls",
            estimates=est,
        )
    )
    cases.append(
        _entry(
            out,
            "smooth-poiseuille-h7.071",
            "controls",
            None,
            H_REFINED,
            [],
            flows=(5,),
            label="smooth-poiseuille",
            estimates=est,
        )
    )
    dd = next(i for i in labels if i["label"] == "deep-dense")
    cases.append(
        _entry(
            out,
            "deep-dense-fresh-pair",
            "cold_repeat",
            _design(dd["parameters"]),
            H_PRIMARY,
            [(5, 0.5e-10, deck.PRIMARY_SCHEME)],
            flows=(5,),
            label="deep-dense",
            estimates=est,
        )
    )
    counts = {}
    for c in cases:
        counts[c["reservation"]] = counts.get(c["reservation"], 0) + 1
    manifest = {
        "schema": "carbon.reference-triage.frozen-decks.v1",
        "ticket": "REFERENCE-PACKAGES-01",
        "authority": "#787 f17 public triage panel; F17-SCIENCE-VALUES-01; no spend",
        "image": LOCK["manifest_digest"],
        "image_run_ref": LOCK["run_reference"],
        "image_note": "the command is relative to the case dir (bulk_run sets -w /case "
        "in Docker and the case dir as cwd natively; pod_phase refuses /case paths); "
        "Allrun cds to its own dir and sources etc/bashrc when simpleFoam is not on PATH",
        "case_limits_recommended": {
            "cpus": 1,
            "memory_gib_primary": 2,
            "memory_gib_refined": 4,
            "pids": 16,
        },
        "counts": counts,
        "solver_starts": sum(c["solver_starts"] for c in cases),
        "cases": cases,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def bank(seed_file, out, count=45, estimates=None):
    """Draw the registered design bank (F7) from the operator's seed."""
    import numpy as np

    seed = int(Path(seed_file).read_text().strip(), 0)
    rng = np.random.Generator(np.random.PCG64(seed))
    est = json.loads(Path(estimates).read_text())["per_case_kind"] if estimates else {}
    cases, refused = [], 0
    while len(cases) < count:
        params = (
            round(float(rng.uniform(20, 40)), 2),
            round(float(rng.uniform(100, 250)), 2),
            int(rng.integers(6, 11)),
        )
        design = _design(params)
        try:
            geo.check(design)
        except ValueError:
            refused += 1  # refuse, never clip
            continue
        name = f"bank-{len(cases):03d}"
        cases.append(
            _entry(
                out, name, "primary", design, H_PRIMARY, NINE, label=name, estimates=est
            )
        )
    manifest = {
        "schema": "carbon.reference-triage.frozen-decks.v1",
        "ticket": "REFERENCE-PACKAGES-01",
        "authority": "F17-SCIENCE-VALUES-01 F7 bank tranche 1; operator seed not recorded",
        "image": LOCK["manifest_digest"],
        "image_run_ref": LOCK["run_reference"],
        "seed_sha256": hashlib.sha256(str(seed).encode()).hexdigest(),
        "refused_draws": refused,
        "counts": {"primary": len(cases)},
        "solver_starts": sum(c["solver_starts"] for c in cases),
        "cases": cases,
    }
    (Path(out) / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("triage")
    t.add_argument("--out", type=Path, required=True)
    t.add_argument("--estimates", type=Path)
    b = sub.add_parser("bank")
    b.add_argument("--seed-file", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--count", type=int, default=45)
    b.add_argument("--estimates", type=Path)
    args = parser.parse_args(argv)
    if args.cmd == "triage":
        m = triage(args.out, args.estimates)
    else:
        m = bank(args.seed_file, args.out, args.count, args.estimates)
    print(json.dumps({"counts": m["counts"], "solver_starts": m["solver_starts"]}))


if __name__ == "__main__":
    main()
