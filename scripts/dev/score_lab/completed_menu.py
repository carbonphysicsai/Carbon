"""Mapping only for the prospective completed-library research protocol.

No reader, model, solver, reference method, score formula or adoption policy.
The producer binds actual public inputs; this module also accepts toy shapes.
"""

from __future__ import annotations

import copy
import math
import statistics
from collections import Counter

from carbon.battery.value import score_proof

from . import bank, owner_dev_v1, public_v2_replay
from .core import LabRefused, canonical_sha


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def manifest(protocol, action_of):
    """Validate the entire new/native/case bijection, not a prefix-only join."""
    questions = protocol["questions"]
    ids = [q["question_id"] for q in questions]
    native = [q["native_context_id"] for q in questions]
    cases = [cid for q in questions for cid in q["case_ids"]]
    if (
        not questions
        or len(set(ids)) != len(ids)
        or len(set(native)) != len(native)
        or len(set(cases)) != len(cases)
        or set(action_of) != set(cases)
        or set(protocol["P"]["support_frozen"]) != set(ids)
        or set(protocol["folds"]["A"]) & set(protocol["folds"]["B"])
        or set(protocol["folds"]["A"] + protocol["folds"]["B"]) != set(ids)
        or len(protocol["folds"]["A"] + protocol["folds"]["B"]) != len(ids)
    ):
        raise LabRefused("completed_menu_identity_or_fold_coverage")
    for q in questions:
        actions = [action_of[cid] for cid in q["case_ids"]]
        if (
            len(actions) < 2
            or len(set(actions)) != len(actions)
            or q["fallback_case_id"] not in q["case_ids"]
            or any(
                not cid.startswith("ev4:" + q["native_context_id"] + ":")
                for cid in q["case_ids"]
            )
        ):
            raise LabRefused("completed_menu_action_or_anchor_coverage")
    return {q["question_id"]: copy.deepcopy(q) for q in questions}


def reference_questions(protocol, action_of, assessed, coverage_rows):
    """Strict whole-menu precheck BEFORE the existing BANK_SPEC classifier."""
    declared = manifest(protocol, action_of)
    case_sets = {qid: q["case_ids"] for qid, q in declared.items()}
    invalid = []
    clean = {}
    for cid in action_of:
        row = coverage_rows.get(cid)
        sealed = row.get("sealed_v2") if isinstance(row, dict) else None
        if (
            not isinstance(row, dict)
            or not finite(row.get("m20_mv"))
            or (
                isinstance(sealed, dict)
                and sealed.get("m160_mv") is not None
                and not finite(sealed["m160_mv"])
            )
        ):
            clean[cid] = None
            invalid.append(cid)
        else:
            clean[cid] = row
    coverage = owner_dev_v1.covered_questions(case_sets, clean)
    covered = set(coverage["common_questions"])
    questions, excluded = {}, {}
    for qid, spec in declared.items():
        q = {
            "question_id": qid,
            "fallback_action": action_of[spec["fallback_case_id"]],
            "actions": {
                action_of[cid]: [
                    copy.deepcopy(
                        assessed.get(
                            cid, {"status": "FAILED_REFERENCE", "objective": None}
                        )
                    )
                ]
                for cid in spec["case_ids"]
            },
        }
        unresolved = [
            cid
            for cid in spec["case_ids"]
            if assessed.get(cid, {}).get("status") not in ("FEASIBLE", "INFEASIBLE")
            or (
                assessed[cid]["status"] == "FEASIBLE"
                and not finite(assessed[cid].get("objective"))
            )
        ]
        if qid not in covered or unresolved:
            q["class"] = "INCOMPLETE"
            excluded[qid] = {
                "plating_coverage": coverage["excluded_questions"].get(qid, {}),
                "unresolved_native_conditions": unresolved,
            }
        else:
            q["class"], _ = bank.classify(q)
        questions[qid] = q
    counts = Counter(q["class"] for q in questions.values())
    return questions, {
        "first_line": protocol["first_line"],
        "offered_questions": len(declared),
        "offered_P_mass": 1.0,
        "class_counts": {
            c: counts[c] for c in ("SCORED", "RESCUE", "NONE", "INCOMPLETE")
        },
        "class_P_mass": {
            c: counts[c] / len(declared)
            for c in ("SCORED", "RESCUE", "NONE", "INCOMPLETE")
        },
        "scored_questions": sorted(
            qid for qid, q in questions.items() if q["class"] == "SCORED"
        ),
        "excluded_questions": excluded,
        "invalid_reference_measurements": sorted(invalid),
        "strict_plating_coverage": coverage,
        "pruned_actions": 0,
        "scalar_is_conditional_on_SCORED": True,
        "qualification": False,
    }


def score_side(rule_id, rule, questions, predictions, leg_ids):
    """Call the exact frozen proxy on LEG only and check its native domain."""
    skipped = (
        [q for q in leg_ids if len(questions[q]["actions"]) < 3]
        if rule_id == "N4-TOP-REGION-RANKING"
        else []
    )
    missing = [
        q
        for q in leg_ids
        if predictions.get(q) is None
        or set(predictions[q]) != set(questions[q]["actions"])
    ]
    if missing:
        return {"status": "UNMEASURED_LEG_PREDICTION_COVERAGE", "questions": missing}
    if rule_id == "N4-TOP-REGION-RANKING":
        missing_objectives = [
            [q, a]
            for q in leg_ids
            for a, rows in questions[q]["actions"].items()
            if rows[0]["status"] == "FEASIBLE"
            and not finite(predictions[q][a].get("objective"))
        ]
        if missing_objectives:
            return {
                "status": "UNMEASURED_NATIVE_RULE_INPUT",
                "missing_predicted_objectives": missing_objectives,
            }
    refs = {
        q: {
            a: {"status": rows[0]["status"], "objective": rows[0]["objective"]}
            for a, rows in questions[q]["actions"].items()
        }
        for q in leg_ids
    }
    preds = {
        q: {
            a: {
                "objective": p["objective"],
                "margins": {"mandatory": 1 if p["feasible"] else -1},
            }
            for a, p in predictions[q].items()
        }
        for q in leg_ids
    }
    metadata = {
        "sense": "min",
        "questions": {
            q: {
                "actions": sorted(questions[q]["actions"]),
                "fallback": questions[q]["fallback_action"],
                "conditions": 1,
                "u": 120,
            }
            for q in leg_ids
        },
        "knobs": {"miss_penalty": 1, "top_fraction": 0.3},
    }
    result = rule(preds, refs, metadata)
    field = "scored_questions" if rule_id.startswith("V2r2") else "questions"
    if skipped or result.get("detail", {}).get(field) != len(leg_ids):
        return {
            "status": "UNMEASURED_INCOMPLETE_LEG_RULE_COVERAGE",
            "required_questions": len(leg_ids),
            "skipped_questions": skipped,
            "native_coverage": result.get("detail", {}),
        }
    if not finite(result.get("score")):
        return {"status": "UNMEASURED_NATIVE_RULE_SCORE"}
    return {
        "status": "MEASURED_DIAGNOSTIC_PROXY",
        "score": result["score"],
        "native_detail": result.get("detail", {}),
        "LEG_questions": list(leg_ids),
    }


def accuracy_score(per_question_errors, leg_ids):
    """Unit question weights; errors have already been case-averaged per menu."""
    if not leg_ids or any(not finite(per_question_errors.get(q)) for q in leg_ids):
        return None
    return 1 / (1 + statistics.fmean(per_question_errors[q] for q in leg_ids))


def question_errors(case_errors, protocol):
    """Do not give a larger action menu a larger outer question weight."""
    return {
        q["question_id"]: (
            statistics.fmean(case_errors[cid] for cid in q["case_ids"])
            if all(finite(case_errors.get(cid)) for cid in q["case_ids"])
            else None
        )
        for q in protocol["questions"]
    }


def diagnostic_selection(scores, members):
    """Freeze real LEG picks; no registered gamer/admission receipt is present."""
    selection = owner_dev_v1.select_top_three(scores, admitted=members, gamers=[])
    if "selection_sha256" in selection:
        selection.pop("selection_sha256")
        selection.pop("no_gamer_in_top_half")
        selection.pop("gamer_top_half")
        selection["gamer_screen"] = "UNMEASURED_NO_REGISTERED_GAMER_IDENTITIES"
        selection["admission_guards"] = "UNMEASURED_NOT_PASS"
        # Bind the explicitly scoped receipt passed to the existing reader.
        selection["selection_sha256"] = canonical_sha(selection)
    return selection


def value_vectors(questions, predictions, value_ids):
    """Use the existing utility and retain gross regret separately from cost."""
    utilities = public_v2_replay.outcomes(
        questions, predictions, value_ids, cap=3, kappa=0.1, unit=120
    )
    if utilities is None:
        return {"status": "UNMEASURED_VALUE_PREDICTION_COVERAGE", "utilities": None}
    if any(utilities[q]["unresolved_attempts"] for q in value_ids):
        return {"status": "UNRESOLVED_REFERENCE_VALUE_VECTOR", "utilities": utilities}
    regrets = {}
    for qid in value_ids:
        q = questions[qid]
        anchor = max(c["objective"] for c in q["actions"][q["fallback_action"]])
        best = min(
            max(c["objective"] for c in rows)
            for rows in q["actions"].values()
            if all(c["status"] == "FEASIBLE" for c in rows)
        )
        # Equivalent to anchor - 120*G - best, using the actual verified
        # objective to avoid an artificial negative regret from round-off.
        verified = [
            max(c["objective"] for c in q["actions"][aid])
            for aid in utilities[qid]["shortlisted_actions"]
            if all(c["status"] == "FEASIBLE" for c in q["actions"][aid])
        ]
        regrets[qid] = min([anchor] + verified) - best
    return {
        "status": "MEASURED_CONDITIONAL_DIAGNOSTIC",
        "utilities": utilities,
        "losses": [-utilities[q]["U"] for q in value_ids],
        "regret_seconds": regrets,
    }


def orientation(
    protocol,
    questions,
    predictions,
    errors,
    groups,
    real_ids,
    controls,
    rules,
    *,
    leg_fold,
):
    """Fixed folds/common mask; controls never inflate learned-model statistics."""
    value_fold = "B" if leg_fold == "A" else "A"
    leg = [q for q in protocol["folds"][leg_fold] if questions[q]["class"] == "SCORED"]
    value = [
        q for q in protocol["folds"][value_fold] if questions[q]["class"] == "SCORED"
    ]
    result = {
        "first_line": protocol["first_line"],
        "LEG_questions": leg,
        "VALUE_questions": value,
        "status": "INSUFFICIENT_EVIDENCE",
        "original_folds": copy.deepcopy(protocol["folds"]),
        "rules": {},
        "qualification": False,
    }
    if not leg or not value:
        return result
    if (
        set(real_ids) & set(controls)
        or len(set(real_ids)) != len(real_ids)
        or len(set(controls)) != len(controls)
        or any(not isinstance(groups.get(m), str) or not groups[m] for m in real_ids)
    ):
        raise LabRefused("completed_menu_real_control_identity")
    ids = list(real_ids) + list(controls)
    # Freeze all LEG scores/selections before reading any VALUE prediction.
    # The declared denominator cannot shrink because a VALUE vector is unknown.
    base = {m: accuracy_score(errors.get(m, {}), leg) for m in ids}
    measured_by_rule = {}
    selections = {}
    for rid, rule in rules.items():
        measured_by_rule[rid] = {
            m: (
                score_side(rid, rule, questions, predictions[m], leg)
                if m in predictions
                and all(predictions[m].get(q) is not None for q in leg)
                else {"status": "UNMEASURED_LEG_PREDICTION_COVERAGE"}
            )
            for m in ids
        }
        selections[rid] = diagnostic_selection(
            {
                m: row["score"]
                for m, row in measured_by_rule[rid].items()
                if "score" in row
            },
            real_ids,
        )
    baseline_selection = diagnostic_selection(base, real_ids)
    vectors = {m: value_vectors(questions, predictions.get(m, {}), value) for m in ids}
    result["declared_real_members"] = list(real_ids)
    result["value_vectors"] = vectors
    result["baseline"] = {
        "label": "recomputed original-reference accuracy diagnostic; not literal v2 or strongest cheap arm",
        "scores": base,
        "fixed_LEG_selection": baseline_selection,
    }
    result["unresolved_value_members"] = [
        m for m in ids if vectors[m]["status"] != "MEASURED_CONDITIONAL_DIAGNOSTIC"
    ]
    regrets = {m: vectors[m].get("regret_seconds", {}) for m in real_ids}
    if baseline_selection["status"] == "SCORE_SIDE_SELECTION_ONLY":
        result["baseline"]["selected_gross_regret_minutes"] = {
            **owner_dev_v1.selected_regret_minutes(baseline_selection, regrets, value),
            "first_line": protocol["first_line"],
        }
    for rid, rule in rules.items():
        measured = measured_by_rule[rid]
        incomplete = {m: row for m, row in measured.items() if "score" not in row}
        # A native-domain defect invalidates the full-LEG rule itself.
        # Missing model inputs instead remain explicit member exclusions below.
        if any(
            r["status"] == "UNMEASURED_INCOMPLETE_LEG_RULE_COVERAGE"
            for r in incomplete.values()
        ):
            result["rules"][rid] = {
                "status": "UNMEASURED_INCOMPLETE_LEG_RULE_COVERAGE",
                "native_receipts": measured,
                "fixed_LEG_selection": selections[rid],
            }
            continue
        scores = {m: row["score"] for m, row in measured.items() if "score" in row}
        matched = [
            m
            for m in real_ids
            if m in scores
            and finite(base[m])
            and vectors[m]["status"] == "MEASURED_CONDITIONAL_DIAGNOSTIC"
        ]
        losses = {m: vectors[m]["losses"] for m in matched}
        means = {m: statistics.fmean(losses[m]) for m in matched}
        tau = score_proof._tau(scores, means, matched) if len(matched) > 1 else None
        baseline_tau = (
            score_proof._tau(base, means, matched) if len(matched) > 1 else None
        )
        boot = (
            score_proof.bootstrap(
                scores, base, losses, groups, matched, n=2000, seed=20261014, level=0.95
            )
            if len(matched) > 1
            else None
        )
        selection = selections[rid]
        contrast = None
        if selection["status"] == "SCORE_SIDE_SELECTION_ONLY":
            contrast = owner_dev_v1.selected_regret_minutes(selection, regrets, value)
            contrast["first_line"] = protocol["first_line"]
        result["rules"][rid] = {
            "status": (
                "MEASURED_CONDITIONAL_DIAGNOSTIC"
                if tau is not None
                else "UNDEFINED_TAU"
            ),
            "tau": tau,
            "baseline_tau": baseline_tau,
            "bootstrap": boot,
            "matched_real_members": matched,
            "scores": scores,
            "native_receipts": measured,
            "unavailable_real_members": sorted(set(real_ids) - set(matched)),
            "fixed_LEG_selection": selection,
            "selected_gross_regret_minutes": contrast,
            "controls": {
                m: {
                    "score": scores.get(m),
                    "competition_rank": (
                        1 + sum(s > scores[m] for s in scores.values())
                        if m in scores
                        else None
                    ),
                    "rank_population": "available real members plus separately constructed controls",
                    "rank_population_count": len(scores),
                    "learned_member": False,
                }
                for m in controls
            },
            "guard_status": "UNMEASURED_NOT_PASS",
            "Stage_C": "NOT_DECIDED_NO_ELIGIBLE_FULL_RULE",
        }
    result["status"] = "CONDITIONAL_DIAGNOSTIC_READOUT"
    return result
