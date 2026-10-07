"""Quiz and pool batches drawn at random from a pre-solved bank (analysis memo,
public stand-in only; not a registration).

    python -m scripts.dev.battery.quiz_bank --out bank.json

The binary-feedback probe model of `quiz_load probe`, re-run when every quiz
and every pool batch is a fresh random draw of n cases from a bank of B:

- **Stand-in bank.** Q2 and pool cases are bootstrapped from the public
  scoring set (Q2 from its near-limit pool) with a small input jitter (2 % of
  each range); each copy keeps its parent's reference verdict and the
  boundary-optimist's damage flag. Q3 scenarios are uniform conditions over
  EV4's envelope.
- **Attacker.** Adaptive binary splitting over input cells, as before. A
  group's pass is now noisy (the draw may simply miss its damage), so a pass
  is believed only after r consecutive passes, r set for 95 % confidence
  that a cell holding one bank damage case would have shown it. A fail is
  certain.
- **Gain.** False-feasible on fresh population cases (Q2, pool) or the share
  of fresh conditions left free (Q3) once the attacker is optimistic in the
  cells it believes clean; plus its gate-fail rate when it does so.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.battery import quiz_load as ql

RATIOS = (1, 2, 5, 10, 20)
REPLICATES = 40
EXAM = 3000
NAMES = ("c1", "c2", "t_amb_c", "soc0")
DRAWS_PER_DAY = ql.TEMPOS_PER_DAY


def _population():
    from carbon.battery.value import contract as ev
    from carbon.battery.value import decision as d
    from carbon.battery.value import panel as pn
    from carbon.battery.value import quiz
    from carbon.battery.value import scoring as sc

    contract, _ = ev.load(ql.CONTRACT)
    store, ids, _ = sc.scoring_set(ROOT)
    bands = contract["reference"]["uncertainty"]["bands"]
    optimist = pn.control_predictions("boundary_optimist", store.refs)
    rows = []
    for c in ids:
        r = store.refs[c]
        if r.get("status") != "OK" or not r.get("outputs"):
            continue
        truth = d.check(contract, d.measure(contract, r["outputs"]), bands)
        bad = any(v == d.FAIL for v in truth.values())
        rows.append(
            {
                "inputs": r["inputs"],
                "near": quiz.q2_near(contract, r),
                "bad": bad,
                "damage": bad and quiz._feasible_call(contract, optimist[c])[0],
            }
        )
    return rows


def _bootstrap(rng, parents, count):
    out = []
    for i in rng.integers(0, len(parents), count):
        p = parents[i]
        inputs = {}
        for name in NAMES:
            low, high = ql.BOUNDS[name]
            value = p["inputs"][name] + rng.normal(0, 0.02 * (high - low))
            inputs[name] = min(high, max(low, value))
        out.append({**p, "inputs": inputs})
    return out


def _repeats(n, bank):
    if bank <= n:
        return 1
    return math.ceil(math.log(0.05) / math.log(1 - n / bank))


def _attack(rng, items, cell_of, n, cells=None):
    """Noisy splitting over `cells` (default: the cells the bank occupies).
    Returns probes, believed-clean cells, and the gate-fail rate when
    optimistic there."""
    cells = sorted(cells or {cell_of(x) for x in items})
    damage_cells = [cell_of(x) if x["damage"] else None for x in items]
    r = _repeats(n, len(items))
    probes = 0

    def test(group):
        nonlocal probes
        group = set(group)
        for _ in range(r):
            probes += 1
            drawn = rng.choice(len(items), n, replace=False)
            if any(damage_cells[i] in group for i in drawn):
                return False
        return True

    clean = []

    def solve(group, known_bad=False):
        if not known_bad and test(group):
            clean.extend(group)
            return
        if len(group) == 1:
            return
        half = len(group) // 2
        left, right = group[:half], group[half:]
        if test(left):
            clean.extend(left)
            solve(right, known_bad=True)
        else:
            solve(left, known_bad=True)
            solve(right)

    solve([cells[i] for i in rng.permutation(len(cells))])
    clean = set(clean)
    fails = 0
    for _ in range(200):
        drawn = rng.choice(len(items), n, replace=False)
        fails += any(damage_cells[i] in clean for i in drawn)
    return probes, clean, fails / 200


def _family(rng, label, parents, n, bins, population):
    rows = {}

    def cell_of(x):
        return ql._cell(x["inputs"], NAMES, bins)

    region = {cell_of(x) for x in parents}
    for ratio in RATIOS:
        stats = {
            "probes": [],
            "gain": [],
            "gate_fail": [],
            "ceiling": [],
            "coverage": [],
        }
        for _ in range(REPLICATES):
            bank = _bootstrap(rng, parents, n * ratio)
            fresh = _bootstrap(rng, population, EXAM)
            # Coverage: the P mass of the cells the live bank occupies.
            bank_cells = {cell_of(x) for x in bank}
            stats["coverage"].append(
                sum(cell_of(x) in bank_cells for x in fresh) / len(fresh)
            )
            exam = [x for x in fresh if x["bad"]]
            bank_damage = {cell_of(x) for x in bank if x["damage"]}
            stats["ceiling"].append(
                sum(x["damage"] and cell_of(x) not in bank_damage for x in exam)
                / len(exam)
            )
            # The attacker probes every cell the public near band occupies
            # (as in `quiz_load probe`), not just the bank's.
            probes, clean, fail = _attack(rng, bank, cell_of, n, region)
            stats["probes"].append(probes)
            stats["gain"].append(
                sum(x["damage"] and cell_of(x) in clean for x in exam) / len(exam)
            )
            stats["gate_fail"].append(fail)
        rows[f"B={ratio}n"] = {
            "bank": n * ratio,
            "repeats_per_pass": _repeats(n, n * ratio),
            "probes_median": statistics.median(stats["probes"]),
            "days_one_hotkey": statistics.median(stats["probes"]) / DRAWS_PER_DAY,
            "gain_median": statistics.median(stats["gain"]),
            "ceiling_gain_median": statistics.median(stats["ceiling"]),
            "coverage_of_P_median": statistics.median(stats["coverage"]),
            "gate_fail_when_exploiting": statistics.median(stats["gate_fail"]),
        }
    return {"n": n, "cells": f"{bins}^4", "by_bank": rows}


def _q3(rng, n=8, bins=16):
    rows = {}
    cells_all = list(itertools.product(range(bins), repeat=2))

    def point():
        return {
            "t_amb_c": rng.uniform(*ql.BOUNDS["t_amb_c"]),
            "soc0": rng.uniform(*ql.BOUNDS["soc0"]),
        }

    def cell_of(x):
        return ql._cell(x["inputs"], ("t_amb_c", "soc0"), bins)

    for ratio in RATIOS:
        probes, free, ceiling, fails = [], [], [], []
        for _ in range(REPLICATES):
            bank = [{"inputs": point(), "damage": True} for _ in range(n * ratio)]
            occupied = {cell_of(x) for x in bank}
            ceiling.append(1 - len(occupied) / len(cells_all))
            # The attacker probes every cell of the condition plane.
            p, clean, fail = _attack(rng, bank, cell_of, n, cells_all)
            free.append(len(clean) / len(cells_all))
            probes.append(p)
            fails.append(fail)
        rows[f"B={ratio}n"] = {
            "bank": n * ratio,
            "repeats_per_pass": _repeats(n, n * ratio),
            "probes_median": statistics.median(probes),
            "days_one_hotkey": statistics.median(probes) / DRAWS_PER_DAY,
            "free_condition_share_median": statistics.median(free),
            "ceiling_free_share_median": statistics.median(ceiling),
            "gate_fail_when_exploiting": statistics.median(fails),
        }
    return {"n": n, "cells": f"{bins}^2", "by_bank": rows}


def _exposure():
    rows = {}
    for ratio in (2, 5, 10, 20):
        p = 1 / ratio
        rows[f"B={ratio}n"] = {
            "seen_after_draws": {
                str(draws): 1 - (1 - p) ** draws for draws in (1, 5, 20, 140, 600)
            },
            "mean_appearances_per_case_per_day": DRAWS_PER_DAY * p,
            "days_to_k_appearances": {
                str(k): k / (DRAWS_PER_DAY * p) for k in (3, 5, 10, 20)
            },
        }
    return {
        "draws_per_day_per_validator": DRAWS_PER_DAY,
        "rule": "retire a case after k appearances, then publish it to "
        "training; steady state needs n / k new cases per draw",
        "by_bank": rows,
    }


def _power(rng, parents):
    """P(a subtle optimist's pooled false-feasible exceeds an honest
    member's) over W batches: fixed quiz vs fresh draws from a bank."""
    n = 80
    bank = _bootstrap(rng, parents, 20 * n)
    honest = [x["bad"] and rng.random() < 0.05 for x in bank]
    subtle = [x["damage"] and rng.random() < 0.15 for x in bank]
    bad_idx = [i for i, x in enumerate(bank) if x["bad"]]
    rate_h = sum(honest[i] for i in bad_idx) / len(bad_idx)
    rate_s = sum(subtle[i] for i in bad_idx) / len(bad_idx)
    out = {"honest_ff": rate_h, "subtle_ff": rate_s}
    for mode in ("fixed", "random"):
        row = {}
        for w in (1, 2, 4, 8, 16):
            wins = 0.0
            for _ in range(1000):
                quizzes = []
                first = rng.choice(len(bank), n, replace=False)
                for b in range(w):
                    quizzes.append(
                        first
                        if mode == "fixed" or b == 0
                        else rng.choice(len(bank), n, replace=False)
                    )
                cases = [i for q in quizzes for i in q if bank[i]["bad"]]
                if not cases:
                    continue
                hs = sum(honest[i] for i in cases)
                ss = sum(subtle[i] for i in cases)
                wins += (ss > hs) + 0.5 * (ss == hs)
            row[f"W{w}"] = wins / 1000
        out[mode] = row
    return out


def _sizing():
    # Per-batch draw sizes and solves per drawn item (public registries).
    families = {
        "battery_pool": (120, 1, "confirmation set size; 1 solve per case"),
        "battery_Q2": (80, 1, "quiz-registry v3/v5"),
        "battery_Q3": (8, 117, "117-point lattice; 52-62 with coarse-then-refine"),
        "motor_pool": (60, 1, "confirmation set size"),
        "motor_Q3": (8, 48, "8 candidates x 6 conditions per task"),
        "cooling_pool": (60, 1, "confirmation set size; cooling quiz not yet defined"),
    }
    rows = {}
    for name, (n, solves, note) in families.items():
        rows[name] = {
            "n": n,
            "solves_per_item": solves,
            "note": note,
            "bank_solves": {str(r): n * r * solves for r in (5, 10, 20)},
            "replenish_solves_per_day_per_validator": {
                str(k): DRAWS_PER_DAY * n / k * solves for k in (5, 10, 20)
            },
        }
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(prog="quiz_bank")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    rng = np.random.default_rng(20261007)
    population = _population()
    near = [x for x in population if x["near"]]
    document = {
        "schema": "carbon.battery.quiz-bank.v1",
        "source": "PUBLIC_STANDIN (see module docstring)",
        "population": len(population),
        "near_pool": len(near),
        "Q2": _family(rng, "Q2", near, 80, 4, near),
        "pool": _family(rng, "pool", population, 120, 4, population),
        "Q3": _q3(rng),
        "exposure": _exposure(),
        "power_pooled": _power(rng, near),
        "sizing": _sizing(),
    }
    args.out.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(json.dumps(document, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
