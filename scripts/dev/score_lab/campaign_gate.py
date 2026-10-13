"""Pre-campaign controls on committed public aggregates and analytic toys.

The public side recomputes ranks and capture from published development
aggregates. It does not claim to replay raw solver/model bundles. The toy side
checks the lab's own decision arithmetic on an EV4-like finite action panel.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

from . import synthetic
from .core import LabRefused

SCHEMA = "carbon.dev.score-lab-campaign-controls.v1"


def _read_public(path: Path, schema: str):
    data = path.read_bytes()
    obj = json.loads(data)
    if obj.get("schema") != schema or obj.get("maturity") is None:
        raise LabRefused("campaign_public_source_schema")
    return obj, "sha256:" + hashlib.sha256(data).hexdigest()


def _public_controls(audit, stress):
    old = audit["historical"]["ev5"]["verification"]
    common = old["common_mask"]["per_member"]
    abstain = old["always_abstain_common_loss"]
    if len(common) != 99 or not isinstance(abstain, (float, int)):
        raise LabRefused("campaign_abstain_public_coverage")
    losses = [row["loss"] for row in common.values()]
    if not all(math.isfinite(x) for x in losses):
        raise LabRefused("campaign_abstain_public_nonfinite")
    best_rank = 1 + sum(x < abstain for x in losses)
    worst_rank = best_rank + sum(x == abstain for x in losses)
    recorded = old["always_abstain_rank_against_real"]
    if (best_rank, worst_rank, len(common) + 1) != (
        recorded["best"],
        recorded["worst"],
        recorded["of"],
    ):
        raise LabRefused("campaign_abstain_public_rank_mismatch")
    profile = stress["primary"]["k3-c0.1"]
    if profile["cap"] != 3:
        raise LabRefused("campaign_cheap_public_cap")
    nominal = profile["families"]["nominal"]
    gain = nominal["controls"]["control-bilinear-D"]["gain_units"]
    ceiling = nominal["ceiling_gain_units"]
    if not (math.isfinite(gain) and math.isfinite(ceiling) and ceiling > 0):
        raise LabRefused("campaign_cheap_public_nonfinite")
    capture = gain / ceiling
    if not math.isclose(
        capture, nominal["bilinear_ceiling_capture"], rel_tol=0, abs_tol=1e-12
    ):
        raise LabRefused("campaign_cheap_public_capture_mismatch")
    return {
        "abstain_rank": [best_rank, worst_rank, len(common) + 1],
        "capture": capture,
    }


def _toy_controls(problem, *, questions_per_side, cap):
    if (
        problem.get("space") != "small-grid"
        or problem.get("shift") != "nominal"
        or not isinstance(questions_per_side, int)
        or questions_per_side < 3
        or not isinstance(cap, int)
        or cap < 1
    ):
        raise LabRefused("campaign_toy_control_config")
    panel = synthetic.build(problem, questions_per_side=questions_per_side)
    common = [
        qid
        for qid in panel["value_questions"]
        if all(m["value_losses"][qid] is not None for m in panel["members"])
    ]
    if not common:
        raise LabRefused("campaign_toy_control_no_common_mask")
    losses = {
        m["id"]: statistics.fmean(m["value_losses"][qid] for qid in common)
        for m in panel["members"]
    }
    abstain = losses["control-always-abstain"]
    rank = 1 + sum(v < abstain for v in losses.values())
    offered, hits = 0, 0
    for qid, question in panel["value_questions"].items():
        fallback = question["actions"][question["fallback"]]
        if fallback["status"] != "FEASIBLE":
            continue
        predictions = {
            aid: synthetic._predict(
                "control-bilinear",
                qid,
                float(aid[2:]),
                question["context"],
                problem,
                score_side=False,
            )
            for aid in question["actions"]
        }
        shortlist = sorted(
            (
                (row["objective"], aid)
                for aid, row in predictions.items()
                if row["feasible"] and row["objective"] < fallback["objective"]
            ),
            key=lambda pair: (pair[0], pair[1]),
        )[:cap]
        feasible = [
            question["actions"][aid]["objective"]
            for _, aid in shortlist
            if question["actions"][aid]["status"] == "FEASIBLE"
        ]
        best = min(
            row["objective"]
            for row in question["actions"].values()
            if row["status"] == "FEASIBLE"
        )
        offered += 1
        hits += bool(feasible) and math.isclose(
            min(feasible), best, rel_tol=0, abs_tol=1e-12
        )
    if not offered:
        raise LabRefused("campaign_toy_control_no_priced_questions")
    return {
        "abstain_rank": [rank, len(losses)],
        "finite_grid_optimum_capture": hits / offered,
        "priced_questions": offered,
    }


def run(*, audit_path, stress_path, problem, questions_per_side, cap):
    audit, audit_sha = _read_public(
        Path(audit_path), "carbon.research.value-metric-audit.v1"
    )
    stress, stress_sha = _read_public(
        Path(stress_path), "carbon.research.value-metric-v2-stress.v1"
    )
    public = _public_controls(audit, stress)
    toy = _toy_controls(problem, questions_per_side=questions_per_side, cap=cap)
    passed = (
        public["abstain_rank"][1] <= 2
        and math.isclose(public["capture"], 1.0, abs_tol=1e-12)
        and toy["abstain_rank"][0] == 1
        and math.isclose(toy["finite_grid_optimum_capture"], 1.0, abs_tol=1e-12)
    )
    return {
        "schema": SCHEMA,
        "status": "CONTROL_PASS" if passed else "CONTROL_FAIL_STOP_CAMPAIGN",
        "scope": "PUBLIC_AGGREGATE_BACKTEST_AND_ANALYTIC_TOY",
        "source_sha256": {"res07": audit_sha, "res08": stress_sha},
        "public": public,
        "toy": toy,
        "toy_problem_ASSUMPTION": problem,
        "limit": "Published aggregates are historical; this is not a raw-bundle replay or qualification.",
    }
