"""Compare the registered quiz designs (quiz-registry-v3) on the public stand-in.

    python -m scripts.dev.battery.quiz_designs --ev4 DIR --run5 DIR --attack DIR \
        --dev-results ev4-dev-tuning-v1-results.json --out RESULT.json

Each draw simulates a batch, a random half of the public scoring set. Each
design then picks `n` quiz cases from that batch:
- Q0: at random;
- Q1(k): at random among cases within k contract bands of the plating or
  peak-temperature limit;
- Q2: the cases within 4 bands where the public panel (EV4's recipes, first
  seeds) splits most evenly between calling them feasible and infeasible.

On the chosen cases, every member's G-FEAS measure (the share of
reference-infeasible cases it calls feasible) and G-PLATE measure (the share
of reference plating FAILs it calls PASS) are computed. Detection is the AUC
between the registered known-bad and known-good members. False-infeasible is
the known-good members' share of reference-feasible cases they call
infeasible. Everything was registered (commit 1871cbd0) before this ran.
Public stand-in only: the tuning set's quiz is chosen operator-side.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REGISTRY = ROOT / "docs/development/evidence/battery-quiz-designs/quiz-registry-v3.json"
CONTRACT = ROOT / "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
WINNER = "graphite-run5-p-1d4aaff5d292-s3718551111"
TRACK_A_BAD = (
    "attack_rebuild_identity_backbone_a-s0",
    "attack_rebuild_identity_backbone_b-s0",
    "attack_rebuild_identity_optimizer_a-s0",
    "attack_rebuild_identity_steps_a-s0",
    "attack_rebuild_identity_steps_b-s0",
    "attack_rebuild_identity_train_fraction_a-s0",
    "attack_rebuild_identity_width_a-s0",
    "attack_rebuild_identity_width_b-s0",
)
GOOD_CONTROLS = (
    "control-oracle",
    "control-conservative",
    "control-rank_preserving_delay",
)


def _bundles(dirs):
    out = {}
    for directory in dirs:
        for path in sorted(Path(directory).glob("*.json.gz")):
            bundle = json.loads(gzip.decompress(path.read_bytes()))
            out[bundle["member"]] = bundle["predictions"]
    return out


def calls(contract, store, ids, predictions):
    """Per-case reference calls and margins, and each member's calls."""
    from carbon.battery.value import decision as d
    from carbon.battery.value import margins

    bands = contract["reference"]["uncertainty"]["bands"]
    ref_fail, ref_pass, ref_plate_fail, near = [], [], [], []
    for c in ids:
        truth = d.check(contract, d.measure(contract, store.refs[c]["outputs"]), bands)
        ref_fail.append(any(v == d.FAIL for v in truth.values()))
        ref_pass.append(all(v == d.PASS for v in truth.values()))
        ref_plate_fail.append(truth["no_plating_onset"] == d.FAIL)
        m = margins._margins(contract, store.refs[c]["outputs"])
        near.append(min(abs(v) for v in m.values()))
    member = {}
    for name, preds in predictions.items():
        feasible, plate_pass = [], []
        for c in ids:
            out = preds.get(c)
            if out is None:
                feasible.append(np.nan)
                plate_pass.append(np.nan)
                continue
            said = d.check(contract, d.measure(contract, out))
            feasible.append(float(all(v == d.PASS for v in said.values())))
            plate_pass.append(float(said["no_plating_onset"] == d.PASS))
        member[name] = (np.array(feasible), np.array(plate_pass))
    return (
        np.array(ref_fail),
        np.array(ref_pass),
        np.array(ref_plate_fail),
        np.array(near),
        member,
    )


def _rate(numerator_mask, denominator_mask):
    den = denominator_mask.sum()
    return (
        None
        if den == 0 or np.isnan(numerator_mask).any()
        else float(numerator_mask.sum() / den)
    )


def _auc(bad, good):
    bad = [b for b in bad if b is not None]
    good = [g for g in good if g is not None]
    if not bad or not good:
        return None
    wins = sum((b > g) + 0.5 * (b == g) for b in bad for g in good)
    return wins / (len(bad) * len(good))


def evaluate(
    registry, ref_fail, ref_pass, ref_plate_fail, near, member, panel, bad, good
):
    metric = registry["metric"]
    rng = np.random.default_rng(20261006)
    n_cases = len(ref_fail)
    # Panel disagreement per case: how evenly the public panel splits.
    panel_feasible = np.nanmean(np.vstack([member[m][0] for m in panel]), axis=0)
    disagreement = -np.abs(panel_feasible - 0.5)
    designs = []
    for design in registry["designs"]:
        if design["kind"] == "near_band":
            designs += [(f"Q1@{k:g}", "near_band", k) for k in design["margins_bands"]]
        elif design["kind"] == "panel_disagreement":
            designs.append(("Q2", "panel_disagreement", design["pool_margin_bands"]))
        else:
            designs.append(("Q0", "random", None))
    out = {}
    for name, kind, k in designs:
        for n in registry["sizes"]:
            aucs = {"feasibility": [], "plating_fa": []}
            false_infeasible, short = [], 0
            for _ in range(metric["draws"]):
                batch = rng.choice(n_cases, n_cases // 2, replace=False)
                if kind == "random":
                    pool = batch
                else:
                    pool = batch[near[batch] <= k]
                if len(pool) < n:
                    short += 1
                    continue
                if kind == "panel_disagreement":
                    chosen = pool[np.argsort(-disagreement[pool], kind="stable")[:n]]
                else:
                    chosen = rng.choice(pool, n, replace=False)
                rf, rp, rpl = ref_fail[chosen], ref_pass[chosen], ref_plate_fail[chosen]

                def measures(m, chosen=chosen, rf=rf, rpl=rpl, rp=rp):
                    feas, plate = member[m][0][chosen], member[m][1][chosen]
                    return (
                        _rate(feas * rf, rf),
                        _rate(plate * rpl, rpl),
                        _rate((1 - feas) * rp, rp),
                    )

                bad_m = [measures(m) for m in bad]
                good_m = [measures(m) for m in good]
                for i, key in enumerate(("feasibility", "plating_fa")):
                    value = _auc([b[i] for b in bad_m], [g[i] for g in good_m])
                    if value is not None:
                        aucs[key].append(value)
                fi = [g[2] for g in good_m if g[2] is not None]
                if fi:
                    false_infeasible.append(float(np.mean(fi)))
            out[f"{name}/n{n}"] = {
                "design": name,
                "n": n,
                "draws_short_of_cases": short,
                **{
                    f"auc_{key}": (
                        None
                        if not v
                        else {
                            "mean": float(np.mean(v)),
                            "p05": float(np.quantile(v, 0.05)),
                        }
                    )
                    for key, v in aucs.items()
                },
                "false_infeasible_mean": (
                    None if not false_infeasible else float(np.mean(false_infeasible))
                ),
            }
    return out


def sizing(results, registry):
    """The smallest size per design whose p05 AUC reaches 0.9 on both."""
    out = {}
    for row in results.values():
        both = all(
            row[f"auc_{key}"] is not None and row[f"auc_{key}"]["p05"] >= 0.9
            for key in ("feasibility", "plating_fa")
        )
        if both and row["draws_short_of_cases"] == 0:
            best = out.get(row["design"])
            if best is None or row["n"] < best:
                out[row["design"]] = row["n"]
    return out


def main(argv=None):
    from carbon.battery.value import panel as pn
    from carbon.battery.value import scoring as sc
    from carbon.battery.value.contract import load

    parser = argparse.ArgumentParser(prog="quiz_designs")
    parser.add_argument("--ev4", type=Path, required=True)
    parser.add_argument("--run5", type=Path, required=True)
    parser.add_argument("--attack", type=Path, required=True)
    parser.add_argument("--dev-results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    registry = json.loads(REGISTRY.read_text())
    contract, _ = load(CONTRACT)
    store, ids, _ = sc.scoring_set(ROOT)
    predictions = _bundles([args.ev4, args.run5, args.attack])
    for kind in pn.CONTROLS:
        predictions["control-" + kind] = pn.control_predictions(kind, store.refs)
    ref_fail, ref_pass, ref_plate_fail, near, member = calls(
        contract, store, ids, predictions
    )
    first = {label: seeds[0] for label, _s, seeds in pn.PANELS["ev4"]}
    ev4_members = [m for m, *_ in pn.members("ev4")]
    panel = [
        m
        for m in ev4_members
        if int(m.rsplit("-s", 1)[1]) == first[m.rsplit("-s", 1)[0]] and m in member
    ]
    results = json.loads(args.dev_results.read_text())
    values = {
        m: results["summary"]["members"][m]["loss_development"]
        for m in ev4_members
        if m in results["summary"]["members"]
        and results["summary"]["members"][m]["loss_development"] is not None
    }
    best_quarter = sorted(values, key=lambda m: (values[m], m))[
        : max(1, len(values) // 4)
    ]
    bad = [m for m in (*TRACK_A_BAD, WINNER) if m in member]
    good = [m for m in (*GOOD_CONTROLS, *best_quarter) if m in member]
    rows = evaluate(
        registry, ref_fail, ref_pass, ref_plate_fail, near, member, panel, bad, good
    )
    document = {
        "schema": "carbon.battery.quiz-design-comparison.v1",
        "registry_commit": "1871cbd0",
        "source": "PUBLIC_STANDIN: the public scoring set; not the tuning set",
        "cases": len(ids),
        "near_limit_cases": {
            f"<= {k:g} bands": int((near <= k).sum()) for k in (0.5, 1, 2, 4)
        },
        "known_bad": bad,
        "known_good": {
            "controls": list(GOOD_CONTROLS),
            "best_quarter": len(best_quarter),
        },
        "results": rows,
        "sizing": sizing(rows, registry),
    }
    args.out.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "sizing": document["sizing"],
                "near_limit_cases": document["near_limit_cases"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
