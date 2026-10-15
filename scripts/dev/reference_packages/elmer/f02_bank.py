"""f02 round-2 public bank v3: design and freeze (F02-SCIENCE-VALUES-01 §E).

    python3 f02_bank.py design STEPS_DIR BASELINES_DIR REGISTRY.json
    python3 f02_bank.py freeze REGISTRY.json OUT_DIR

`design` places the frontier brackets. For each of the 24 contexts, each
bracket duration and each registered ceiling, it finds by bisection the
power P*(D, c) whose PREDICTED peak equals c (f02_superpose: 20 W baseline
plus the superposed step response; planning only), and registers the pair
floor(P*) and floor(P*) + step on the bracket power grid: one action just
inside and one just outside each ceiling. Predictions only choose where the
actions sit; every verdict comes from the solved decks and their rungs.
The registry also lists the low-power seed row and the retained menu-v2
actions, and the TRAIN v2 draw rule.

`freeze` writes every deck and OUT_DIR/manifest.json
(`carbon.reference-triage.frozen-decks.v1`): bank primaries (menu v2 decks
byte-checked against their registered manifest), 8 transient and 4 steady
20 W baselines, both rungs (mesh 2, dt/2) for every bracket action (they are
decision contenders by design, B8) and for the B9 audit sample, and TRAIN
v2. Seed actions whose solved peak lands in the B8 window get their rungs in
a second, small freeze after the primaries solve
(`f02_readiness.py freeze-contenders`).
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f02_baselines as baselines
import f02_deck as deck
import f02_menu as menu
import f02_readiness as readiness
import f02_superpose as sp

SCHEMA = "carbon.f02-bank-v3.registry.v1"
POWER_RANGE_W = (30.0, 140.0)  # registered action box (§E); burst above the 20 W base
DURATION_RANGE_S = (5.0, 20.0)
CEILINGS_C = (90.0, 92.5, 95.0)
BRACKET_DURATIONS_S = (5.0, 8.0, 11.0, 14.0, 17.0, 20.0)
BRACKET_STEP_W = 0.5
LOW_SEED_W = (30.0, 50.0)
TRAIN_SEED, TRAIN_PER_CONTEXT = 20261015, 40


def p_star(base, d, ceiling, steps, bases):
    """Predicted power whose peak equals the ceiling (None outside the box)."""
    lo, hi = POWER_RANGE_W

    def pk(p):
        return sp.peak({**base, "peak_w": p, "on_time_s": d}, steps, bases)[0]

    if pk(lo) > ceiling:
        return None, pk(lo)
    if pk(hi) <= ceiling:
        return math.inf, pk(hi)
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if pk(mid) <= ceiling else (lo, mid)
    return lo, None


def design(steps_dir, baselines_dir, out):
    steps, bases = sp.load(steps_dir, baselines_dir)
    contexts = {}
    for ctx, base in menu.contexts():
        actions, notes = {}, []

        def put(p, d, role, predicted=None, actions=actions):
            key = (round(p, 1), round(d, 1))
            row = actions.setdefault(
                key, {"peak_w": key[0], "on_time_s": key[1], "roles": []}
            )
            row["roles"].append(role)
            if predicted is not None:
                row["predicted_peak_c"] = predicted

        for p, d in itertools.product(menu.PEAKS_W, menu.ON_TIMES_S):
            put(p, d, "menu_v2")
        for p, d in itertools.product(LOW_SEED_W, menu.ON_TIMES_S):
            put(p, d, "low_seed")
        for c, d in itertools.product(CEILINGS_C, BRACKET_DURATIONS_S):
            star, edge = p_star(base, d, c, steps, bases)
            if star is None:
                notes.append(
                    f"c{c:g} d{d:g}: box floor {POWER_RANGE_W[0]:g} W predicted {edge:.2f} C > ceiling"
                )
                continue
            if star == math.inf:
                notes.append(
                    f"c{c:g} d{d:g}: box top predicted {edge:.2f} C <= ceiling"
                )
                continue
            inside = math.floor(star / BRACKET_STEP_W) * BRACKET_STEP_W
            outside = inside + BRACKET_STEP_W
            for p, side in ((inside, "feasible"), (outside, "infeasible")):
                if POWER_RANGE_W[0] <= p <= POWER_RANGE_W[1]:
                    pred = sp.peak({**base, "peak_w": p, "on_time_s": d}, steps, bases)[
                        0
                    ]
                    put(p, d, f"bracket_c{c:g}_{side}", pred)
        for key, row in actions.items():
            if "predicted_peak_c" not in row:
                row["predicted_peak_c"] = sp.peak(
                    {**base, "peak_w": key[0], "on_time_s": key[1]}, steps, bases
                )[0]
        contexts[ctx] = {
            "actions": [actions[k] for k in sorted(actions)],
            "notes": notes,
        }
    train = train_draws(contexts)
    doc = {
        "schema": SCHEMA,
        "decision": "F02-SCIENCE-VALUES-01",
        "role": "public DEVELOPMENT bank and TRAIN; never hidden, quiz or exam material",
        "power_range_w": POWER_RANGE_W, "duration_range_s": DURATION_RANGE_S,
        "ceilings_c": CEILINGS_C, "bracket_durations_s": BRACKET_DURATIONS_S,
        "bracket_step_w": BRACKET_STEP_W, "low_seed_w": LOW_SEED_W,
        "predictor": "f02_superpose (planning only; step responses and 20 W baselines on the local image)",
        "contexts": contexts,
        "train_v2": {"seed": TRAIN_SEED, "per_context": TRAIN_PER_CONTEXT,
                     "draw": "numpy default_rng(seed), consumed in the menu's context order: peak U[30, 140] W at 1 W, on-time U[5, 20] s at 0.1 s; a draw equal to a bank action of that context, or a duplicate, is redrawn",
                     "cases": train},
        "counts": {
            "bank_actions": sum(len(v["actions"]) for v in contexts.values()),
            "bracket_actions": sum(
                1 for v in contexts.values() for a in v["actions"]
                if any(r.startswith("bracket") for r in a["roles"])
            ),
            "train": len(train),
        },
    }  # fmt: skip
    Path(out).write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def train_draws(contexts):
    rng = np.random.default_rng(TRAIN_SEED)
    out = []
    for ctx, _ in menu.contexts():
        bank = {(a["peak_w"], a["on_time_s"]) for a in contexts[ctx]["actions"]}
        seen = set()
        while len(seen) < TRAIN_PER_CONTEXT:
            peak = float(round(rng.uniform(*POWER_RANGE_W)))
            on = round(float(rng.uniform(*DURATION_RANGE_S)), 1)
            if (peak, on) in bank or (peak, on) in seen:
                continue
            seen.add((peak, on))
            out.append([ctx, peak, on])
    return out


def case_name(ctx, p, d, tag):
    return f"{ctx}-p{p:g}-d{d:g}-{tag}"


def freeze(registry, out):
    reg = json.loads(Path(registry).read_text())
    out, ctxs, entries = Path(out), dict(menu.contexts()), []
    menu_files = readiness._registered(readiness.MENU_MANIFEST)

    def add(name, reservation, case, *, level=1, dt=1.0, steady=False, check=None):
        d = out / "f02" / name
        meta = deck.write_case(case, d, level, dt, steady)
        files = readiness._hashes(d)
        if check is not None and files != check:
            raise SystemExit(
                f"{name}: regenerated deck differs from its registered manifest"
            )
        entries.append({"family": "f02", "case": name, "reservation": reservation,
                        "command": readiness.SOLVE, "files": files, "mesh": meta["mesh"]})  # fmt: skip

    primaries = {}
    for ctx, block in reg["contexts"].items():
        for a in block["actions"]:
            case = {**ctxs[ctx], "peak_w": a["peak_w"], "on_time_s": a["on_time_s"]}
            name = case_name(ctx, a["peak_w"], a["on_time_s"], "primary")
            add(name, "primary", case, check=(menu_files.get(name) or {}).get("files"))
            primaries[name] = {"context": ctx, "case": case, "roles": a["roles"]}
    registered = readiness._registered(readiness.BASELINE_MANIFEST)
    for name, case in baselines.contexts():
        add(name, "transient_baselines", case, check=registered[name]["files"])
    for name, case in readiness.steady_regimes():
        add(name, "steady_baselines", case, steady=True)
    refine = [
        n
        for n, p in primaries.items()
        if any(r.startswith("bracket") for r in p["roles"])
    ]
    audit = [n for n in readiness.audit_choice(primaries) if n not in refine]
    for names, reservation in (
        (refine, "contender_refinement"),
        (audit, "audit_refinement"),
    ):
        for name in names:
            stem, case = name[: -len("-primary")], primaries[name]["case"]
            add(f"{stem}-mesh2", reservation, case, level=2)
            add(f"{stem}-dt0.5", reservation, case, dt=0.5)
    for ctx, p, d in reg["train_v2"]["cases"]:
        add(
            case_name(ctx, p, d, "train"),
            "train",
            {**ctxs[ctx], "peak_w": p, "on_time_s": d},
        )
    readiness._write_manifest(out, "bank-v3", entries, {
        "registry": "docs/development/evidence/reference-packages-01/f02-readiness/bank-v3-registry.json",
        "deferred": "seed actions whose solved peak lands in [89, 96] C get both rungs in a second freeze: f02_readiness.py freeze-contenders BANK_DIR OUT",
    })  # fmt: skip
    return {
        r: sum(1 for e in entries if e["reservation"] == r)
        for r in sorted({e["reservation"] for e in entries})
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f02_bank")
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("design")
    d.add_argument("steps", type=Path)
    d.add_argument("baselines", type=Path)
    d.add_argument("out", type=Path)
    f = sub.add_parser("freeze")
    f.add_argument("registry", type=Path)
    f.add_argument("out", type=Path)
    args = parser.parse_args(argv)
    if args.command == "design":
        doc = design(args.steps, args.baselines, args.out)
        print(json.dumps(doc["counts"], indent=1))
    else:
        print(json.dumps(freeze(args.registry, args.out), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
