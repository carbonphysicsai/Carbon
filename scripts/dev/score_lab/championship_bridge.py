"""Synthetic accuracy-only bridge to the existing fresh-batch rev-5 rule.

No score conversion, guard inference, sampling, I/O, deployment or carry-forward.
Value diagnostics consume a committed result after the selector has returned.
"""

from __future__ import annotations

import copy
import math
import re
import statistics
from dataclasses import asdict
from itertools import pairwise

from carbon.championship_stats import (
    Rev5Case,
    Rev5Contender,
    Rev5Rule,
    select_rev5_winner,
)

from .core import LabRefused, canonical_sha, validate_panel

SCHEMA = "carbon.dev.score-lab-accuracy-championship.v1"
SCOPE = "SYNTHETIC_DEVELOPMENT"


def batch_binding(evidence, rule, draws):
    return canonical_sha({"evidence": evidence, "rule": asdict(rule), "draws": draws})


def _evidence(evidence):
    if (
        type(evidence) is not dict
        or set(evidence) != {"schema", "scope", "metric", "case_blocks", "errors"}
        or evidence["schema"] != SCHEMA
        or evidence["scope"] != SCOPE
    ):
        raise LabRefused("championship_requires_synthetic_accuracy_evidence")
    metric = evidence["metric"]
    if (
        type(metric) is not dict
        or set(metric) != {"id", "kind", "unit", "source_sha256"}
        or metric["kind"] != "nonnegative_case_accuracy_error"
        or any(type(metric[k]) is not str or not metric[k] for k in metric)
        or re.fullmatch(r"[0-9a-f]{64}", metric["source_sha256"]) is None
    ):
        raise LabRefused("championship_accuracy_metric_required")
    blocks, errors = evidence["case_blocks"], evidence["errors"]
    if (
        type(blocks) is not dict
        or not blocks
        or type(errors) is not dict
        or not errors
        or any(
            type(q) is not str or not q or type(b) is not str or not b
            for q, b in blocks.items()
        )
    ):
        raise LabRefused("championship_evidence_shape")
    for artifact, values in errors.items():
        if (
            type(artifact) is not str
            or not artifact
            or type(values) is not dict
            or set(values) != set(blocks)
        ):
            raise LabRefused("championship_accuracy_coverage")
        if any(
            v is not None
            and (type(v) not in (int, float) or not math.isfinite(v) or v < 0)
            for v in values.values()
        ):
            raise LabRefused("championship_nonnegative_accuracy_required")


def accuracy_round(evidence, rule, *, draws, contenders, guards):
    """Use exact rev-5 selection; callers supply guard evidence, never defaults.

    A bound hash is integrity only, not an independent guard attestation. This
    adapter is structurally restricted to synthetic development measurements.
    """
    _evidence(evidence)
    if (
        type(rule) is not Rev5Rule
        or type(draws) is not tuple
        or type(contenders) is not tuple
    ):
        raise LabRefused("championship_registered_inputs_required")
    if any(type(item) is not str or not item for item in draws + contenders):
        raise LabRefused("championship_case_or_artifact_identity")
    if (
        len(draws) != rule.drawn_cases
        or any(q not in evidence["case_blocks"] for q in draws)
        or len(contenders) != len(set(contenders))
        or rule.king_id in contenders
        or len(contenders) > rule.max_contenders
    ):
        raise LabRefused("championship_shared_batch_or_contenders")
    if rule.draw_unit == "case" and any(evidence["case_blocks"][q] != q for q in draws):
        raise LabRefused("championship_case_draw_block_mismatch")
    compared = (rule.king_id,) + contenders
    if (
        any(a not in evidence["errors"] for a in compared)
        or type(guards) is not dict
        or set(guards) != set(compared)
    ):
        raise LabRefused("championship_compared_artifact_coverage")
    binding = batch_binding(evidence, rule, draws)
    guard_fields = {
        "receipt_id",
        "artifact_id",
        "batch_sha256",
        "g_feas",
        "important_region",
    }
    for artifact, receipt in guards.items():
        if (
            type(receipt) is not dict
            or set(receipt) != guard_fields
            or type(receipt["receipt_id"]) is not str
            or not receipt["receipt_id"]
            or receipt["artifact_id"] != artifact
            or receipt["batch_sha256"] != binding
            or receipt["g_feas"] not in ("PASS", "FAIL", "UNRESOLVED")
            or receipt["important_region"] not in ("PASS", "FAIL", "UNRESOLVED")
        ):
            raise LabRefused("championship_guard_receipt_binding")
    reason = None
    if any(evidence["errors"][a][q] is None for a in compared for q in draws):
        reason = "unresolved_accuracy_measurement"
    elif any(
        "UNRESOLVED" in (r["g_feas"], r["important_region"]) for r in guards.values()
    ):
        reason = "unresolved_hard_guard"
    elif any(guards[rule.king_id][g] != "PASS" for g in ("g_feas", "important_region")):
        reason = "incumbent_qualification_unavailable"
    elif len({evidence["case_blocks"][q] for q in draws}) < 2:
        reason = "fewer_than_two_independent_draw_blocks"
    elif statistics.fmean(evidence["errors"][rule.king_id][q] for q in set(draws)) <= 0:
        reason = "relative_improvement_undefined_for_zero_king_error"
    body = {
        "schema": SCHEMA,
        "scope": SCOPE,
        "rule": asdict(rule),
        "metric": copy.deepcopy(evidence["metric"]),
        "batch_sha256": binding,
        "score_case_ids": sorted(set(draws)),
        "compared_artifacts": list(compared),
        "guard_receipts": copy.deepcopy(guards),
    }
    if reason is not None:
        body.update(status="INSUFFICIENT_EVIDENCE", reason=reason, winner_id=None)
    else:
        cases = tuple(
            Rev5Contender(
                artifact,
                tuple(
                    Rev5Case(
                        q,
                        evidence["case_blocks"][q],
                        evidence["errors"][rule.king_id][q],
                        evidence["errors"][artifact][q],
                    )
                    for q in draws
                ),
                guards[artifact]["g_feas"] == "PASS",
                guards[artifact]["important_region"] == "PASS",
            )
            for artifact in contenders
        )
        result = select_rev5_winner(rule, cases)
        body.update(
            status="MEASURED_SYNTHETIC_ROUND",
            winner_id=result.winner_id,
            unique_cases=result.unique_cases,
            outcomes=[asdict(r) for r in result.outcomes],
        )
    return {**body, "commit_sha256": canonical_sha(body)}


def _commit(receipt):
    if type(receipt) is not dict:
        raise LabRefused("championship_round_commit_binding")
    body = {k: v for k, v in receipt.items() if k != "commit_sha256"}
    if (
        body.get("schema") != SCHEMA
        or body.get("scope") != SCOPE
        or canonical_sha(body) != receipt.get("commit_sha256")
    ):
        raise LabRefused("championship_round_commit_binding")


def value_diagnostic(receipt, panel):
    """Read value only after the immutable round result, on one common mask."""
    _commit(receipt)
    validate_panel(panel)
    if panel["scope"] != SCOPE:
        raise LabRefused("championship_value_requires_synthetic")
    if set(receipt["score_case_ids"]) & set(panel["value_questions"]):
        raise LabRefused("championship_score_value_case_overlap")
    if receipt["status"] != "MEASURED_SYNTHETIC_ROUND":
        return {"status": "INSUFFICIENT_EVIDENCE", "reason": "round_unscored"}
    pool = {m["id"]: m for m in panel["members"]}
    ids = receipt["compared_artifacts"]
    if any(a not in pool for a in ids):
        raise LabRefused("championship_value_artifact_missing")
    if any(
        v is not None and (type(v) not in (int, float) or not math.isfinite(v))
        for a in ids
        for v in pool[a]["value_losses"].values()
    ):
        raise LabRefused("championship_value_nonfinite")
    mask = sorted(
        q
        for q in panel["value_questions"]
        if all(pool[a]["value_losses"][q] is not None for a in ids)
    )
    if not mask:
        return {"status": "INSUFFICIENT_EVIDENCE", "reason": "no_common_value_outcomes"}
    values = {
        a: -statistics.fmean(pool[a]["value_losses"][q] for q in mask) for a in ids
    }
    best_value = max(values.values())
    winner = receipt["winner_id"]
    return {
        "status": "MEASURED_SYNTHETIC_DIAGNOSTIC",
        "round_commit_sha256": receipt["commit_sha256"],
        "value_panel_sha256": canonical_sha(panel),
        "common_mask_sha256": canonical_sha(mask),
        "value_questions": len(mask),
        "value_questions_offered": len(panel["value_questions"]),
        "estimand": "mean_value_on_common_resolved_questions_for_compared_finite_pool",
        "winner_id": winner,
        "winner_value": values[winner],
        "best_compared_members": sorted(
            a for a, v in values.items() if v == best_value
        ),
        "crown_is_best_compared_value": values[winner] == best_value,
        "regret_against_best_compared_member": best_value - values[winner],
    }


def trajectory_diagnostic(receipts, panel):
    """Summarize supplied rounds, never simulate or carry statistical evidence."""
    if type(receipts) is not tuple or not receipts:
        raise LabRefused("championship_round_sequence_required")
    for receipt in receipts:
        _commit(receipt)
    if any(r["status"] != "MEASURED_SYNTHETIC_ROUND" for r in receipts):
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": "round_sequence_incomplete",
        }
    if (
        len({r["rule"]["batch_id"] for r in receipts}) != len(receipts)
        or any(b["rule"]["king_id"] != a["winner_id"] for a, b in pairwise(receipts))
        or any(
            set(r["compared_artifacts"]) != set(receipts[0]["compared_artifacts"])
            for r in receipts
        )
    ):
        raise LabRefused("championship_trajectory_identity_or_chain")
    diagnostics = [value_diagnostic(r, panel) for r in receipts]
    if any(d["status"] != "MEASURED_SYNTHETIC_DIAGNOSTIC" for d in diagnostics):
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": "trajectory_value_unmeasured",
        }
    wins = [
        i + 1 for i, d in enumerate(diagnostics) if d["crown_is_best_compared_value"]
    ]
    return {
        "status": "MEASURED_SYNTHETIC_TRAJECTORY",
        "rounds": len(receipts),
        "rounds_best_compared_member_holds_crown": len(wins),
        "first_round_best_compared_member_holds_crown": min(wins) if wins else None,
        "takeovers": sum(r["winner_id"] != r["rule"]["king_id"] for r in receipts),
        "round_commits": [r["commit_sha256"] for r in receipts],
        "interpretation": (
            "one supplied toy trajectory, not a detection probability or power estimate"
        ),
    }
