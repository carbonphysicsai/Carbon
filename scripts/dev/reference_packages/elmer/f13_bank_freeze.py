"""f13 design-bank freeze path (F13-SCIENCE-VALUES-01 F5-F8).

    # tranche 1: 64 designs from the packet geometry law
    python -m scripts.dev.reference_packages.elmer.f13_bank_freeze tranche --seed-file SEED --count 64 --out DIR
    # refined rungs for every design whose 8 mm p10 is within 0.5 dB of a floor in [5, 7] dB
    python -m scripts.dev.reference_packages.elmer.f13_bank_freeze refine --bank DIR --results RESULTS.json
    # tranche 2: up to 32 frontier designs around near-floor designs until T2(a) holds
    python -m scripts.dev.reference_packages.elmer.f13_bank_freeze frontier --bank DIR --results RESULTS.json --seed-file SEED2 --count 32

The producer seed is operator material: it is read from a file the operator
holds and is never written to the manifest (only its sha256 commitment).
A public dry run uses `--public-seed N` and is labelled PUBLIC_DEVELOPMENT;
its designs are public and can never become hidden bank cases. Every deck
is the accepted f13 v2 deck (60 mm leads, 8 mm P2 mesh, 201 points,
BiCGStabl+ILU2), bound to `silencer_readiness.IMAGE`; the manifest uses the
shared `carbon.reference-triage.frozen-decks.v1` case schema so the bulk
runner can launch it. Designs identical to a public panel geometry are
refused (no public/hidden aliasing).

RESULTS.json is {case: {"p10_tl_db": float, ...}} from the observer on the
solved tranche. Nothing here launches a solver.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.challenge_pipeline import silencer_readiness as sr
from scripts.dev.reference_packages.elmer import f13_deck as f13
from scripts.dev.reference_packages.elmer import f13_proof
from scripts.dev.reference_packages.elmer import f13_triage_freeze as tf

FLOORS = (5.0, 7.0)  # P support ends (F1)
NEAR_DB = 0.5  # F5/F8: two p10 bands
T2A_EACH_SIDE = 5  # F8
M_MAX = 96  # F7


def _seed(args):
    if args.public_seed is not None:
        return args.public_seed, "PUBLIC_DEVELOPMENT", None
    raw = Path(args.seed_file).read_bytes().strip()
    commitment = "sha256:" + hashlib.sha256(raw).hexdigest()
    return (
        int.from_bytes(hashlib.sha256(raw).digest()[:8], "big"),
        "OPERATOR_BANK",
        commitment,
    )


def _public_keys():
    panel = json.loads(f13.PANELS.read_text())["families"]["f13"]
    return {sr.digest(sr.geometry(dict(zip(sr.FIELDS, c["parameters"]))))
            for c in panel["public_cases"]}  # fmt: skip


def _write(out, designs, tranche, scope, commitment, mesh=True):
    out = Path(out)
    entries = []
    for i, action in enumerate(designs):
        name = f"{tranche}-{i:03d}"
        d = out / "f13" / name
        f13.write_case(action, d)
        if mesh:
            tf._mesh(d)
        entry = {"family": "f13", "case": name, "reservation": tranche,
                 "command": tf.SOLVE, "files": tf._digest(d),
                 "frequency_systems": 201, "action": action}  # fmt: skip
        if mesh:
            entry["mesh"] = {
                "nodes": json.loads((d / "groups.json").read_text())["nodes"],
                "h_mm": 8.0,
            }
        entries.append(entry)
    for e in entries:
        if "mesh" in e:
            e.update(f13_proof.estimate(e["mesh"]["nodes"], e["frequency_systems"]))
    path = out / f"manifest-{tranche}.json"
    manifest = {
        "schema": "carbon.reference-triage.frozen-decks.v1",
        "decision": sr.VALUES_DECISION,
        "scope": scope,
        "seed_commitment": commitment,
        "image": sr.IMAGE,
        "mesh_image_f13": f13.MESH_IMAGE,
        "deck_version": f13.DECK_VERSION,
        "deck_sha256": sr.DECK_SHA,
        "observer": sr.PINS["observer"],
        "cases": entries,
        "counts": {"f13": {tranche: len(entries)}},
        "frequency_systems": 201 * len(entries),
    }
    path.write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def tranche(args):
    seed, scope, commitment = _seed(args)
    public = _public_keys()
    designs = [
        a for a in sr.actions(args.count + 8, seed) if sr.digest(a) not in public
    ]
    designs = designs[: args.count]
    return _write(
        args.out, designs, "bank_tranche_1", scope, commitment, not args.no_mesh
    )


def near_floor(results):
    """Cases whose 8 mm p10 lies within NEAR_DB of the floor support [5, 7]."""
    lo, hi = FLOORS[0] - NEAR_DB, FLOORS[1] + NEAR_DB
    return sorted(c for c, r in results.items() if lo <= r["p10_tl_db"] <= hi)


def t2a(results):
    """Distinct near designs on each side of each checked floor (8 mm rung;
    final sides need the refined rung by F5)."""
    out = {}
    for floor in FLOORS:
        near = [
            r["p10_tl_db"]
            for r in results.values()
            if abs(r["p10_tl_db"] - floor) <= NEAR_DB
        ]
        out[str(floor)] = {"feasible": sum(p >= floor for p in near),
                           "infeasible": sum(p < floor for p in near)}  # fmt: skip
        out[str(floor)]["holds"] = min(out[str(floor)].values()) >= T2A_EACH_SIDE
    return out


def refine(args):
    """Refined-rung decks (4 mm mesh, BiCGStabl; 5 Hz grid) for near-floor designs."""
    bank = Path(args.bank)
    results = json.loads(Path(args.results).read_text())
    manifest = json.loads((bank / "manifest-bank_tranche_1.json").read_text())
    actions = {c["case"]: c["action"] for c in manifest["cases"]}
    entries = []
    for case in near_floor(results):
        for tag, kwargs in (("mesh4mm", {"h_mm": 4.0}), ("freq5hz", {"step_hz": 5.0})):
            d = bank / "f13" / f"{case}-{tag}"
            f13.write_case(actions[case], d, **kwargs)
            tf._mesh(d)
            entries.append({"family": "f13", "case": d.name, "reservation": "bank_refined",
                            "command": tf.SOLVE, "files": tf._digest(d),
                            "frequency_systems": len(json.loads((d / "deck.json").read_text())["frequencies_hz"]),
                            "mesh": {"nodes": json.loads((d / "groups.json").read_text())["nodes"], "h_mm": kwargs.get("h_mm", 8.0)}})  # fmt: skip
    for e in entries:
        e.update(f13_proof.estimate(e["mesh"]["nodes"], e["frequency_systems"]))
    doc = {**{k: manifest[k] for k in manifest if k not in ("cases", "counts", "frequency_systems")},
           "cases": entries, "counts": {"f13": {"bank_refined": len(entries)}},
           "frequency_systems": sum(e["frequency_systems"] for e in entries)}  # fmt: skip
    (bank / "manifest-bank_refined.json").write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def frontier(args):
    """Q2 frontier tranche: jitter near-floor designs (±10 % of each packet
    range), refuse invalid ones, until the T2(a) shortfall is covered or
    the M_MAX bank cap is reached."""
    bank = Path(args.bank)
    results = json.loads(Path(args.results).read_text())
    manifest = json.loads((bank / "manifest-bank_tranche_1.json").read_text())
    actions = {c["case"]: c["action"] for c in manifest["cases"]}
    seed, scope, commitment = _seed(args)
    rng = random.Random(seed)
    parents = [actions[c] for c in near_floor(results)] or list(actions.values())
    budget = min(args.count, M_MAX - len(actions))
    public = _public_keys() | {sr.digest(a) for a in actions.values()}
    designs = []
    for _ in range(budget * 50):
        if len(designs) >= budget:
            break
        p = rng.choice(parents)
        trial = {k: p[k] + rng.uniform(-0.1, 0.1) * (hi - lo)
                 for k, (lo, hi) in zip(sr.FIELDS, sr.BOUNDS)}  # fmt: skip
        try:
            trial = sr.geometry(trial)
        except ValueError:
            continue
        if sr.digest(trial) not in public:
            designs.append(trial)
            public.add(sr.digest(trial))
    doc = _write(
        bank, designs, "bank_tranche_2_frontier", scope, commitment, not args.no_mesh
    )
    doc["t2a_before"] = t2a(results)
    (bank / "manifest-bank_tranche_2_frontier.json").write_text(
        json.dumps(doc, indent=1) + "\n"
    )
    return doc


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f13_bank_freeze")
    parser.add_argument("command", choices=("tranche", "refine", "frontier"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--bank", type=Path)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--count", type=int, default=64)
    seed = parser.add_mutually_exclusive_group()
    seed.add_argument("--seed-file", type=Path)
    seed.add_argument("--public-seed", type=int)
    parser.add_argument("--no-mesh", action="store_true", help="decks only (dry run)")
    args = parser.parse_args(argv)
    if (
        args.command in ("tranche", "frontier")
        and args.seed_file is None
        and args.public_seed is None
    ):
        parser.error("an operator --seed-file or a --public-seed is required")
    doc = {"tranche": tranche, "refine": refine, "frontier": frontier}[args.command](
        args
    )
    print(json.dumps({"counts": doc["counts"], "frequency_systems": doc["frequency_systems"],
                      "scope": doc.get("scope")}))  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
