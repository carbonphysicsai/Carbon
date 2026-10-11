"""Synthetic, public-only adversarial probe of adopted battery v3 scoring.

This script imports the existing scorer but never loads predictions, case
stores, references, or a producer bank. Numbers are diagnostic fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

from carbon.battery.value import score_tuning

REGISTRY = (
    Path(__file__).resolve().parents[3]
    / "docs/development/evidence/battery-score-tuning/registry-v4.json"
)
CANDIDATE = "G-FEAS/A-Q@0.05"


def _member(candidate, *, accuracy, regrets, false_feasible, loss):
    if not regrets or min(regrets) < 0:
        raise ValueError("synthetic regrets must be nonnegative and nonempty")
    mean_regret = sum(regrets) / len(regrets)
    row = {
        "eligible": True,
        "E": 1 / accuracy - 1,
        "legs": {"a": accuracy, "q": 1 / (1 + mean_regret)},
        "gates": {"feasibility": false_feasible},
    }
    raw = score_tuning.score_member(candidate, row)
    verdict = score_tuning.gate_verdict(candidate, row)
    return {
        "raw_score": raw,
        "gate": verdict,
        "eligible_under_gate": verdict == "PASS",
        "synthetic_decision_loss": loss,
        "mean_q3_regret": mean_regret,
        "max_q3_regret": max(regrets),
        "accuracy_leg": accuracy,
        "q_leg": row["legs"]["q"],
        "false_feasible_rate": false_feasible,
    }


def report():
    registry, identity = score_tuning.load_registry(REGISTRY)
    candidate = registry[CANDIDATE]
    cases = {
        "regret_tail": {
            "definition": "same four-question mean regret, one concentrated large loss",
            "baseline": {
                "accuracy": 0.8,
                "regrets": [0.25] * 4,
                "false_feasible": 0,
                "loss": 0.25,
            },
            "attack": {
                "accuracy": 0.8,
                "regrets": [1, 0, 0, 0],
                "false_feasible": 0,
                "loss": 0.25,
            },
        },
        "unnecessary_abstention": {
            "definition": "miss one feasible opportunity; higher screening accuracy offsets regret",
            "baseline": {
                "accuracy": 0.7,
                "regrets": [0.2] * 4,
                "false_feasible": 0,
                "loss": 0.2,
            },
            "attack": {
                "accuracy": 0.9,
                "regrets": [0.2, 0.2, 0.2, 1],
                "false_feasible": 0,
                "loss": 0.4,
            },
        },
        "feasibility_edge": {
            "definition": "one false-feasible screening case among 21 infeasible cases (1/21 below gate cutoff)",
            "baseline": {
                "accuracy": 0.8,
                "regrets": [0.1] * 4,
                "false_feasible": 0,
                "loss": 0.1,
            },
            "attack": {
                "accuracy": 0.8,
                "regrets": [0.1] * 4,
                "false_feasible": 1 / 21,
                "loss": 1.1,
            },
        },
        "accuracy_regret_tradeoff": {
            "definition": "accuracy gain outweighs a larger Q3 mean regret in geometric A-Q",
            "baseline": {
                "accuracy": 0.64,
                "regrets": [1 / 9] * 4,
                "false_feasible": 0,
                "loss": 1 / 9,
            },
            "attack": {
                "accuracy": 0.95,
                "regrets": [7 / 13] * 4,
                "false_feasible": 0,
                "loss": 7 / 13,
            },
        },
    }
    out = {}
    for name, case in cases.items():
        baseline = _member(candidate, **case["baseline"])
        attack = _member(candidate, **case["attack"])
        out[name] = {
            "definition": case["definition"],
            "baseline": baseline,
            "attack": attack,
            "raw_score_delta": attack["raw_score"] - baseline["raw_score"],
            "synthetic_loss_delta": (
                attack["synthetic_decision_loss"] - baseline["synthetic_decision_loss"]
            ),
        }
    return {
        "schema": "carbon.development.v3-rule-robustness.v1",
        "evidence_class": "SYNTHETIC_ONLY",
        "rule": CANDIDATE,
        "registry_sha256": identity["sha256"],
        "cases": out,
    }


def main():
    print(json.dumps(report(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
