"""Freeze #787's f08 triage decks (REFERENCE-PACKAGES-01).

    python3 f08_freeze.py --out DIR
    python3 f08_freeze.py --observe DIR --out OBSERVED.json

Test Lead 2026-10-08: run on the operator host's free CPU (no spend), one
CPU per ccx process, costs recorded as CPU-s with the host profile. #787
reserves 58 launches (40 unbatched primaries, 10 witness studies, 8
controls and repeat); batching static/eigen/three damping sweeps into one
ccx process makes the panel 17 launches:

    primary (8)          every public geometry, h 3 mm, 48 modes
    witness_studies (6)  #787's long-flexible and relieved-tall, plus the
                         nominal geometry (the packet's full-rung case), at
                         h 2.25 and 1.7 mm
    controls (2)         the analytic oscillators; an unribbed, unrelieved
                         220 x 20 x 6 mm beam against Euler-Bernoulli
    cold_repeat (1)      the first primary again

The 12/24/48 mode ladder and the frequency refinement come from each launch's
stored mass-normalised basis (f08_proof demonstrates the truncations equal
ccx's own 12/24-mode runs). Nothing is generated on the run host.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f08_deck as deck
import f08_proof as proof

IMAGE = "sha256:d9ef68d016226a945c7eefcb6b2261c60a11249ee0f93458ae6c3aca956fd6f8"
H_PRIMARY, H_WITNESS, MODES = 3.0, (2.25, 1.7), 48
WITNESS_LABELS = ("long-flexible", "relieved-tall", "nominal")


def _digest(case_dir):
    files = sorted(p for p in Path(case_dir).rglob("*") if p.is_file())
    return {
        str(p.relative_to(case_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
    }


def freeze(out):
    out = Path(out)
    labels = [
        c["label"]
        for c in json.loads(deck.PANELS.read_text())["families"]["f08"]["public_cases"]
    ]
    plan = [(lb, "primary", H_PRIMARY, "primary") for lb in labels]
    plan += [
        (lb, f"h{h:g}", h, "witness_studies")
        for lb in WITNESS_LABELS
        for h in H_WITNESS
    ]
    plan += [("control-beam", "h2", 2.0, "controls")]
    plan += [(labels[0], "cold-repeat", H_PRIMARY, "cold_repeat")]
    entries = []
    for label, tag, h, reservation in plan:
        d = out / "f08" / (label if label.startswith("control") else f"{label}-{tag}")
        case = deck.BEAM_CONTROL if label == "control-beam" else deck.panel_case(label)
        size = deck.write_case(case, d, h, MODES)
        entries.append({"family": "f08", "case": d.name, "reservation": reservation, "command": deck.COMMAND,
                        "mesh": size, "files": _digest(d)})  # fmt: skip
    d = out / "f08" / "control-oscillators"
    d.mkdir(parents=True, exist_ok=True)
    (d / "case.inp").write_text(proof.oscillator_deck()[0])
    (d / "deck.json").write_text(json.dumps({"control": "oscillators"}) + "\n")
    entries.insert(len(labels), {"family": "f08", "case": d.name, "reservation": "controls",
                                 "command": deck.COMMAND, "files": _digest(d)})  # fmt: skip
    manifest = {
        "schema": "carbon.reference-triage.frozen-decks.v1",
        "ticket": "REFERENCE-PACKAGES-01",
        "authority": "Test Lead 2026-10-08: #787 f08 triage on local free CPU, no spend",
        "image": IMAGE,
        "mesh_image_f08": deck.MESH_IMAGE,
        "cases": entries,
        "counts": {
            r: sum(e["reservation"] == r for e in entries)
            for r in sorted({e["reservation"] for e in entries})
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest["counts"]


def observe_all(decks, out):
    decks = Path(decks)
    rows = {}
    for d in sorted((decks / "f08").iterdir()):
        if not (d / "case.dat").exists():
            rows[d.name] = {"status": "NOT_RUN_OR_NO_OUTPUT"}
            continue
        try:
            if d.name == "control-oscillators":
                steps = proof.parse_dat((d / "case.dat").read_text(errors="replace"))
                rows[d.name] = proof.oscillator_check(steps)
            else:
                obs = deck.observe(d)
                if d.name == "control-beam":
                    obs["beam_theory"] = deck.beam_theory()
                    obs["static_over_beam_theory"] = (
                        obs["static_tip_mm_per_n"]
                        / obs["beam_theory"]["static_mm_per_n"]
                    )
                    obs["f1_over_beam_theory"] = (
                        obs["eigen_hz"][0] / obs["beam_theory"]["f1_hz"]
                    )
                rows[d.name] = obs
        except (
            KeyError,
            IndexError,
            ValueError,
        ) as error:  # malformed output is a reference failure
            rows[d.name] = {"status": "OBSERVER_FAILED", "why": repr(error)}
    Path(out).write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n")
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f08_freeze")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--observe", type=Path)
    args = parser.parse_args(argv)
    if args.observe:
        rows = observe_all(args.observe, args.out)
        print(
            json.dumps(
                {
                    k: v.get("worst_dynamic_mm_per_n", v.get("status"))
                    for k, v in rows.items()
                },
                indent=1,
            )
        )
    else:
        print(json.dumps(freeze(args.out), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
