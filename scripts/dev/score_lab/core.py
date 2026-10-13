"""Common, read-only score lab: rules never receive value-side references."""

from __future__ import annotations

import hashlib
import json
import math
import statistics

from carbon.battery.value import score_proof, score_tuning

SCHEMA = "carbon.dev.score-lab-panel.v1"


class LabRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def canonical_sha(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_panel(panel):
    if panel.get("schema") != SCHEMA or panel.get("scope") not in (
        "SYNTHETIC_DEVELOPMENT",
        "PUBLIC_DEVELOPMENT",
    ):
        raise LabRefused("panel_scope_or_schema")
    score, value = panel.get("score_questions"), panel.get("value_questions")
    members = panel.get("members")
    if not isinstance(score, dict) or not isinstance(value, dict) or not members:
        raise LabRefused("panel_missing_parts")
    if set(score) & set(value):
        raise LabRefused("score_value_question_overlap")
    ids = [m.get("id") for m in members]
    if len(ids) != len(set(ids)):
        raise LabRefused("duplicate_member")
    for member in members:
        if set(member.get("score_predictions", {})) != set(score):
            raise LabRefused("score_prediction_coverage")
        if set(member.get("value_losses", {})) != set(value):
            raise LabRefused("value_outcome_coverage")
    return panel


def registry_rule(path, candidate_id):
    """Use the score-tuning candidate parser/scorer, without adopting a rule."""
    candidates, identity = score_tuning.load_registry(path)
    try:
        candidate = candidates[candidate_id]
    except KeyError:
        raise LabRefused("candidate_not_registered") from None

    def score(predictions, references, metadata):
        del predictions, references
        row = metadata.get("score_row")
        if row is None:
            return None
        raw = score_tuning.score_member(candidate, row)
        if raw is None:
            return None
        verdict = score_tuning.gate_verdict(candidate, row)
        return {"score": raw, "admissible": verdict != "FAIL"}

    score.rule_identity = {
        "kind": "score_tuning_registry",
        "candidate": candidate_id,
        "registry_sha256": identity["sha256"],
    }
    return score


def v2_rule(*, definition, kappa, cap, unit):
    """VALUE-METRIC-V2 rev 2 on the score half, with explicit lab assumptions.

    The bank admits only complete questions with a reference-feasible fallback.
    This is a prospective score candidate, never a deployed score.
    """
    if (
        definition.get("id") != "VALUE-METRIC-V2"
        or definition.get("revision") != 2
        or definition.get("estimand", {}).get("per_question") != "U = G - kappa * n"
    ):
        raise LabRefused("v2_definition_mismatch")
    if (
        not all(
            isinstance(x, (int, float)) and math.isfinite(x) and x > 0
            for x in (kappa, unit)
        )
        or not isinstance(cap, int)
        or cap < 1
    ):
        raise LabRefused("v2_human_input_required")

    def score(predictions, references, metadata):
        gate = metadata.get("v2_gate")
        if gate is None:
            return None  # active G-FEAS gate not supplied; fail closed
        utilities = []
        weights = []
        for qid, question in references.items():
            actions = question["actions"]
            fallback = question["fallback"]
            if any(
                a["status"] not in ("FEASIBLE", "INFEASIBLE") for a in actions.values()
            ):
                continue
            if actions[fallback]["status"] != "FEASIBLE":
                continue
            base = actions[fallback]["objective"]
            predicted = predictions[qid]
            if set(predicted) != set(actions):
                return None  # missing action predictions cannot mimic abstention
            shortlist = sorted(
                (
                    (p["objective"], aid)
                    for aid, p in predicted.items()
                    if p["feasible"]
                    and p["objective"] is not None
                    and p["objective"] < base
                ),
                key=lambda x: (x[0], x[1]),
            )[:cap]
            n = sum(actions[aid]["solves"] for _, aid in shortlist)
            feasible = [
                actions[aid]["objective"]
                for _, aid in shortlist
                if actions[aid]["status"] == "FEASIBLE"
                and actions[aid]["objective"] < base
            ]
            gain = max(0.0, (base - min(feasible)) / unit) if feasible else 0.0
            utilities.append(gain - kappa * n)
            weight = question.get("weight")
            if (
                not isinstance(weight, (int, float))
                or weight <= 0
                or not math.isfinite(weight)
            ):
                raise LabRefused("v2_question_weight_missing")
            weights.append(weight)
        if not utilities:
            return None
        row = metadata.get("score_row") or {}
        # The active registered G-FEAS gate remains mandatory. The score lab
        # does not select its threshold: the caller passes the exact gate.
        admissible = score_tuning.one_gate_verdict(gate, row) != "FAIL"
        return {
            "score": sum(w * u for w, u in zip(weights, utilities, strict=True))
            / sum(weights),
            "admissible": admissible,
        }

    score.rule_identity = {
        "kind": "VALUE-METRIC-V2-rev2-lab",
        "definition_sha256": canonical_sha(definition),
        "kappa_ASSUMPTION": kappa,
        "k_ASSUMPTION": cap,
        "u_ASSUMPTION": unit,
    }
    return score


def _number(result):
    if result is None:
        return None, False, 0
    if isinstance(result, dict):
        value, admissible = result.get("score"), result.get("admissible")
        if type(admissible) is not bool:
            raise LabRefused("rule_admissibility_malformed")
        tier = result.get("tier", 0)
        if type(tier) is not int or tier < 0:
            raise LabRefused("rule_tier_malformed")
    else:
        value, admissible, tier = result, True, 0
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
    ):
        raise LabRefused("rule_score_nonfinite")
    return float(value), admissible, tier


def analyze(panel, rule, *, bootstrap=200, seed=20261013):
    """One rule over one panel. Statistical intervals are exploratory."""
    validate_panel(panel)
    if (
        getattr(rule, "rule_identity", {}).get("kind") == "VALUE-METRIC-V2-rev2-lab"
        and panel["scope"] == "PUBLIC_DEVELOPMENT"
        and panel.get("assumption", {}).get("job") != "VALUE-METRIC-V2"
    ):
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": "v2_bank_not_registered_for_public_job",
        }
    if bootstrap < 1:
        raise LabRefused("bootstrap_count")
    references = panel["score_questions"]
    members = panel["members"]
    names = [m["id"] for m in members]
    recipe_of = {m["id"]: m["recipe"] for m in members}
    scores, admissibility, tiers, losses = {}, {}, {}, {}
    for member in members:
        name = member["id"]
        result = rule(
            member["score_predictions"],
            references,
            {
                "score_row": member.get("score_row"),
                **panel.get("score_metadata", {}),
                **member.get("score_metadata", {}),
            },
        )
        scores[name], admissibility[name], tiers[name] = _number(result)
        losses[name] = member["value_losses"]
    mask = sorted(
        q
        for q in panel["value_questions"]
        if all(losses[m][q] is not None for m in names)
    )
    if not mask:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": "no_common_resolved_value_questions",
        }
    values = {m: -statistics.fmean(losses[m][q] for q in mask) for m in names}
    primary = [m["id"] for m in members if m["kind"] == "MODEL"]
    missing = [m for m in primary if scores[m] is None]
    if missing:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": "unscored_primary_members",
            "count": len(missing),
        }
    finite = [s for s in scores.values() if s is not None]
    floor = min(finite) - max(1.0, max(finite) - min(finite) + 1.0)
    # FLOOR is lexicographic: every lower tier outranks every higher tier,
    # while the candidate's own score orders members inside each tier.
    finite_tiers = sorted({tiers[m] for m in names if scores[m] is not None})
    span = max(finite) - min(finite) + 1.0
    ranked_scores = {
        m: (
            floor - span
            if s is None or not admissibility[m]
            else s - (finite_tiers.index(tiers[m]) * span)
        )
        for m, s in scores.items()
    }
    boot = score_proof.bootstrap(
        ranked_scores,
        {},
        {m: [losses[m][q] for q in mask] for m in primary},
        recipe_of,
        primary,
        n=bootstrap,
        seed=seed,
    )
    tau = score_proof._tau(ranked_scores, {m: -v for m, v in values.items()}, primary)
    ranked_primary = sorted(primary, key=lambda m: (-ranked_scores[m], m))
    ranked_all = sorted(names, key=lambda m: (-ranked_scores[m], m))
    top1 = next((m for m in ranked_primary if admissibility[m]), None)
    best = max(values[m] for m in primary)
    oracle = panel.get("exact_oracle_losses")
    exact_best = (
        -statistics.fmean(oracle[q] for q in mask)
        if oracle is not None and all(oracle.get(q) is not None for q in mask)
        else None
    )
    probes = [m["id"] for m in members if m["kind"] != "MODEL"]
    probe_ranks = {m: 1 + ranked_all.index(m) for m in probes}
    return {
        "status": "MEASURED_DEVELOPMENT",
        "source": panel["scope"],
        "panel_sha256": canonical_sha(panel),
        "rule": getattr(rule, "rule_identity", {"kind": "local_python_function"}),
        "members": len(primary),
        "score_questions": len(references),
        "value_questions": len(mask),
        "value_questions_offered": len(panel["value_questions"]),
        "tau": tau,
        "tau_ci95": None if boot is None else boot["joint"],
        "tau_undefined_fraction": None if boot is None else boot["undefined_fraction"],
        "top1_regret": (
            None
            if top1 is None
            else (exact_best if exact_best is not None else best) - values[top1]
        ),
        "top1_regret_reference": (
            panel.get("oracle_kind", "EXACT_ANALYTIC_ORACLE")
            if exact_best is not None
            else "BEST_MEMBER_IN_POOL"
        ),
        "top1_member": top1,
        "probe_rank_of": len(names),
        "probe_ranks": probe_ranks,
        "known_bad_in_top_half": sorted(
            m
            for m in probes
            if m.startswith("known-bad") and 2 * probe_ranks[m] <= len(names)
        ),
        "adversarial_in_top_half": sorted(
            m
            for m in probes
            if m.startswith("adversarial") and 2 * probe_ranks[m] <= len(names)
        ),
        "always_abstain_rank": probe_ranks.get("control-always-abstain"),
        "cheap_baseline_rank": probe_ranks.get("control-bilinear"),
        "admissibility_failures": sum(not admissibility[m] for m in names),
        "admissibility": admissibility,
        "physics_tiers": {m: tiers[m] for m in names},
        "ranked_scores": ranked_scores,
        "assumption": panel.get("assumption"),
    }
