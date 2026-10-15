"""Prospective owner-v1 diagnostics; no execution, holdout or rule adoption.

Reference masks consume producer-bound public rows only. Score-side selection
and subsequent VALUE readout are separate functions: VALUE cannot pick members.
Historical readers and frozen RESEARCH_V1 outputs are unchanged.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

from scripts.dev.battery.plating_rereference import V2_RULES, v2_label

from .core import LabRefused, canonical_sha

ESTIMAND = "value conditional on the covered region"
REGISTRATION = (
    Path(__file__).resolve().parents[3]
    / "Business/research/score-lab-campaign-01/owner-dev-v1/REGISTRATION.json"
)


def candidate_disposition(candidate_id):
    """Read the registered D6 status; never turn a proxy into case errors.

    All ten sources remain reproducible diagnostic inputs. This registration
    has no evidenced eligible new-v3 full-rule form in the current accuracy
    championship frame. A future form needs a new prospective registration.
    """
    registration = json.loads(REGISTRATION.read_bytes())
    forms = registration["candidates"]["per_case_forms"]
    if candidate_id not in forms:
        raise LabRefused("candidate_outside_frozen_family")
    return {"candidate": candidate_id, **forms[candidate_id], "adoptable": False}


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def covered_questions(question_cases, reference_rows):
    """Strict EXCLUDE_COMMON over complete, unchanged question manifests.

    Each row supplies original m20 in mV and an optional sealed v2 label row.
    The upstream producer binds these rows and the complete question grammar
    to actual digests. This function does not authenticate that provenance.
    A dominated/unselected/out-of-claim action still excludes its question.
    """
    if not question_cases or any(
        not isinstance(cases, (list, tuple))
        or not cases
        or len(cases) != len(set(cases))
        for cases in question_cases.values()
    ):
        raise LabRefused("covered_complete_question_grammar_required")
    included, excluded, statuses = [], {}, {}
    for qid, cases in sorted(question_cases.items()):
        reasons = {}
        for cid in cases:
            row = reference_rows.get(cid)
            reason = None
            if row is None or not _finite(row.get("m20_mv")):
                reason = "MISSING_OR_FAILED_REFERENCE"
            elif abs(row["m20_mv"]) >= 15:
                reason = "OUTSIDE_PLATING_V2_CLAIM"
            else:
                sealed = row.get("sealed_v2")
                if not isinstance(sealed, dict):
                    reason = "MISSING_SEALED_V2_REFERENCE"
                elif (
                    sealed.get("source") != "ev4"
                    or sealed.get("case_id") != cid
                    or sealed.get("rule") not in V2_RULES
                    or not _finite(sealed.get("m20_mv"))
                    or not math.isclose(
                        sealed["m20_mv"], row["m20_mv"], rel_tol=0, abs_tol=1e-9
                    )
                    or (
                        sealed.get("m160_mv") is not None
                        and not _finite(sealed["m160_mv"])
                    )
                ):
                    raise LabRefused("covered_v2_source_rule_or_join")
                else:
                    expected = v2_label(
                        row["m20_mv"] / 1000,
                        (
                            None
                            if sealed.get("m160_mv") is None
                            else sealed["m160_mv"] / 1000
                        ),
                    )
                    if expected != {
                        "rule": sealed["rule"],
                        "label": sealed.get("label"),
                    }:
                        raise LabRefused("covered_v2_label_mismatch")
                    if expected["label"] == "UNRESOLVED":
                        reason = "PENDING_OR_UNRESOLVED_V2_REFERENCE"
            statuses[cid] = "UNRESOLVED" if reason else sealed["label"]
            if reason:
                reasons[cid] = reason
        if reasons:
            excluded[qid] = reasons
        else:
            included.append(qid)
    return {
        "first_line": ESTIMAND,
        "status": "READY_REFERENCE_MASK" if included else "INSUFFICIENT_EVIDENCE",
        "common_questions": included,
        "excluded_questions": excluded,
        "plating_status_by_case": statuses,
        "question_manifest_sha256": canonical_sha(question_cases),
        "reference_rows_sha256": canonical_sha(reference_rows),
        "pruned_actions": 0,
        "other_hard_limits": "REQUIRE_SEPARATE_REGISTERED_CHECKS",
        "qualification": False,
    }


def select_top_three(scores, *, admitted, gamers):
    """Freeze each rule's own top three from LEG scores, never VALUE outcomes.

    Admission and known-bad identities must already be prospectively bound.
    Tied gamers use their best competition rank, so lexical order cannot hide
    them below the top-half boundary. Missing scores never shrink n silently.
    """
    admitted = tuple(admitted)
    if len(admitted) != len(set(admitted)) or any(
        type(member) is not str or not member for member in admitted
    ):
        raise LabRefused("selection_admitted_identity")
    missing = sorted(m for m in admitted if not _finite(scores.get(m)))
    if missing or len(admitted) < 3:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "missing_scores": missing,
            "admitted_count": len(admitted),
            "selected": [],
        }
    order = sorted(admitted, key=lambda member: (-scores[member], member))
    ranks = {
        member: 1 + sum(scores[other] > scores[member] for other in admitted)
        for member in admitted
    }
    bad = sorted(
        m for m in set(gamers) & set(admitted) if ranks[m] <= len(admitted) // 2
    )
    body = {
        "status": "SCORE_SIDE_SELECTION_ONLY",
        "selected": order[:3],
        "scores": {m: scores[m] for m in sorted(admitted)},
        "ranks": ranks,
        "admitted_count": len(admitted),
        "gamer_top_half": bad,
        "no_gamer_in_top_half": not bad,
        "cutoff_ties": sorted(m for m in admitted if scores[m] == scores[order[2]]),
        "tie_rule": "descending LEG score then lexical ID; never VALUE",
    }
    return {**body, "selection_sha256": canonical_sha(body)}


def selected_regret_minutes(selection, regret_seconds, value_questions):
    """Read all three frozen picks on one complete VALUE vector in minutes.

    Regrets must come from a registered verified-pick workflow. Missing or
    unresolved outcomes withhold the entire comparison, never select a
    replacement member or average only the favourable resolved questions.
    This is conditional descriptive regret, not an adoption verdict or CI.
    """
    body = {k: v for k, v in selection.items() if k != "selection_sha256"}
    if (
        selection.get("status") != "SCORE_SIDE_SELECTION_ONLY"
        or canonical_sha(body) != selection.get("selection_sha256")
        or len(selection.get("selected", [])) != 3
        or len(set(selection["selected"])) != 3
        or not value_questions
        or len(set(value_questions)) != len(value_questions)
    ):
        raise LabRefused("registered_top_three_selection_required")
    missing = [
        [m, q]
        for m in selection["selected"]
        for q in value_questions
        if not _finite(regret_seconds.get(m, {}).get(q))
    ]
    if missing:
        return {
            "first_line": ESTIMAND,
            "status": "INSUFFICIENT_EVIDENCE",
            "unresolved_selected_outcomes": missing,
            "mean_regret_min": None,
        }
    vectors = {
        m: [regret_seconds[m][q] / 60 for q in value_questions]
        for m in selection["selected"]
    }
    if any(value < 0 for row in vectors.values() for value in row):
        raise LabRefused("negative_buyer_regret")
    return {
        "first_line": ESTIMAND,
        "status": "MEASURED_CONDITIONAL_DIAGNOSTIC",
        "selection_sha256": selection["selection_sha256"],
        "value_questions": list(value_questions),
        "per_selected_member_min": vectors,
        "per_member_mean_regret_min": {
            m: statistics.fmean(v) for m, v in vectors.items()
        },
        "mean_regret_min": statistics.fmean(v for row in vectors.values() for v in row),
        "qualification": False,
    }
