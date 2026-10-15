"""Register and freeze an f08 reference bank (F08-SCIENCE-VALUES-01, DEVELOPMENT).

    python3 f08_bank.py register --out REGISTRATION.json
    python3 f08_bank.py freeze --registration REGISTRATION.json --seed SEED \
        --out DIR [--count 256] [--h 3] [--jobs 4] [--public-seed]

`register` seals a `carbon.f08-preparation.v1` registration from the current
sources: the Q1 lattice (length 180:5:260, width 60:5:100, thickness 4:0.5:8,
rib height 8:1:16, rib thickness 3:0.5:5, relief 20:5:60 mm), P = Q = w = 1/3
over the three damping ratios (all three are solved for every geometry), and
the image, mesh image, deck, proof, material and observer pins.

`freeze` draws `count` distinct valid lattice geometries with
`structures_readiness.actions` (uniform, Q1/Q2), writes one deck per geometry
(static, 48-mode eigen and the three damping sweeps in one ccx launch, at the
V9 bank mesh) and a `carbon.reference-triage.frozen-decks.v1` manifest the
triage runner executes unchanged (`reservation: bank`). The seed is recorded
only with --public-seed; a hidden bank's seed is owner-held and never written
here. Nothing is solved by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from carbon.challenge_pipeline import structures_readiness as s

import f08_deck as deck
import f08_freeze as freeze_mod

STEPS = (5, 5, 0.5, 1, 0.5, 5)  # Q1 lattice steps, packet field order
MODES = 48


def _sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def registration(scope="PUBLIC_DEVELOPMENT"):
    return s.seal(
        {
            "schema": s.SCHEMA,
            "family": s.FAMILY,
            "scope": scope,
            "authority": "F08-SCIENCE-VALUES-01 under OWNER-SOLVER-READINESS-SCIENCE-DELEGATION-01; DEVELOPMENT only",
            "grammar": {
                field: {"min": lo, "max": hi, "step": step}
                for field, (lo, hi), step in zip(s.FIELDS, s.BOUNDS, STEPS)
            },
            "P": {str(z): 1 / 3 for z in s.DAMPING},
            "Q": {str(z): 1 / 3 for z in s.DAMPING},
            "w": {str(z): 1 / 3 for z in s.DAMPING},
            "pins": {
                "image": s.IMAGE,
                "mesh_image": s.MESH_IMAGE,
                "deck": _sha(HERE / "f08_deck.py"),
                "proof": _sha(HERE / "f08_proof.py"),
                "material": s.tasks.digest(s.MATERIAL),
                "observer": _sha(HERE / "f08_freeze.py"),
            },
        }
    )


def freeze(reg, seed, out, count=256, h_mm=3.0, jobs=1, public_seed=False):
    s.validate(reg)
    if reg["pins"] != registration(reg["scope"])["pins"]:
        raise SystemExit(
            "current sources differ from the registration pins; re-register"
        )
    rows = s.actions(reg, seed=seed, count=count)
    out = Path(out)

    def one(item):
        i, row = item
        name = f"bank-{i:04d}"
        d = out / "f08" / name
        size = deck.write_case(row, d, h_mm, MODES)
        return {"family": "f08", "case": name, "reservation": "bank", "command": deck.COMMAND,
                "mesh": size, **deck.estimate(size["nodes"]), "action": row, "action_digest": s.tasks.digest(row),
                "files": freeze_mod._digest(d)}  # fmt: skip

    with ThreadPoolExecutor(max(1, jobs)) as pool:
        cases = list(pool.map(one, enumerate(rows)))
    manifest = {
        "schema": "carbon.reference-triage.frozen-decks.v1",
        "ticket": "F08-SCIENCE-VALUES-01 bank freeze",
        "authority": "DEVELOPMENT bank; no LIVE, reward or spend",
        "image": reg["pins"]["image"],
        "mesh_image_f08": reg["pins"]["mesh_image"],
        "bank": {
            "registration_digest": reg["registration_digest"],
            "scope": reg["scope"],
            "count": count,
            "h_mm": h_mm,
            "modes": MODES,
            "seed": seed if public_seed else "WITHHELD",
        },
        "cases": cases,
        "counts": {"bank": len(cases)},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def main(argv=None):
    p = argparse.ArgumentParser(prog="f08_bank")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register")
    r.add_argument("--out", type=Path, required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--registration", type=Path, required=True)
    f.add_argument("--seed", type=int, required=True)
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--count", type=int, default=256)
    f.add_argument("--h", type=float, default=3.0)
    f.add_argument("--jobs", type=int, default=1)
    f.add_argument("--public-seed", action="store_true")
    args = p.parse_args(argv)
    if args.cmd == "register":
        args.out.write_text(json.dumps(registration(), indent=1, sort_keys=True) + "\n")
        print(json.loads(args.out.read_text())["registration_digest"])
    else:
        reg = json.loads(args.registration.read_text())
        doc = freeze(
            reg, args.seed, args.out, args.count, args.h, args.jobs, args.public_seed
        )
        print(
            json.dumps(
                {"cases": len(doc["cases"]), "registration": reg["registration_digest"]}
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
