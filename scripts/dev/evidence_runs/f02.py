"""Registered evidence entrypoint: f02 burst-thermal (EVIDENCE-ENTRYPOINTS-01).

    python -m scripts.dev.evidence_runs.f02 plan --kind {menu,train} --root DIR
    python -m scripts.dev.evidence_runs.f02 check --kind {menu,train} --root DIR
    python -m scripts.dev.evidence_runs.f02 solve --kind {menu,train} --root DIR [--parallel N]
    python -m scripts.dev.evidence_runs.f02 export-train --root DIR --out FILE.jsonl --diagnostics FILE.jsonl

- **Decks** are generated deterministically into `--root` and bound by the
  sha256 of their manifest (every deck file's digest):
  - `menu`: the #846 f02-v2 test menu, 384 decks (16 actions x 24 contexts),
    `f02-menu-v2/registry.json`;
  - `train`: the public TRAIN split, 960 decks (40 per context), drawn by
    `f02-menu-v2/train-registry.json` (one generator seeded 20261010, consumed in the menu's
    context order; peak U[80, 140] W at 1 W, on-time U[5, 20] s at 0.1 s;
    a menu point or a duplicate is redrawn).
- **Solver:** the re-pinned Elmer 26.2.1 image (sha256:6fab746f...), one CPU
  per ElmerSolver, through `f02_menu.run`, which re-checks every deck file's
  digest against the manifest before launching it.
- **Output:** `<root>/cases/<case>/` (Elmer scalars and the final VTU) and
  `<root>/ledger.jsonl` (wall, CPU, memory, exit per case).
- **export-train:** `carbon.f02.train-record.v1` JSONL for the f02 kit (#1036):
  inputs {coolant_c, h_w_m2_k, initial_c, left_source_fraction, waveform,
  peak_w, on_time_s}, outputs exactly {peak_top_c, extra_energy_j} from the
  panel's observer. The diagnostics file holds `first_95c_crossing_s` and the
  0.5-s die-top and patch histories per case, never in a row's values.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from scripts.dev.evidence_runs import common

HERE = common.ROOT / "scripts/dev/reference_packages/elmer"
sys.path.insert(0, str(HERE))

import f02_deck as deck
import f02_menu as menu

IMAGE_REF = "carbon-ref-elmer:26.2.1"
IMAGE_DIGEST = "sha256:6fab746f31257236da9e91b5be681bfbd2d25bd69f5dcd9a2e350394e8bcb675"
MANIFESTS = {
    "menu": "docs/development/evidence/reference-packages-01/f02-menu-v2/decks-manifest.json",
    "train": "docs/development/evidence/reference-packages-01/f02-menu-v2/train-decks-manifest.json",
}
TRAIN_SEED, TRAIN_PER_CONTEXT = 20261010, 40
TRAIN_SCHEMA = "carbon.f02.train-record.v1"
MENU_POINTS = {(p, d) for p in menu.PEAKS_W for d in menu.ON_TIMES_S}


def train_draws():
    """[(context, base, peak_w, on_time_s)] in registry order (960)."""
    out = []
    rng = np.random.default_rng(
        TRAIN_SEED
    )  # one generator, consumed in the menu's context order
    for ctx, base in menu.contexts():
        seen = set()
        while len(seen) < TRAIN_PER_CONTEXT:
            peak = float(round(rng.uniform(80.0, 140.0)))
            on = round(float(rng.uniform(5.0, 20.0)), 1)
            if (peak, on) in MENU_POINTS or (peak, on) in seen:
                continue
            seen.add((peak, on))
            out.append((ctx, base, peak, on))
    return out


def plan(kind, root):
    root = Path(root)
    if kind == "menu":
        menu.plan(root)
        return root / "manifest.json"
    entries = []
    for ctx, base, peak, on in train_draws():
        name = menu.case_name(ctx, peak, on, "train")
        deck.write_case(
            {**base, "peak_w": peak, "on_time_s": on}, root / "cases" / name
        )
        entries.append(
            {
                "case": name,
                "context": ctx,
                "peak_w": peak,
                "on_time_s": on,
                "tag": "train",
            }
        )
    menu._manifest(root, entries)
    return root / "manifest.json"


def check(kind, root, inspect=None):
    registered = common.ROOT / MANIFESTS[kind]
    if not registered.exists():
        raise common.Refused("MANIFEST_NOT_REGISTERED", str(registered))
    common.require_plan(Path(root) / "manifest.json", common.sha256_file(registered))
    common.require_image(IMAGE_REF, IMAGE_DIGEST, inspect)


def solve(kind, root, parallel):
    check(kind, root)
    menu.run(
        root,
        parallel,
        IMAGE_DIGEST,
        "registered evidence entrypoint (EVIDENCE-ENTRYPOINTS-01)",
    )
    return 0


def train_record(entry, base, observed):
    """One kit TRAIN record: the context axes and the action as inputs, exactly
    the two panel observables as outputs."""
    return {
        "schema": TRAIN_SCHEMA,
        "case_id": entry["case"],
        "inputs": {**base, "peak_w": entry["peak_w"], "on_time_s": entry["on_time_s"]},
        "outputs": {
            "peak_top_c": observed["peak_top_c"],
            "extra_energy_j": observed["extra_energy_j"],
        },
    }


def export_train(root, out, diagnostics):
    manifest = json.loads((Path(root) / "manifest.json").read_text())
    rows, diag, failed = [], [], 0
    for e in manifest["cases"]:
        if e["tag"] != "train":
            continue
        base = next(b for c, b in menu.contexts() if c == e["context"])
        try:
            o = deck.observe(Path(root) / "cases" / e["case"])
        except (OSError, StopIteration, ValueError, IndexError):
            failed += 1
            continue
        rows.append(train_record(e, base, o))
        diag.append({"case_id": e["case"], "first_95c_crossing_s": o["first_95c_crossing_s"],
                     "peak_time_s": o["peak_time_s"], "top_max_c_at_0p5s": o["top_max_c_at_0p5s"],
                     "patch_centres_c_at_0p5s": o["patch_centres_c_at_0p5s"]})  # fmt: skip
    sha = common.write_jsonl(out, rows)
    common.write_jsonl(diagnostics, diag)
    return {"exported": len(rows), "failed_observe": failed, "sha256": sha}


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="evidence_runs.f02", description=__doc__.split("\n")[0]
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "check", "solve"):
        p = sub.add_parser(name)
        p.add_argument("--kind", choices=sorted(MANIFESTS), required=True)
        p.add_argument("--root", type=Path, required=True)
        if name == "solve":
            p.add_argument("--parallel", type=int, default=2)
    e = sub.add_parser("export-train")
    e.add_argument("--root", type=Path, required=True)
    e.add_argument("--out", type=Path, required=True)
    e.add_argument("--diagnostics", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "plan":
            path = plan(args.kind, args.root)
            print(
                json.dumps({"manifest": str(path), "sha256": common.sha256_file(path)})
            )
        elif args.cmd == "check":
            check(args.kind, args.root)
            print(json.dumps({"status": "OK", "image": IMAGE_DIGEST}))
        elif args.cmd == "solve":
            return solve(args.kind, args.root, args.parallel)
        else:
            print(json.dumps(export_train(args.root, args.out, args.diagnostics)))
        return 0
    except common.Refused as refused:
        print(json.dumps({"refused": refused.code, "detail": str(refused)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
