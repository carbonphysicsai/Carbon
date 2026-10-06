"""Run SR-B1 (battery score candidates) on its two registered panels.

    python -m scripts.dev.battery.srb1 --run5 DIR --ev4 DIR --out RESULT.json

`--run5` is the graphite-run5 Q1 output directory (#609). `--ev4` is the
SR-B1 EV4 CPU rebuild directory (`srb1_ev4_rebuild`). Definitions were
registered in `.agent/tickets/SR-B1_battery_score_candidates.md` before
computing. The script is CPU only and spends nothing.
"""

from __future__ import annotations

import argparse
import gzip
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.battery.value import panel as value_panel
from carbon.battery.value import score_candidates_b1 as b1
from carbon.battery.value import scoring as sc
from carbon.battery.value.contract import load

EV4_CONTRACT = (
    ROOT / "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
)
RUN5_CONTRACT = (
    ROOT
    / "carbon/battery/value/contracts/graphite-run5-charge-protocol-selection.v1.json"
)
BUNDLED = "graphite-run5-p-1d4aaff5d292"
D_T24 = "D-T24-S0.12"


def _bundle(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()))["predictions"]


def _mask_values(results, members):
    decisions = results["decisions"]
    development = sorted(
        {
            s
            for m in members
            for s, v in decisions[m].items()
            if v["split"] == "development"
        }
    )
    mask = [
        s
        for s in development
        if all(decisions[m][s]["outcome"]["decision_loss"] is not None for m in members)
    ]
    values = {
        m: (
            statistics.fmean(decisions[m][s]["outcome"]["decision_loss"] for s in mask)
            if mask
            else None
        )
        for m in members
    }
    return values, {"development": len(development), "common_resolved": len(mask)}


def run5(directory):
    directory = Path(directory)
    contract, _ = load(RUN5_CONTRACT)
    results = json.loads(
        (directory / "experiment/results/results.json").read_text("utf-8")
    )
    report = json.loads((directory / "q1-report.json").read_text("utf-8"))
    members = list(report["members"])
    recipe_of = {m: report["members"][m]["recipe"] for m in members}
    one_seed = [m for m in members if report["members"][m]["first_seed"]]
    predictions = {
        m: _bundle(directory / "predictions" / f"{m}.json.gz") for m in members
    }
    values, mask = _mask_values(results, members)
    base, notes = b1.member_scores(contract, results, predictions, members, ROOT)
    table = b1.candidate_scores(base, recipe_of)
    stats, panels = b1.analyse(table, values, recipe_of, members, one_seed)
    bundled = next(m for m in one_seed if m.startswith(BUNDLED))
    pickers = sorted(
        m
        for m in members
        if results["decisions"][m][D_T24]["outcome"]["kind"] == "SELECTED_INFEASIBLE"
    )

    def rank(scores, pool, member):
        order = sorted(
            (m for m in pool if scores[m] is not None), key=lambda m: (-scores[m], m)
        )
        return order.index(member) + 1 if member in order else None

    def failed(c, m):
        gate = c.split("+", 1)[1] if "+" in c else None
        return gate is not None and base[m][gate]["verdict"] == "FAIL"

    baseline = next(m for m in one_seed if "baseline" in m)
    catch = {
        c: {
            "bundled_rank_one_seed": rank(table[c], one_seed, bundled),
            "one_seed_n": len(one_seed),
            "bundled_failed_gate": failed(c, bundled),
            "baseline_failed_gate": failed(c, baseline),
            "d_t24_pickers_failed_gate": sum(1 for m in pickers if failed(c, m)),
            "gate_failures_all": sum(1 for m in members if failed(c, m)),
            "d_t24_pickers_mean_rank_all": statistics.fmean(
                rank(table[c], members, m) for m in pickers
            ),
            "n_all": len(members),
        }
        for c in b1.CANDIDATES
    }
    return {
        "members": len(members),
        "recipes": len(set(recipe_of.values())),
        "mask": mask,
        "panels": panels,
        "notes": notes,
        "gates": {m: {g: base[m][g] for g in ("G1", "G2")} for m in members},
        "d_t24_pickers": len(pickers),
        "candidates": stats,
        "catch": catch,
    }


def ev4(directory):
    directory = Path(directory)
    contract, _ = load(EV4_CONTRACT)
    results = json.loads(
        (directory / "experiment/results/results.json").read_text("utf-8")
    )
    store, _ids, _ = sc.scoring_set(ROOT)
    summary = results["summary"]["members"]
    members = sorted(summary)
    first = {label: seeds[0] for label, _s, seeds in value_panel.PANELS["ev4"]}
    recipe_of, one_seed, predictions = {}, [], {}
    for m in members:
        if summary[m]["kind"] == "SYNTHETIC_CONTROL":
            recipe_of[m] = m
            one_seed.append(m)
            predictions[m] = value_panel.control_predictions(
                m.removeprefix("control-"), store.refs
            )
            continue
        label, seed = m.rsplit("-s", 1)
        recipe_of[m] = label
        if int(seed) == first[label]:
            one_seed.append(m)
        predictions[m] = _bundle(directory / "experiment/predictions" / f"{m}.json.gz")
    values, mask = _mask_values(results, members)
    base, notes = b1.member_scores(contract, results, predictions, members, ROOT)
    table = b1.candidate_scores(base, recipe_of)
    stats, panels = b1.analyse(table, values, recipe_of, members, one_seed)
    return {
        "members": len(members),
        "recipes": len(set(recipe_of.values())),
        "mask": mask,
        "panels": panels,
        "notes": notes,
        "candidates": stats,
        "rebuild": "CPU on the operator host; not bit-identical to EV4's A40 bundles",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run5", type=Path, required=True)
    parser.add_argument("--ev4", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = {
        "schema": "carbon.battery.score-candidates-b1.v1",
        "registration": ".agent/tickets/SR-B1_battery_score_candidates.md (commit 7c355f2f)",
        "candidates": list(b1.CANDIDATES),
        "graphite_run5": run5(args.run5),
        "ev4": ev4(args.ev4),
        "claims": (
            "descriptive DEVELOPMENT evidence on EV4 development conditions "
            "(previously used); nothing adopted; EV5 untouched"
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for panel in ("graphite_run5", "ev4"):
        print(panel)
        for c, v in result[panel]["candidates"].items():
            print(
                f"  {c:9s} tau1={v['tau_one_seed']} tauAll={v['tau_all']} "
                f"band={v['tau_seed_band']} dCE={v['delta_tau_vs_CE']} "
                f"dSR2={v['delta_tau_vs_SR2']} div={v['divergence_count']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
