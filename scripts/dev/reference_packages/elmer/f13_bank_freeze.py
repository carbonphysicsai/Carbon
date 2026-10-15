"""f13 role freeze path: TRAIN, PRACTICE, decision study and banks
(F13-SCIENCE-VALUES-01 F5-F8 and G; data-acquisition/f13.md).

    # a representative role drawn from the packet geometry law P
    python -m scripts.dev.reference_packages.elmer.f13_bank_freeze freeze --role train --count 256 \
        (--public-seed N | --seed-file SEED) --out DIR [--exclude OTHER_MANIFEST ...]
    # refined rungs (4 mm mesh; 5 Hz grid) for every design within 0.5 dB of a floor in [5, 7] dB
    python -m scripts.dev.reference_packages.elmer.f13_bank_freeze refine --manifest DIR/manifest-ROLE.json --results RESULTS.json
    # a boundary (Q2 frontier) role: jitter near-floor designs of a solved role
    python -m scripts.dev.reference_packages.elmer.f13_bank_freeze frontier --role decision_boundary --count 32 \
        --manifest DIR/manifest-ROLE.json --results RESULTS.json (--public-seed N | --seed-file SEED) --out DIR

Public roles (TRAIN, PRACTICE, decision study, timing) use `--public-seed`
and are labelled PUBLIC_DEVELOPMENT. Sealed roles (hidden pool, tuning,
confirmation) run only on the custody host with `--seed-file`: the seed is
read from the operator's file and only its sha256 commitment is written.
Every role is whole-geometry disjoint from the public recipe panel and from
each `--exclude` manifest (by action digest). Every deck is the accepted f13
v2 deck (60 mm leads, 8 mm P2 mesh, 201 points, BiCGStabl+ILU2) bound to
`silencer_readiness.IMAGE`, in the shared `carbon.reference-triage.frozen-
decks.v1` schema with estimate_cpu_s/estimate_wall_s/estimate_mem_mib, so
the bulk runner can launch it. Case commands are plain shell (ElmerGrid and
ElmerSolver on PATH), so they run in the image or on a native build;
meshing needs Gmsh 4.15 (the pinned mesher image, or `CARBON_F13_NATIVE_GMSH=1`
for a native `python3` with the gmsh module). RESULTS.json is
{case: {"p10_tl_db": float}} from the observer. Nothing here runs a solver.
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
ROLES = (
    "train",
    "practice",
    "decision_representative",
    "decision_boundary",
    "hidden_pool",
    "hidden_standby",
    "tuning",
    "confirmation_representative",
    "confirmation_boundary",
)
SEALED = {
    "hidden_pool",
    "hidden_standby",
    "tuning",
    "confirmation_representative",
    "confirmation_boundary",
}


def _seed(args):
    sealed = args.role in SEALED
    if args.public_seed is not None:
        if sealed:
            raise SystemExit(
                "sealed roles need the operator --seed-file, never a public seed"
            )
        return args.public_seed, "PUBLIC_DEVELOPMENT", None
    if args.seed_file is None:
        raise SystemExit("an operator --seed-file or a --public-seed is required")
    raw = Path(args.seed_file).read_bytes().strip()
    commitment = "sha256:" + hashlib.sha256(raw).hexdigest()
    seed = int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")
    return seed, "SEALED_CUSTODY" if sealed else "OPERATOR_PUBLIC", commitment


def _excluded(paths):
    panel = json.loads(f13.PANELS.read_text())["families"]["f13"]
    keys = {sr.digest(sr.geometry(dict(zip(sr.FIELDS, c["parameters"]))))
            for c in panel["public_cases"]}  # fmt: skip
    for path in paths or ():
        for case in json.loads(Path(path).read_text())["cases"]:
            if "action" in case:
                keys.add(sr.digest(case["action"]))
    return keys


def _mesh_and_entry(d, name, role, h_mm=8.0):
    tf._mesh(d)
    meta = json.loads((d / "deck.json").read_text())
    nodes = json.loads((d / "groups.json").read_text())["nodes"]
    entry = {"family": "f13", "case": name, "reservation": role, "command": tf.SOLVE,
             "files": tf._digest(d), "frequency_systems": len(meta["frequencies_hz"]),
             "mesh": {"nodes": nodes, "h_mm": h_mm}, "action": meta["case"]}  # fmt: skip
    entry.update(f13_proof.estimate(nodes, entry["frequency_systems"]))
    return entry


def _manifest(out, role, entries, scope, commitment, extra=None):
    manifest = {
        "schema": "carbon.reference-triage.frozen-decks.v1",
        "decision": sr.VALUES_DECISION,
        "role": role,
        "scope": scope,
        "seed_commitment": commitment,
        "image": sr.IMAGE,
        "mesh_image_f13": f13.MESH_IMAGE,
        "deck_version": f13.DECK_VERSION,
        "deck_sha256": sr.DECK_SHA,
        "observer": sr.PINS["observer"],
        "cases": entries,
        "counts": {"f13": {role: len(entries)}},
        "frequency_systems": sum(e["frequency_systems"] for e in entries),
        "estimate_cpu_h": round(sum(e["estimate_cpu_s"] for e in entries) / 3600, 2),
        **(extra or {}),
    }
    path = Path(out) / f"manifest-{role}.json"
    path.write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def freeze(args):
    """A representative role from P (uniform conditioned geometry law)."""
    seed, scope, commitment = _seed(args)
    excluded = _excluded(args.exclude)
    designs = [a for a in sr.actions(args.count + len(excluded), seed)
               if sr.digest(a) not in excluded][: args.count]  # fmt: skip
    if len(designs) < args.count:
        raise SystemExit("not enough distinct designs after exclusion")
    entries = []
    for i, action in enumerate(designs):
        name = f"{args.role}-{i:04d}"
        d = Path(args.out) / "f13" / name
        f13.write_case(action, d)
        entries.append(_mesh_and_entry(d, name, args.role))
    return _manifest(args.out, args.role, entries, scope, commitment,
                     {"law": "P: uniform independent packet parameters conditioned on clearance/packaging",
                      "nesting": "the first n cases of this manifest are the size-n prefix"})  # fmt: skip


def near_floor(results):
    """Cases whose 8 mm p10 lies within NEAR_DB of the floor support [5, 7]."""
    lo, hi = FLOORS[0] - NEAR_DB, FLOORS[1] + NEAR_DB
    return sorted(c for c, r in results.items() if lo <= r["p10_tl_db"] <= hi)


def t2a(results):
    """Distinct near designs on each side of each checked floor (8 mm rung;
    final sides need the refined rung by F5)."""
    out = {}
    for floor in FLOORS:
        near = [r["p10_tl_db"] for r in results.values()
                if abs(r["p10_tl_db"] - floor) <= NEAR_DB]  # fmt: skip
        row = {"feasible": sum(p >= floor for p in near),
               "infeasible": sum(p < floor for p in near)}  # fmt: skip
        row["holds"] = min(row.values()) >= T2A_EACH_SIDE
        out[str(floor)] = row
    return out


def refine(args):
    """Refined-rung decks (4 mm mesh; 5 Hz grid) for near-floor designs."""
    source = json.loads(Path(args.manifest).read_text())
    out = Path(args.manifest).parent
    results = json.loads(Path(args.results).read_text())
    actions = {c["case"]: c["action"] for c in source["cases"]}
    role = f"{source['role']}_refined"
    entries = []
    for case in near_floor({c: r for c, r in results.items() if c in actions}):
        for tag, kwargs in (("mesh4mm", {"h_mm": 4.0}), ("freq5hz", {"step_hz": 5.0})):
            d = out / "f13" / f"{case}-{tag}"
            f13.write_case(actions[case], d, **kwargs)
            entries.append(_mesh_and_entry(d, d.name, role, kwargs.get("h_mm", 8.0)))
    return _manifest(out, role, entries, source["scope"], source["seed_commitment"])


def frontier(args):
    """Boundary (Q2 frontier) role: jitter near-floor designs of a solved
    role by +-10 % of each packet range; invalid geometry is refused, never
    clipped. Weights w = P/Q are reported by the study, not by this file."""
    source = json.loads(Path(args.manifest).read_text())
    results = json.loads(Path(args.results).read_text())
    actions = {c["case"]: c["action"] for c in source["cases"]}
    seed, scope, commitment = _seed(args)
    rng = random.Random(seed)
    parents = [actions[c] for c in near_floor(results) if c in actions] or list(
        actions.values()
    )
    excluded = _excluded(args.exclude) | {sr.digest(a) for a in actions.values()}
    designs = []
    for _ in range(args.count * 50):
        if len(designs) >= args.count:
            break
        p = rng.choice(parents)
        trial = {k: p[k] + rng.uniform(-0.1, 0.1) * (hi - lo)
                 for k, (lo, hi) in zip(sr.FIELDS, sr.BOUNDS)}  # fmt: skip
        try:
            trial = sr.geometry(trial)
        except ValueError:
            continue
        if sr.digest(trial) not in excluded:
            designs.append(trial)
            excluded.add(sr.digest(trial))
    entries = []
    for i, action in enumerate(designs):
        name = f"{args.role}-{i:04d}"
        d = Path(args.out) / "f13" / name
        f13.write_case(action, d)
        entries.append(_mesh_and_entry(d, name, args.role))
    return _manifest(args.out, args.role, entries, scope, commitment,
                     {"law": "Q2 frontier: +-10 % jitter of designs within 0.5 dB of a floor",
                      "t2a_before": t2a({c: r for c, r in results.items() if c in actions})})  # fmt: skip


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f13_bank_freeze")
    parser.add_argument("command", choices=("freeze", "refine", "frontier"))
    parser.add_argument("--role", choices=ROLES)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--count", type=int, default=64)
    parser.add_argument("--exclude", type=Path, nargs="*")
    seed = parser.add_mutually_exclusive_group()
    seed.add_argument("--seed-file", type=Path)
    seed.add_argument("--public-seed", type=int)
    args = parser.parse_args(argv)
    if args.command != "refine" and (args.role is None or args.out is None):
        parser.error("--role and --out are required")
    if args.out:
        Path(args.out).mkdir(parents=True, exist_ok=True)
    doc = {"freeze": freeze, "refine": refine, "frontier": frontier}[args.command](args)
    print(json.dumps({"counts": doc["counts"], "frequency_systems": doc["frequency_systems"],
                      "estimate_cpu_h": doc["estimate_cpu_h"], "scope": doc["scope"]}))  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
