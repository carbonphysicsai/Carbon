"""Read-only SCORE-VALUE-ALIGNMENT-01 audit of committed DEVELOPMENT panels.

Run from the repository root with ``python -m scripts.dev.battery.score_value_alignment_report``.
This deliberately refuses to infer v3's Q3 and G-FEAS legs from EV4/EV5
decision outcomes. It reads no prediction bundle, solver, hidden bank, or host
data. The output is a reproducible JSON evidence table, not a score update.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from carbon.design_search.score_value import kendall_tau_b, spearman_rho

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path("docs/development/evidence")
V3_REQUIRED = (
    "accuracy_on_registered_v3_screening_cases",
    "q3_regret_on_corresponding_settled_quiz",
    "false_feasible_rate_on_v3_scoring_set",
    "case_and_rule_identity_with_failure_cause",
)


def _read(root: Path, relative: str) -> dict:
    return json.loads((root / EVIDENCE / relative).read_text(encoding="utf-8"))


def _sha256(root: Path, relative: str) -> str:
    return hashlib.sha256((root / EVIDENCE / relative).read_bytes()).hexdigest()


def _metrics(rows: list[tuple[float, float]]) -> dict:
    if len(rows) < 2:
        return {"tau": None, "rho": None}
    scores = [score for score, _ in rows]
    values = [-loss for _, loss in rows]
    return {
        "tau": kendall_tau_b(scores, values),
        "rho": spearman_rho(scores, values),
    }


def _percentile(sorted_values: list[float], p: float) -> float:
    index = (len(sorted_values) - 1) * p
    low = math.floor(index)
    high = math.ceil(index)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (
        index - low
    )


def _bootstrap(
    groups: dict[str, list[tuple[float, float]]], *, seed: int, draws: int
) -> dict:
    """Descriptive cluster bootstrap, keeping every seed of a recipe together."""
    keys = sorted(groups)
    rng = random.Random(seed)
    samples = {"tau": [], "rho": []}
    for _ in range(draws):
        rows = [row for _ in keys for row in groups[rng.choice(keys)]]
        metrics = _metrics(rows)
        for name, values in samples.items():
            if metrics[name] is not None:
                values.append(metrics[name])
    return {
        name: (
            {
                "low": _percentile(sorted(vals), 0.025),
                "high": _percentile(sorted(vals), 0.975),
                "defined_draws": len(vals),
            }
            if vals
            else None
        )
        for name, vals in samples.items()
    }


def _v3_unavailable() -> dict:
    return {
        "status": "UNCOMPUTABLE_FROM_COMMITTED_PANEL",
        "tau": None,
        "rho": None,
        "term_contributions": {"a": None, "q": None, "G-FEAS@0.05": None},
        "missing": list(V3_REQUIRED),
    }


def _q1(root: Path, directory: str, *, draws: int) -> list[dict]:
    relative = f"{directory}/q1-report.json"
    report = _read(root, relative)
    members = report["members"]
    records = []
    for panel_name in ("one_seed", "three_seed"):
        panel = report[panel_name]
        ids = panel["members_ranked"]
        groups = {}
        for member_id in ids:
            member = members[member_id]
            groups.setdefault(member["recipe"], []).append(
                (-member["cpu_practice_score"], member["development_decision_loss"])
            )
        metrics = _metrics([row for group in groups.values() for row in group])
        if not math.isclose(metrics["tau"], panel["kendall_tau_b"], abs_tol=1e-12):
            raise ValueError(f"{relative}:{panel_name}:recorded_tau_mismatch")
        if not math.isclose(metrics["rho"], panel["spearman_rho"], abs_tol=1e-12):
            raise ValueError(f"{relative}:{panel_name}:recorded_rho_mismatch")
        records.append(
            {
                "panel": directory,
                "split": panel_name,
                "source": relative,
                "source_sha256": _sha256(root, relative),
                "score_rule": "v2_public_PRACTICE",
                "decision_value": "EV4_development_common_resolved_mask",
                "members": len(ids),
                "clusters": len(groups),
                "metrics": metrics,
                "cluster_bootstrap_95_descriptive": _bootstrap(
                    groups, seed=20261009, draws=draws
                ),
                "v3": _v3_unavailable(),
                "divergent_members_v2": (
                    [
                        c["member"]
                        for c in panel["conditions"]
                        if c["condition"] == "SCORE_VALUE_DIVERGENCE"
                    ]
                    if panel_name == "one_seed"
                    else None
                ),
            }
        )
    return records


def _ev(root: Path, directory: str, *, draws: int) -> list[dict]:
    relative = f"{directory}/results.json"
    results = _read(root, relative)
    members = results["summary"]["members"]
    records = []
    for split in ("development", "verification"):
        groups = {}
        for member_id, member in members.items():
            if member["kind"] != "RECONSTRUCTED":
                continue
            score = results["rule_scores"][member_id]["control-exam-v1"]
            loss = member[f"loss_{split}"]
            if loss is None or isinstance(score, str):
                raise ValueError(f"{relative}:{split}:missing_historical_pair")
            family = member_id.rsplit("-s", 1)[0]
            groups.setdefault(family, []).append(
                (float("-inf") if score is None else score, loss)
            )
        metrics = _metrics([row for group in groups.values() for row in group])
        recorded = results["comparison"]["control-exam-v1"][f"tau_{split}"]
        if not math.isclose(metrics["tau"], recorded, abs_tol=1e-12):
            raise ValueError(f"{relative}:{split}:recorded_tau_mismatch")
        records.append(
            {
                "panel": directory,
                "split": split,
                "source": relative,
                "source_sha256": _sha256(root, relative),
                "score_rule": "control-exam-v1_not_v2",
                "decision_value": "historical_EV_per_member_resolved_loss",
                "members": sum(len(group) for group in groups.values()),
                "clusters": len(groups),
                "metrics": metrics,
                "cluster_bootstrap_95_descriptive": _bootstrap(
                    groups, seed=20261009, draws=draws
                ),
                "v2": {
                    "status": "NOT_RECORDED_ON_THIS_PANEL",
                    "tau": None,
                    "rho": None,
                },
                "v3": _v3_unavailable(),
            }
        )
    return records


def audit(root: Path = ROOT, *, draws: int = 500) -> dict:
    if draws < 1:
        raise ValueError("draws_must_be_positive")
    panels = []
    for directory in ("graphite-run5-q1", "graphite-run5-q1-refined"):
        panels.extend(_q1(root, directory, draws=draws))
    for directory in ("ev4-2026-10-01", "ev5-2026-10-03"):
        panels.extend(_ev(root, directory, draws=draws))
    return {
        "schema": "carbon.development.score-value-alignment-audit.v1",
        "authority": "SCORE-VALUE-ALIGNMENT-01; owner-approved v3 is prospective",
        "bootstrap": {
            "method": "cluster-resample recipes/families with replacement",
            "draws": draws,
            "seed": 20261009,
            "interpretation": "descriptive, not independent confirmation or qualification",
        },
        "panels": panels,
        "quiz_design_curves": {
            "status": "AGGREGATES_ONLY_NO_MATCHED_MEMBER_SCORE_VALUE_ROWS",
            "v2_tau": None,
            "v2_rho": None,
            "v3": _v3_unavailable(),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draws", type=int, default=500)
    args = parser.parse_args()
    print(json.dumps(audit(draws=args.draws), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
