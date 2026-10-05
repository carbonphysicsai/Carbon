"""Graphite run-5 Q1 follow-up: battery's defences, and the conditions report.

    python -m scripts.dev.battery.graphite_run5_alignment followup --out DIR

These are the Test Lead's 2026-10-05 follow-ups, development computations
only. EV5's modules are imported, never edited, and are never run on EV5's
conditions.

1. **Battery's defences on this panel.**
   - The near-limit optimism gate: `admissibility.near_optimism` and
     `verdict`, at cutoff 2.0 bands.
   - Kendall tau under the SR-2 candidate rule (`ev5.candidate_rule`, the
     `sr2-a0-r0.3-g0.6-m0.1` weights) against the deciding rule
     `control-exam-v1`, each with and without the gate.
   These show whether battery's planned fixes would have caught Graphite's
   winner. They are evidence for EV5's question, not a substitute for EV5.
2. **The conditions report**, `carbon.admission-conditions.v1`, in the shape
   `divergence.main` writes and `CampaignController.consume_conditions`
   accepts. Each condition is bound to the committed evidence by SHA-256. The
   controller's operator records it. This script never writes to a campaign
   store.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from carbon.battery.value import panel as value_panel
from carbon.design_search import score_value

from .graphite_run5_alignment import CONTRACT, PANEL, ROOT

EVIDENCE = ROOT / "docs/development/evidence/graphite-run5-q1"
BUNDLED = "graphite-run5-p-1d4aaff5d292"
BASELINE = "graphite-run5-baseline"


def _sha256(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def defences(out, report):
    from carbon.battery.value import admissibility, ev5, margins
    from carbon.battery.value import scoring as sc
    from carbon.battery.value.contract import load

    out = Path(out)
    contract, _ = load(CONTRACT)
    results = json.loads(
        (out / "experiment" / "results" / "results.json").read_text("utf-8")
    )
    store, scoring_ids, _ = sc.scoring_set(ROOT)
    members = [m for m, *_ in value_panel.members(PANEL)]
    predictions = {
        m: json.loads(
            gzip.decompress((out / "predictions" / f"{m}.json.gz").read_bytes())
        )["predictions"]
        for m in members
    }
    candidate = ev5.candidate_rule(ROOT)
    weights = tuple(candidate["weights"])
    scored = margins.with_margins(results, contract, predictions, ROOT)
    rows = report["members"]
    gate = {}
    for m in members:
        optimism = admissibility.near_optimism(
            contract, predictions[m], scoring_ids, store.refs
        )
        gate[m] = {
            "near_optimism_bands": optimism,
            "verdict": admissibility.verdict(optimism),
        }
    rules = {
        "control-exam-v1": {
            m: results["rule_scores"][m]["control-exam-v1"] for m in members
        },
        candidate["rule"]: {
            m: margins.score(scored["components"][m], weights) for m in members
        },
    }

    def alignment(names, scores):
        return score_value.alignment(
            {
                m: {
                    "score": scores[m],
                    "value": rows[m]["development_decision_loss"],
                    "eligible": isinstance(scores[m], (int, float)),
                    "recipe": rows[m]["recipe"],
                    "kind": "GRAPHITE_RECONSTRUCTED",
                }
                for m in names
            },
            top_k=3,
        )

    one = [m for m in members if rows[m]["first_seed"]]
    taus = {}
    for rule, scores in rules.items():
        gated = {
            m: admissibility.gated(scores[m], gate[m]["near_optimism_bands"])
            for m in members
        }
        for label, values in (("ungated", scores), ("gated", gated)):
            taus[f"{rule}/{label}"] = {
                "one_seed": alignment(one, values)["kendall_tau_b"],
                "all_seeds": alignment(members, values)["kendall_tau_b"],
                "top1_one_seed": alignment(one, values)["top_k"]["by_score"][:1],
            }
    infeasible_pickers = sorted(
        m for m in members if rows[m]["decision_kinds"].get("SELECTED_INFEASIBLE")
    )
    return {
        "gate": {
            "module": "carbon.battery.value.admissibility",
            "cutoff_bands": admissibility.THRESHOLD_BANDS,
            "members": gate,
            "fails": sorted(m for m in members if gate[m]["verdict"] == "FAIL"),
            "bundled_first_seed": gate[f"{BUNDLED}-s{_first(BUNDLED)}"],
            "infeasible_pickers_failing": sorted(
                m for m in infeasible_pickers if gate[m]["verdict"] == "FAIL"
            ),
            "infeasible_pickers": infeasible_pickers,
        },
        "sr2_rule": {"rule": candidate["rule"], "weights": list(weights)},
        "tau_by_rule": taus,
        "scope": (
            "development computation on EV4 development conditions (previously "
            "used); EV5 modules imported read-only; not EV5 and not a substitute "
            "for it"
        ),
    }


def _first(label):
    return next(
        seeds[0] for name, _s, seeds in value_panel.PANELS[PANEL] if name == label
    )


def conditions_report(report, defence):
    files = {
        name: _sha256(EVIDENCE / name)
        for name in (
            "q1-report.json",
            "results.json",
            "predictions.sha256",
            "aliasing.json",
            "practice-summaries.json",
        )
    }
    one = report["one_seed"]
    review = (
        "the newest battery expansion record "
        "(carbon/reconstruction/expansions/battery-fastcharge-ageing-development-v1/)"
    )
    conditions = [
        {
            "schema": "carbon.admission-condition.v1",
            "condition": "SCORE_VALUE_DIVERGENCE",
            "member": "graphite-run5 panel (rule v2 practice score)",
            "kind": "PANEL_ANTI_ALIGNMENT",
            "detail": {
                "one_seed_kendall_tau_b": one["kendall_tau_b"],
                "one_seed_spearman_rho": one["spearman_rho"],
                "n_one_seed": report["n_one_seed"],
                "all_seed_kendall_tau_b": report["three_seed"]["kendall_tau_b"],
                "tau_noise_band": report["three_seed"]["tau_noise_band"],
                "top1_by_score": one["top_k"]["by_score"][:1],
                "top1_by_value": one["top_k"]["by_value"][:1],
                "member_conditions": len(one["conditions"]),
            },
            "basis": "q1-report.json one_seed and three_seed",
            "review_state": review,
        },
        {
            "schema": "carbon.admission-condition.v1",
            "condition": "SCORE_VALUE_DIVERGENCE",
            "member": "graphite-run5 DeepONet recipes",
            "kind": "SHARED_INFEASIBLE_DECISION",
            "detail": {
                "scenario": "D-T24-S0.12",
                "selected": "c1=2,c2=1",
                "reference": "INFEASIBLE; best feasible c1=1.75,c2=1",
                "deeponet_rebuilds_selecting": len(
                    [
                        m
                        for m in defence["gate"]["infeasible_pickers"]
                        if "baseline" not in m
                    ]
                ),
                "deeponet_rebuilds": sum(
                    1 for m in report["members"] if "baseline" not in m
                ),
                "baseline_rebuilds_selecting": 0,
            },
            "basis": "results.json decisions; q1-report.json members decision_kinds",
            "review_state": review,
        },
        {
            "schema": "carbon.admission-condition.v1",
            "condition": "SCORE_VALUE_DIVERGENCE",
            "member": f"{BUNDLED}-s{_first(BUNDLED)}",
            "kind": "NEAR_LIMIT_FALSE_ACCEPTANCE",
            "detail": {
                "worst_false_acceptance_rate": report["near_limit_false_acceptance"][
                    "members"
                ][f"{BUNDLED}-s{_first(BUNDLED)}"]["worst_false_acceptance_rate"],
                "baseline_worst_false_acceptance_rate": report[
                    "near_limit_false_acceptance"
                ]["members"][f"{BASELINE}-s{_first(BASELINE)}"][
                    "worst_false_acceptance_rate"
                ],
                "practice_rank_by_score": 1,
            },
            "basis": "q1-report.json near_limit_false_acceptance",
            "review_state": review,
        },
        {
            "schema": "carbon.admission-condition.v1",
            "condition": "SCORE_VALUE_DIVERGENCE",
            "member": "battery rule v2 practice comparison (Graphite promotion)",
            "kind": "SEED_LUCK_PROMOTION",
            "detail": {
                "aliasing": [
                    a for a in report["aliasing"] if a["identical_predictions"]
                ],
                "bundled_three_seed_practice": report["seed_luck"]["bundled"],
                "baseline_three_seed_practice": report["seed_luck"]["baseline"],
                "largest_recipe_seed_spread": report["seed_luck"][
                    "largest_single_recipe_seed_spread"
                ],
                "rule": report["seed_luck"]["rule"],
            },
            "basis": "aliasing.json; q1-report.json seed_luck and recipe_bands",
            "review_state": review,
        },
    ]
    return {
        "schema": "carbon.admission-conditions.v1",
        "results": "docs/development/evidence/graphite-run5-q1/results.json",
        "deciding_rule": "battery rule v2 practice score (Graphite feedback)",
        "evidence_sha256": files,
        "conditions": conditions,
        "effect": "under W2, findings block LOCK, not exploration (GRAPHITE-CONDITIONAL-EXPLORATION-01)",
        "recording": "by the campaign controller's operator via CampaignController.consume_conditions",
        "scope": (
            "internal DEVELOPMENT evidence on EV4 development conditions "
            "(previously used); no confirmation claim; not a qualification gate; "
            "not mainnet"
        ),
    }


def main(out):
    out = Path(out)
    report = json.loads((out / "q1-report.json").read_text(encoding="utf-8"))
    defence = defences(out, report)
    (out / "defences.json").write_text(
        json.dumps(defence, indent=2, sort_keys=True) + "\n"
    )
    conditions = conditions_report(report, defence)
    (out / "conditions.json").write_text(
        json.dumps(conditions, indent=2, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {
                "gate_fails": defence["gate"]["fails"],
                "bundled_gate": defence["gate"]["bundled_first_seed"],
                "tau_by_rule": defence["tau_by_rule"],
            },
            indent=1,
        )
    )
    return 0
