"""Freeze the public f02 cold-context pilot and rejudge retained solver outputs.

This DEVELOPMENT pilot extends the historical eight-geometry convergence
verification with four prospectively chosen near-limit actions. The 40 TRAIN
decks come from the already registered public menu-v2 TRAIN draw; no menu-v2
reference result or qualification is implied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import f02_deck as deck
import f02_readiness as readiness

NEAR_PEAK_W = (84.0, 85.0, 86.0, 87.0)
EVAL_ACTIONS = {(80.0, 5.0), (110.0, 10.0), (140.0, 5.0), (140.0, 20.0)}
EVAL_ACTIONS.update((peak, 5.0) for peak in NEAR_PEAK_W)
TRAIN_CONTEXT = "c30-i40-s0.5-rectangular"


def _add(entries, out, name, reservation, case, *, level=1, dt=1.0, check=None):
    case_dir = out / "f02" / name
    meta = deck.write_case(case, case_dir, level, dt)
    files = readiness._hashes(case_dir)
    if check is not None and files != check:
        raise ValueError(f"{name}: regenerated deck differs from registered TRAIN")
    entries.append(readiness.entry_for(name, reservation, files, meta))


def freeze_convergence(out):
    out = Path(out)
    readiness.freeze("convergence", out)
    entries = json.loads((out / "manifest.json").read_text())["cases"]
    base = deck.panel_case("cool-rect-low")
    for peak in NEAR_PEAK_W:
        case = dict(base, peak_w=peak, on_time_s=5.0)
        stem = f"cool-rect-near-{int(peak)}w"
        _add(entries, out, f"{stem}-primary", "primary", case)
        _add(entries, out, f"{stem}-mesh2", "mesh_and_time", case, level=2)
        _add(entries, out, f"{stem}-dt0.5", "mesh_and_time", case, dt=0.5)
    readiness._write_manifest(
        out,
        "cold-rect-convergence-pilot",
        entries,
        {"scope": "PUBLIC_DEVELOPMENT_ONLY", "new_actions": list(NEAR_PEAK_W)},
    )
    return len(entries)


def freeze_train(out):
    out = Path(out)
    registered = json.loads(readiness.TRAIN_MANIFEST.read_text())["cases"]
    selected = [e for e in registered if e["context"] == TRAIN_CONTEXT]
    if len(selected) != 40:
        raise ValueError(
            f"expected 40 registered cold-context TRAIN cases, got {len(selected)}"
        )
    actions = {(e["peak_w"], e["on_time_s"]) for e in selected}
    if len(actions) != 40 or actions & EVAL_ACTIONS:
        raise ValueError("TRAIN has repeated or evaluation actions")
    entries = []
    for e in selected:
        _add(
            entries,
            out,
            e["case"],
            "train",
            readiness._menu_case(e),
            check=e["files"],
        )
    readiness._write_manifest(
        out,
        "cold-rect-train40",
        entries,
        {
            "scope": "PUBLIC_DEVELOPMENT_ONLY",
            "source": str(readiness.TRAIN_MANIFEST.relative_to(readiness.ROOT)),
        },
    )
    return len(entries)


def rejudge(new_step, old_step, manifest, out):
    """Use new transient outputs and only matching historical baseline outputs."""
    new_step, old_step, manifest, out = map(Path, (new_step, old_step, manifest, out))
    rows = json.loads(manifest.read_text())["cases"]
    sources = {}
    with tempfile.TemporaryDirectory(prefix="f02-cold-rejudge-") as scratch:
        combined = Path(scratch)
        for row in rows:
            name = row["case"]
            if row["reservation"] == "controls":
                sources[name] = "separate_previously_accepted_A4_control"
                continue
            source = (
                old_step
                if row["reservation"]
                in (
                    "steady_baselines",
                    "transient_baselines",
                )
                else new_step
            )
            work = source / "cases" / "f02" / name / "work"
            deck_file = work / "deck.json"
            if (
                not deck_file.is_file()
                or hashlib.sha256(deck_file.read_bytes()).hexdigest()
                != row["files"]["deck.json"]
            ):
                raise ValueError(f"{name}: missing or changed registered deck")
            if not (work / "scalars.dat").is_file():
                raise ValueError(f"{name}: missing solved scalars")
            if source == new_step and not list(work.rglob("final*.vtu")):
                raise ValueError(f"{name}: final VTU was not retained")
            target = combined / "cases" / "f02" / name / "work"
            shutil.copytree(work, target)
            sources[name] = (
                "prior_matching_baseline" if source == old_step else "new_transient"
            )
        out.parent.mkdir(parents=True, exist_ok=True)
        result = readiness.judge(combined, out, manifest_path=manifest)
    provenance = {
        "schema": "carbon.f02-cold-pilot-rejudge.v1",
        "scope": "PUBLIC_DEVELOPMENT_ONLY",
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "new_step": str(new_step),
        "prior_step": str(old_step),
        "sources": sources,
        "family_acceptance": result["family_acceptance"],
    }
    result["provenance"] = provenance
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    out.with_suffix(".provenance.json").write_text(
        json.dumps(provenance, indent=1) + "\n"
    )
    return result


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("freeze-convergence", "freeze-train"):
        sub.add_parser(name).add_argument("out", type=Path)
    j = sub.add_parser("rejudge")
    for name in ("new_step", "old_step", "manifest", "out"):
        j.add_argument(name, type=Path)
    args = p.parse_args()
    if args.command == "freeze-convergence":
        print(freeze_convergence(args.out))
    elif args.command == "freeze-train":
        print(freeze_train(args.out))
    else:
        print(
            json.dumps(
                rejudge(args.new_step, args.old_step, args.manifest, args.out)[
                    "family_acceptance"
                ]
            )
        )


if __name__ == "__main__":
    main()
