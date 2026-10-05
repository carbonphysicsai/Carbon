"""Analyse the Graphite run-5 battery Q1 panel (see graphite_run5_alignment).

1. Freeze the `graphite-run5` contract in a fresh `Experiment` root.
2. Import EV4's committed decision references (no new solves).
3. Import the CPU-rebuilt prediction bundles and evaluate.
4. Relate each member's CPU practice score (rule v2, the same rebuilt
   artifact) to its development decision loss on the common resolved
   scenario mask.

The one-seed result (each recipe's original seed) is reported first. Then
come the three-seed result with recipe-level bands, the pod-score secondary
line, the pod-to-CPU rank drift and the seed-luck evidence about the rule.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from carbon.battery.value import panel as value_panel
from carbon.design_search import score_value

from .graphite_run5_alignment import CONTRACT, EV4_REFERENCES, PANEL, ROOT

POD_SCORES = "pod-scores.json"


def _experiment(out):
    import gzip
    import hashlib

    from carbon.battery.value.experiment import Experiment

    experiment = Experiment(out / "experiment", repository=ROOT)
    if not experiment.manifest_path.exists():
        experiment.freeze(CONTRACT)
    # EV4's references are committed gzipped; the plain bytes must match EV4's
    # own recorded checksum before they are imported.
    plain = gzip.decompress(EV4_REFERENCES.read_bytes())
    recorded = (EV4_REFERENCES.parent / "references.sha256").read_text().split()[0]
    if hashlib.sha256(plain).hexdigest() != recorded:
        raise SystemExit("EV4 decision references do not match references.sha256")
    unpacked = out / "ev4-decision-references.jsonl"
    unpacked.write_bytes(plain)
    experiment.import_references(unpacked)
    experiment.import_predictions(out / "predictions")
    experiment.evaluate()
    path = out / "experiment" / "results" / "results.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _recipe(member):
    return member.rsplit("-s", 1)[0]


def _near_false_acceptance(out, members):
    """Each member's near-limit false acceptance on the scoring set's
    important region (`near.near_cases`), from its own bundle."""
    import gzip

    from carbon.battery.value import false_acceptance, near
    from carbon.battery.value import scoring as sc
    from carbon.battery.value.contract import load

    contract, _ = load(CONTRACT)
    store, scoring_ids, _ = sc.scoring_set(ROOT)
    near_ids = near.near_cases(store, scoring_ids)
    refs = {c: store.refs[c] for c in near_ids}
    out_rows = {}
    for member in members:
        bundle = json.loads(
            gzip.decompress((out / "predictions" / f"{member}.json.gz").read_bytes())
        )
        out_rows[member] = false_acceptance.component(
            contract, bundle["predictions"], near_ids, refs
        )
    return {"near_cases": len(near_ids), "members": out_rows}


def analyse(out):
    out = Path(out)
    results = _experiment(out)
    members = [m for m, *_ in value_panel.members(PANEL)]
    first_seed = {label: seeds[0] for label, _s, seeds in value_panel.PANELS[PANEL]}
    practice = {
        m: json.loads((out / "practice" / f"{m}.json").read_text("utf-8"))["summary"]
        for m in members
    }
    pod = json.loads((out / POD_SCORES).read_text(encoding="utf-8"))
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
    excluded = sorted(set(development) - set(mask))

    def value(m):
        losses = [decisions[m][s]["outcome"]["decision_loss"] for s in mask]
        return statistics.fmean(losses) if losses else None

    def kinds(m):
        counts = {}
        for s in mask:
            kind = decisions[m][s]["outcome"]["kind"]
            counts[kind] = counts.get(kind, 0) + 1
        return counts

    eligible = {m: results["summary"]["members"][m]["eligible"] for m in members}
    # Identity by rebuilt artifact (OWNER-GRAPHITE-TEST-WAVE-04 §1): a recipe
    # whose rebuild is byte-identical to another's at the same seed is that
    # recipe; its seeds become extra seeds of the target (`alias-check`).
    aliasing = json.loads((out / "aliasing.json").read_text(encoding="utf-8"))
    alias = {a["alias"]: a["target"] for a in aliasing if a["identical_predictions"]}

    def recipe(m):
        return alias.get(_recipe(m), _recipe(m))

    rows = {
        m: {
            "recipe": recipe(m),
            "graphite_proposal": _recipe(m),
            "seed": int(m.rsplit("-s", 1)[1]),
            "first_seed": _recipe(m) not in alias
            and int(m.rsplit("-s", 1)[1]) == first_seed[_recipe(m)],
            "cpu_practice_score": practice[m].get("score"),
            "cpu_practice_eligible": practice[m].get("eligible"),
            "development_decision_loss": value(m),
            "decision_kinds": kinds(m),
            "control_exam_v1": results["rule_scores"][m].get("control-exam-v1"),
            "eligible": eligible[m],
        }
        for m in members
    }

    def panel(selected, score_of):
        return score_value.alignment(
            {
                m: {
                    "score": -score_of(m),
                    "value": rows[m]["development_decision_loss"],
                    "eligible": rows[m]["eligible"] and score_of(m) is not None,
                    "recipe": rows[m]["recipe"],
                    "kind": "GRAPHITE_RECONSTRUCTED",
                }
                for m in selected
            },
            top_k=3,
        )

    one = [m for m in members if rows[m]["first_seed"]]
    primary_one = panel(one, lambda m: rows[m]["cpu_practice_score"])
    primary_all = panel(members, lambda m: rows[m]["cpu_practice_score"])
    secondary_pod = panel(one, lambda m: pod.get(rows[m]["recipe"]))

    def ranks(scores):
        order = sorted(scores, key=lambda k: (scores[k], k))
        return {k: i + 1 for i, k in enumerate(order)}

    pod_rank = ranks({rows[m]["recipe"]: pod[rows[m]["recipe"]] for m in one})
    cpu_rank = ranks({rows[m]["recipe"]: rows[m]["cpu_practice_score"] for m in one})
    drift = {
        r: {
            "pod_score": pod[r],
            "cpu_score": next(
                rows[m]["cpu_practice_score"] for m in one if rows[m]["recipe"] == r
            ),
            "pod_rank": pod_rank[r],
            "cpu_rank": cpu_rank[r],
        }
        for r in sorted(pod_rank)
    }
    bands = {}
    for recipe in sorted({rows[m]["recipe"] for m in members}):
        ms = [m for m in members if rows[m]["recipe"] == recipe]
        scores = [rows[m]["cpu_practice_score"] for m in ms]
        losses = [rows[m]["development_decision_loss"] for m in ms]
        bands[recipe] = {
            "practice_scores": scores,
            "practice_spread": max(scores) - min(scores),
            "decision_losses": losses,
            "decision_loss_spread": max(losses) - min(losses),
        }
    bundled = "graphite-run5-p-1d4aaff5d292"
    baseline = "graphite-run5-baseline"
    seed_luck = {
        "rule": "battery rule v2 paired comparison bootstraps over CASES, not seeds",
        "bundled": bands[bundled]["practice_scores"],
        "baseline": bands[baseline]["practice_scores"],
        "bundled_gap_first_seed": pod[bundled] - pod[baseline],
        "largest_single_recipe_seed_spread": max(
            b["practice_spread"] for b in bands.values()
        ),
        "condition": (
            "CANDIDATE_RULE_CONDITION: a single-seed practice score can move by "
            "more than the improvement gap, and best-of-N selection over one-seed "
            "scores can select on seed luck; evidence for the rule owner, no "
            "rule change"
        ),
    }
    near_fa = _near_false_acceptance(out, members)
    alias_report = [
        {
            **a,
            "alias_pod_score": pod.get(a["alias"]),
            "target_pod_score": pod.get(a["target"]),
            "observation": (
                "IDENTITY_ALIASING: different recipe digests, byte-identical "
                "rebuilt predictions at the same seed; the pod scores differ only "
                "by seed, so Graphite's step between them is seed variation"
                if a["identical_predictions"]
                else "distinct: predictions differ at the same seed"
            ),
        }
        for a in aliasing
    ]
    report = {
        "schema": "carbon.design-search.q1-graphite-run5.v1",
        "panel": PANEL,
        "conditions_label": "EV4 development conditions (previously used): development evidence, no confirmation claim",
        "score_source_primary": "CPU rebuild, battery rule v2 practice scoring on the 200 public PRACTICE cases (same artifact as the decisions)",
        "score_source_secondary": "Graphite pod practice scores (A40 rebuild), first seed only",
        "selection_bias": "practice cases were seen adaptively during Graphite's search; best-of-N selection bias applies",
        "mask": {
            "development_scenarios": len(development),
            "common_resolved": len(mask),
            "excluded": excluded,
            "rule": "every member scored on scenarios where every member's decision loss is defined; reference failure is never a candidate penalty",
        },
        "aliasing": alias_report,
        "n_one_seed": sum(1 for row in rows.values() if row["first_seed"]),
        "members": rows,
        "one_seed": primary_one,
        "three_seed": primary_all,
        "secondary_pod_scores_one_seed": secondary_pod,
        "rank_drift_pod_vs_cpu": drift,
        "recipe_bands": bands,
        "seed_luck": seed_luck,
        "near_limit_false_acceptance": near_fa,
        "experiment_results": "experiment/results/results.json",
    }
    target = out / "q1-report.json"
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main(out):
    report = analyse(out)
    print(
        json.dumps(
            {
                "one_seed_tau": report["one_seed"]["kendall_tau_b"],
                "one_seed_rho": report["one_seed"]["spearman_rho"],
                "three_seed_tau": report["three_seed"]["kendall_tau_b"],
                "tau_band": report["three_seed"]["tau_noise_band"],
                "conditions": len(report["three_seed"]["conditions"]),
                "mask": report["mask"]["common_resolved"],
            },
            indent=1,
        )
    )
    return 0
