"""Quiz producer-load analysis memo (public stand-in only; not a registration).

    python -m scripts.dev.battery.quiz_load probe --out probe.json
    python -m scripts.dev.battery.quiz_load coarse_refine --predictions DIR \
        --out coarse-refine.json

`probe`: if a quiz stays fixed, how many binary-feedback submissions does a
miner need to find where it may be optimistic without failing the quiz gate?
It also covers the benefit of a shared quiz, and a canary detector.

`coarse_refine`: Option 4. Solve EV4's 35-point grid, then refine to the
117-point lattice only around anchors: the coarse oracle optimum, each panel
pick and the limit-band points. Gives the solve count and agreement with the
full lattice, as quiz-diagnostics-v1 (b) re-run.
"""

from __future__ import annotations

import argparse
import gzip
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

CONTRACT = ROOT / "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
BOUNDS = {
    "c1": (0.5, 2.0),
    "c2": (0.2, 1.0),
    "t_amb_c": (5.0, 40.0),
    "soc0": (0.05, 0.5),
}
REPLICATES = 200
#: One scored submission per hotkey per tempo; Bittensor's default tempo
#: (360 blocks of 12 s) gives 20 a day. A subnet's tempo can differ.
TEMPOS_PER_DAY = 20


# --- probe -----------------------------------------------------------------------------


def _cell(inputs, names, bins):
    out = []
    for name in names:
        low, high = BOUNDS[name]
        out.append(min(bins - 1, int((inputs[name] - low) / (high - low) * bins)))
    return tuple(out)


def _splitting_tests(cells, defective):
    """Adaptive binary splitting: tests needed to classify every cell when a
    test reports only whether a group holds a defective cell (pass/fail)."""
    tests = 0

    def solve(group, known_bad=False):
        nonlocal tests
        if not known_bad:
            tests += 1
            if not any(c in defective for c in group):
                return
        if len(group) == 1:
            return
        half = len(group) // 2
        left, right = group[:half], group[half:]
        tests += 1
        if any(c in defective for c in left):
            solve(left, known_bad=True)
            solve(right)
        else:
            solve(right, known_bad=True)

    solve(list(cells))
    return tests


def _log2_comb(n, k):
    return (
        math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    ) / math.log(2)


def _one_sided_fisher(a, n1, b, n2):
    """P(quiz count <= a | margins), with quiz a of n1 and canary b of n2:
    small when the quiz shows fewer failures than the canary."""
    total = a + b
    denom = math.comb(n1 + n2, total)
    return (
        sum(
            math.comb(n1, i) * math.comb(n2, total - i)
            for i in range(max(0, total - n2), min(a, n1) + 1)
        )
        / denom
    )


def probe(out):
    from carbon.battery.value import contract as ev
    from carbon.battery.value import decision as d
    from carbon.battery.value import panel as pn
    from carbon.battery.value import quiz
    from carbon.battery.value import scoring as sc

    contract, _ = ev.load(CONTRACT)
    store, ids, _ = sc.scoring_set(ROOT)
    bands = contract["reference"]["uncertainty"]["bands"]
    pool = [c for c in ids if quiz.q2_near(contract, store.refs[c])]
    optimist = pn.control_predictions("boundary_optimist", store.refs)

    def infeasible(c):
        truth = d.check(contract, d.measure(contract, store.refs[c]["outputs"]), bands)
        return any(v == d.FAIL for v in truth.values())

    bad = {c for c in pool if infeasible(c)}
    damage = {c for c in bad if quiz._feasible_call(contract, optimist[c])[0]}
    rng = np.random.default_rng(20261007)
    names = ("c1", "c2", "t_amb_c", "soc0")
    q2 = {}
    for bins in (2, 3, 4, 6, 8):
        cell_of = {c: _cell(store.refs[c]["inputs"], names, bins) for c in pool}
        cells = sorted(set(cell_of.values()))
        tests, defect, gain, quiz_ff, bound = [], [], [], [], []
        for _ in range(REPLICATES):
            chosen = rng.permutation(pool)
            q, canary = set(chosen[: quiz.Q2_N]), chosen[quiz.Q2_N : 2 * quiz.Q2_N]
            defective = {cell_of[c] for c in q if c in damage}
            order = [cells[i] for i in rng.permutation(len(cells))]
            tests.append(_splitting_tests(order, defective))
            defect.append(len(defective))
            bound.append(_log2_comb(len(cells), len(defective)))
            # After learning: optimistic in clean cells, accurate elsewhere.
            rest_bad = [c for c in pool if c not in q and c in bad]
            caught = [
                c for c in rest_bad if c in damage and cell_of[c] not in defective
            ]
            gain.append(len(caught) / len(rest_bad) if rest_bad else 0.0)
            canary_bad = [c for c in canary if c in bad]
            quiz_ff.append(
                sum(c in damage and cell_of[c] not in defective for c in canary_bad)
                / len(canary_bad)
                if canary_bad
                else 0.0
            )
        q2[f"cells_{bins}^4"] = {
            "cells_with_pool_cases": len(cells),
            "defective_cells_median": statistics.median(defect),
            "info_bound_bits_median": statistics.median(bound),
            "probes_median": statistics.median(tests),
            "probes_p90": float(np.quantile(tests, 0.9)),
            "exam_false_feasible_gained_median": statistics.median(gain),
            "fresh_quiz_false_feasible_median": statistics.median(quiz_ff),
        }
    # Q3: 8 scenario conditions, uniform over the envelope; the attacker must
    # avoid every quiz condition's cell (worst case for the defender).
    q3 = {}
    for bins in (4, 8, 16, 32):
        cells = list(itertools.product(range(bins), repeat=2))
        tests, clean = [], []
        for _ in range(REPLICATES):
            points = [
                {
                    "t_amb_c": rng.uniform(*BOUNDS["t_amb_c"]),
                    "soc0": rng.uniform(*BOUNDS["soc0"]),
                }
                for _ in range(quiz.Q3_K)
            ]
            defective = {_cell(p, ("t_amb_c", "soc0"), bins) for p in points}
            order = [cells[i] for i in rng.permutation(len(cells))]
            tests.append(_splitting_tests(order, defective))
            clean.append(1 - len(defective) / len(cells))
        q3[f"cells_{bins}^2"] = {
            "probes_median": statistics.median(tests),
            "probes_p90": float(np.quantile(tests, 0.9)),
            "free_condition_share_median": statistics.median(clean),
        }
    # Shared-quiz benefit: how often two members with close false-feasible
    # rates are ordered as on the whole pool, when both face the same 80
    # cases (paired) or independent draws (unpaired). The second member is
    # the optimist made optimistic on a random 70 % of its damage cases.
    keep = set(rng.choice(sorted(damage), int(0.7 * len(damage)), replace=False))

    def ff(member, cases):
        cases = [c for c in cases if c in bad]
        hits = damage if member == "optimist" else keep
        return sum(c in hits for c in cases) / len(cases) if cases else 0.0

    paired, unpaired = [], []
    for _ in range(2000):
        a = list(rng.choice(pool, quiz.Q2_N, replace=False))
        b = list(rng.choice(pool, quiz.Q2_N, replace=False))
        paired.append(ff("optimist", a) > ff("milder", a))
        unpaired.append(ff("optimist", a) > ff("milder", b))
    # Canary detector: each submission also scored, unreported, on a disjoint
    # near-limit canary of the same size; flag when the quiz shows clearly
    # fewer false-feasibles than the canary (one-sided Fisher, alpha 0.01).
    detector = {}
    n_bad = round(quiz.Q2_N * len(bad) / len(pool))
    for label, quiz_rate, canary_rate in (
        ("honest_p0.05", 0.05, 0.05),
        ("honest_p0.20", 0.20, 0.20),
        ("fitted_attacker", 0.0, q2["cells_3^4"]["fresh_quiz_false_feasible_median"]),
    ):
        flags = 0
        for _ in range(2000):
            a = rng.binomial(n_bad, quiz_rate)
            b = rng.binomial(n_bad, canary_rate)
            flags += _one_sided_fisher(a, n_bad, b, n_bad) < 0.01
        detector[label] = {"flag_rate": flags / 2000}
    document = {
        "schema": "carbon.battery.quiz-load-probe.v1",
        "source": "PUBLIC_STANDIN: the scoring set's near-limit pool (4 bands); "
        "quiz = 80 random pool cases (the panel split is not modelled); "
        "attacker = boundary_optimist, accurate elsewhere; gate = no "
        "false-feasible on the quiz (tau = 0; tau > 0 only helps the attacker)",
        "pool": len(pool),
        "pool_infeasible": len(bad),
        "optimist_damage_cases": len(damage),
        "tempos_per_day_per_hotkey": TEMPOS_PER_DAY,
        "q2": q2,
        "q3": q3,
        "shared_quiz": {
            "members": "boundary_optimist vs the same made optimistic on 70 % "
            "of its damage cases (pool false-feasible "
            f"{len(damage) / len(bad):.3f} vs {len(keep) / len(bad):.3f})",
            "correct_order_paired": statistics.fmean(paired),
            "correct_order_unpaired": statistics.fmean(unpaired),
        },
        "canary_detector": {"quiz_infeasible_cases": n_bad, **detector},
    }
    Path(out).write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    return document


# --- coarse_refine ---------------------------------------------------------------------


def coarse_refine(predictions_dir, out):
    from carbon.battery.value import contract as ev
    from carbon.battery.value import decision as d
    from carbon.battery.value import quiz
    from scripts.dev.battery import grid_resolution as gr

    contract, refs = gr._load()
    scenarios = gr.pool(contract, refs)
    lattice = quiz.q3_candidates()
    by_id = {c["id"]: c for c in lattice}
    coarse = {c["id"]: c for c in ev.candidates(contract)}
    bands = contract["reference"]["uncertainty"]["bands"]
    refined_path = (
        ROOT / "docs/development/evidence/battery-quiz-designs/grid-resolution-v1/"
        "refined-references.jsonl.gz"
    )
    solved = {}
    for line in gzip.decompress(refined_path.read_bytes()).decode().splitlines():
        if line.strip():
            record = json.loads(line)
            solved[record["case_id"]] = record
    judged = json.loads(
        (
            ROOT / "docs/development/evidence/battery-quiz-designs/grid-resolution-v1/"
            "selection.json"
        ).read_text()
    )["reference_judged"]
    members = sorted(
        p.name[: -len(".json.gz")] for p in Path(predictions_dir).glob("*.json.gz")
    )
    preds = {
        m: json.loads(
            gzip.decompress((Path(predictions_dir) / f"{m}.json.gz").read_bytes())
        )
        for m in members
    }

    def record(scenario, cid):
        if cid in coarse:
            return refs.get(ev.case_id(contract, scenario, coarse[cid], 0))
        return solved.get(gr._case(scenario["id"], by_id[cid]))

    def verdict(scenario, cid):
        if cid is None:
            return "ABSTAIN"
        r = record(scenario, cid)
        if not r or r.get("status") != "OK":
            return "REFERENCE_UNAVAILABLE"
        checks = d.check(contract, d.measure(contract, r["outputs"]), bands)
        if any(v == d.FAIL for v in checks.values()):
            return "INFEASIBLE"
        if any(v == d.UNRESOLVED for v in checks.values()):
            return "UNRESOLVED"
        return "FEASIBLE"

    def best(scenario, ids):
        cands = [by_id[i] for i in sorted(ids)]
        rr = {}
        for c in cands:
            r = record(scenario, c["id"])
            if r:
                rr[(c["id"], 0)] = r
        assessed = d.assess_reference(contract, scenario, cands, rr)
        chosen = d.best_in_set(cands, assessed)
        return chosen["id"] if isinstance(chosen, dict) else chosen

    def pick(member, scenario):
        chosen = gr._pick(contract, scenario, lattice, preds[member])
        if chosen in (None, "MISSING"):
            return None
        return chosen.get("id") if isinstance(chosen, dict) else chosen

    picks = {(m, s["id"]): pick(m, s) for m in members for s in scenarios}

    def near_limit(scenario, cid):
        r = record(scenario, cid)
        if not r or r.get("status") != "OK":
            return False
        return (
            min(abs(v) for v in quiz._band_margins(contract, r["outputs"]).values())
            <= 1
        )

    def hood(anchor, radius):
        a = by_id[anchor]
        dc1, dc2 = (0.25, 0.2) if radius == "r1" else (0.125, 0.1)
        return {
            c["id"]
            for c in lattice
            if abs(c["c1"] - a["c1"]) <= dc1 + 1e-9
            and abs(c["c2"] - a["c2"]) <= dc2 + 1e-9
        }

    results = {}
    for radius in ("r_half", "r1"):
        counts, covered, total = [], 0, 0
        judged_rows = []
        for s in scenarios:
            full = s["id"] in judged
            limit_points = [cid for cid in coarse if near_limit(s, cid)]
            for loo in members:
                anchors = set(limit_points)
                anchors.add(best(s, coarse))
                anchors |= {picks[(m, s["id"])] for m in members if m != loo} - {None}
                ids = set(coarse)
                for a in anchors:
                    ids |= hood(a, radius)
                rounds = 0
                while full:
                    rounds += 1
                    b = best(s, ids)
                    grow = (hood(b, radius) if b else set()) - ids
                    if not grow:
                        break
                    ids |= grow
                if loo == members[0]:
                    counts.append(len(ids))
                p = picks[(loo, s["id"])]
                total += 1
                hit = p is None or p in ids
                covered += hit
                if full:
                    v_full = verdict(s, p)
                    v_cr = v_full if hit else "UNRESOLVED_BACKSTOP"
                    judged_rows.append(
                        {
                            "scenario": s["id"],
                            "member": loo,
                            "pick": p,
                            "covered": hit,
                            "verdict_full": v_full,
                            "verdict_coarse_refine": v_cr,
                            "optimum_full": best(s, set(by_id)),
                            "optimum_coarse_refine": best(s, ids),
                            "oracle_rounds": rounds,
                        }
                    )
        results[radius] = {
            "solves_per_condition_mean": statistics.fmean(counts),
            "solves_per_condition_max": max(counts),
            "full_lattice": len(lattice),
            "pick_coverage_leave_one_out": covered / total,
            "decisions": total,
            "judged": {
                "decisions": len(judged_rows),
                "verdict_matches": sum(
                    r["verdict_full"] == r["verdict_coarse_refine"] for r in judged_rows
                ),
                "optimum_matches": sum(
                    r["optimum_full"] == r["optimum_coarse_refine"] for r in judged_rows
                ),
                "uncovered": [r for r in judged_rows if not r["covered"]],
            },
        }
    document = {
        "schema": "carbon.battery.quiz-coarse-refine.v1",
        "source": "PUBLIC_STANDIN: quiz-diagnostics-v1 (b) data; EV4's 9 "
        "verification scenarios with a feasible design; 26 members' 117-point "
        "picks; full 117 references on the 2 judged scenarios",
        "anchors": "coarse-grid oracle optimum (re-anchored on the refined "
        "optimum until stable where references allow), every other member's "
        "pick (leave-one-out panel), coarse points within 1 band of a limit",
        "radii": {
            "r_half": "lattice points within one lattice step (0.125 C, 0.1 C)",
            "r1": "lattice points within one coarse step (0.25 C, 0.2 C)",
        },
        "results": results,
    }
    Path(out).write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    return document


def main(argv=None):
    parser = argparse.ArgumentParser(prog="quiz_load")
    parser.add_argument("command", choices=("probe", "coarse_refine"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--predictions", type=Path)
    args = parser.parse_args(argv)
    if args.command == "probe":
        document = probe(args.out)
    else:
        document = coarse_refine(args.predictions, args.out)
    print(json.dumps(document, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
