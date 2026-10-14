"""Development-half structural and winnability checks for V2 bank drafts."""

from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path

from .core import LabRefused


def _interval(values):
    values = sorted(values)
    return [
        values[int(0.025 * (len(values) - 1))],
        values[math.ceil(0.975 * (len(values) - 1))],
    ]


def _v2_question(q, prediction, *, cap, kappa, unit, detail=False):
    actions = q["actions"]
    if set(prediction) != set(actions):
        raise LabRefused("bank_predictor_action_coverage")
    if any(
        type(p.get("feasible")) is not bool
        or "objective" not in p
        or (p.get("objective") is None and p["feasible"])
        or (
            p.get("objective") is not None
            and (
                type(p["objective"]) not in (int, float)
                or not math.isfinite(p["objective"])
            )
        )
        for p in prediction.values()
    ):
        raise LabRefused("bank_predictor_nonfinite")
    base = max(c["objective"] for c in actions[q["fallback_action"]])
    shortlist = sorted(
        (
            (p["objective"], aid)
            for aid, p in prediction.items()
            if p["feasible"] and p["objective"] < base
        ),
        key=lambda x: (x[0], x[1]),
    )[:cap]
    solved = sum(len(actions[aid]) for _, aid in shortlist)
    feasible = [
        max(condition["objective"] for condition in actions[aid])
        for _, aid in shortlist
        if all(condition["status"] == "FEASIBLE" for condition in actions[aid])
    ]
    gain = max(0.0, (base - min(feasible)) / unit) if feasible else 0.0
    result = {"U": gain - kappa * solved, "G": gain, "n": solved}
    if detail:
        ids = [aid for _, aid in shortlist]
        result.update(
            shortlisted_actions=ids,
            infeasible_attempts=sum(
                any(c["status"] == "INFEASIBLE" for c in actions[aid]) for aid in ids
            ),
            unresolved_attempts=sum(
                any(c["status"] == "UNRESOLVED" for c in actions[aid])
                and not any(c["status"] == "INFEASIBLE" for c in actions[aid])
                for aid in ids
            ),
        )
    return result


def classify(q):
    """Reference-only BANK_SPEC class and decision-determined reading.

    An in-band action is harmless only when its known objective cannot beat
    the best certainly feasible action. A fallback whose feasibility is still
    in-band cannot define the scored buyer comparison.
    """
    actions = q["actions"]
    if any(
        c["status"] == "FAILED_REFERENCE"
        for conditions in actions.values()
        for c in conditions
    ):
        return "INCOMPLETE", False
    feasible = [
        max(c["objective"] for c in conditions)
        for conditions in actions.values()
        if all(c["status"] == "FEASIBLE" for c in conditions)
    ]
    best = min(feasible) if feasible else None
    fallback_states = {c["status"] for c in actions[q["fallback_action"]]}
    if "UNRESOLVED" in fallback_states and "INFEASIBLE" not in fallback_states:
        return "INCOMPLETE", False
    has_unresolved = False
    for conditions in actions.values():
        states = {c["status"] for c in conditions}
        if "UNRESOLVED" not in states or "INFEASIBLE" in states:
            continue
        has_unresolved = True
        if best is None or max(c["objective"] for c in conditions) < best:
            return "INCOMPLETE", False
    if all(c["status"] == "FEASIBLE" for c in actions[q["fallback_action"]]):
        return "SCORED", has_unresolved
    return ("RESCUE" if feasible else "NONE"), has_unresolved


def check(
    manifest,
    records,
    *,
    definition_bytes,
    cheap=None,
    reference_model=None,
    cap=None,
    kappa=None,
    unit=None,
    ceiling_threshold=None,
    learnability=None,
    replicates=500,
):
    """No sealed-half records accepted. Values are assumptions, never adopted.

    Input records follow BANK_SPEC's per-condition format. Missing prospective
    registrations or human thresholds produce INSUFFICIENT_EVIDENCE.
    """
    definition = json.loads(definition_bytes)
    if definition.get("id") != "VALUE-METRIC-V2" or definition.get("revision") != 2:
        raise LabRefused("bank_definition_version")
    digest = hashlib.sha256(definition_bytes).hexdigest()
    if manifest.get("definition_digest") != "sha256:" + digest:
        raise LabRefused("bank_definition_digest")
    if not isinstance(replicates, int) or replicates < 1:
        raise LabRefused("bank_bootstrap_count")
    required = (
        "question_law_digest",
        "population_digest",
        "proposal_digest",
        "weights_digest",
        "drawer_seed_commitment",
        "image_digest",
        "mms_acceptance_digest",
        "train_separation",
        "cheap_arm_registration",
        "objective_aggregation",
        "neighbour_declarations",
    )
    missing = [k for k in required if not manifest.get(k)]
    cheap_registration = manifest.get("cheap_arm_registration")
    if not isinstance(cheap_registration, dict) or (
        cheap_registration.get("status") != "FROZEN_BEFORE_DRAW"
        or not cheap_registration.get("evidence_digest")
    ):
        missing.append("cheap_arm_frozen_before_draw")
    if not records or any(q.get("half") != "development" for q in records):
        raise LabRefused("sealed_or_empty_bank_records")
    if manifest.get("objective_aggregation") != "worst_case":
        # This diagnostic uses max(condition objectives). Another registered
        # objective aggregation needs an explicit adapter, never an implicit
        # reinterpretation of its buyer job.
        raise LabRefused("bank_objective_aggregation_unsupported")
    if manifest.get("objective_sense") != "minimize":
        raise LabRefused("bank_objective_sense_unsupported")
    declared = manifest.get("neighbour_declarations")
    if not isinstance(declared, list) or any(
        not isinstance(item, dict) or not item.get("id") for item in declared
    ):
        raise LabRefused("bank_neighbour_declarations_missing")
    tasks = {"target", *(item["id"] for item in declared)}
    if any(q.get("task") not in tasks for q in records):
        raise LabRefused("bank_task_unregistered")
    ids = [q.get("question_id") for q in records]
    if len(ids) != len(set(ids)):
        raise LabRefused("bank_duplicate_question")
    classes = {"SCORED": 0, "RESCUE": 0, "NONE": 0, "INCOMPLETE": 0}
    scored = []
    determined = 0
    for q in records:
        actions = q.get("actions")
        fallback = q.get("fallback_action")
        weight = q.get("weight")
        if (
            not q.get("block_id")
            or not actions
            or fallback not in actions
            or not isinstance(weight, (int, float))
            or weight <= 0
            or not math.isfinite(weight)
        ):
            raise LabRefused("bank_record_shape")
        for conditions in actions.values():
            if not conditions or any(
                c.get("status")
                not in ("FEASIBLE", "INFEASIBLE", "UNRESOLVED", "FAILED_REFERENCE")
                or (
                    c.get("status") in ("FEASIBLE", "UNRESOLVED")
                    and (
                        not isinstance(c.get("objective"), (int, float))
                        or not math.isfinite(c["objective"])
                    )
                )
                or not c.get("record_sha256")
                or c.get("image_digest") != manifest.get("image_digest")
                for c in conditions
            ):
                raise LabRefused("bank_condition_record")
        computed, decision_determined = classify(q)
        if q.get("class") != computed:
            raise LabRefused("bank_class_mismatch")
        classes[computed] += 1
        determined += int(decision_determined)
        if computed == "SCORED":
            scored.append(q)
    result = {
        "status": "INSUFFICIENT_EVIDENCE",
        "scope": "DEVELOPMENT_HALF_ONLY",
        "definition_sha256": digest,
        "classes": classes,
        "tasks_present": sorted({q["task"] for q in records}),
        "neighbour_tasks_missing": sorted(tasks - {q["task"] for q in records}),
        "scored_share": len(scored) / len(records),
        "half_or_more_scored": 2 * len(scored) >= len(records),
        "decision_determined_with_unresolved": determined,
        "size_blocker": (
            None if 2 * len(scored) >= len(records) else "scored_share_below_half"
        ),
        "missing_registration": missing,
        "winnability": None,
    }
    values = (cap, kappa, unit, ceiling_threshold)
    if (
        missing
        or result["size_blocker"]
        or result["neighbour_tasks_missing"]
        or manifest.get("train_separation") != "PASS"
        or any(v is None for v in values)
        or cheap is None
        or reference_model is None
        or learnability is None
    ):
        return result
    if (
        not isinstance(cap, int)
        or cap < 1
        or any(
            not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0
            for v in (kappa, unit, ceiling_threshold)
        )
    ):
        raise LabRefused("bank_human_input_invalid")
    if not scored:
        return result
    if set(cheap) != set(ids) or set(reference_model) != set(ids):
        raise LabRefused("bank_predictor_coverage")
    cheap_outcomes = [
        _v2_question(q, cheap[q["question_id"]], cap=cap, kappa=kappa, unit=unit)
        for q in scored
    ]
    model_outcomes = [
        _v2_question(
            q, reference_model[q["question_id"]], cap=cap, kappa=kappa, unit=unit
        )
        for q in scored
    ]
    ceiling = []
    for q in scored:
        base = max(c["objective"] for c in q["actions"][q["fallback_action"]])
        feasible = [
            max(c["objective"] for c in cs)
            for cs in q["actions"].values()
            if all(c["status"] == "FEASIBLE" for c in cs)
        ]
        ceiling.append(max(0.0, (base - min(feasible)) / unit) if feasible else 0.0)
    weights = [q["weight"] for q in scored]
    weighted = lambda xs: sum(w * x for w, x in zip(weights, xs, strict=True)) / sum(
        weights
    )
    denominator = weighted(ceiling)
    capture = (
        weighted([o["G"] for o in cheap_outcomes]) / denominator
        if denominator > 0
        else None
    )
    paired = [
        a["U"] - b["U"] for a, b in zip(model_outcomes, cheap_outcomes, strict=True)
    ]
    blocks = sorted({q["block_id"] for q in scored})
    if len(blocks) < 2:
        return result
    by_block = {
        block: (
            sum(
                p * q["weight"]
                for p, q in zip(paired, scored, strict=True)
                if q["block_id"] == block
            ),
            sum(q["weight"] for q in scored if q["block_id"] == block),
        )
        for block in blocks
    }
    rng = random.Random(20261013)
    boots = []
    for _ in range(replicates):
        sampled = [by_block[rng.choice(blocks)] for _ in blocks]
        boots.append(sum(x[0] for x in sampled) / sum(x[1] for x in sampled))
    ci = _interval(boots)
    sizes = learnability.get("train_sizes") if isinstance(learnability, dict) else None
    accuracies = (
        learnability.get("accuracies") if isinstance(learnability, dict) else None
    )
    if (
        not isinstance(sizes, list)
        or not isinstance(accuracies, list)
        or len(sizes) != len(accuracies)
        or len(sizes) < 2
        or any(
            not isinstance(v, (int, float)) or not math.isfinite(v)
            for v in (*sizes, *accuracies)
        )
        or sizes != sorted(set(sizes))
    ):
        return result
    result["winnability"] = {
        "cheap_ceiling_capture": capture,
        "cheap_below_assumed_threshold": capture is not None
        and capture < ceiling_threshold,
        "paired_net_margin": weighted(paired),
        "paired_margin_block_ci95": ci,
        "paired_lower_positive": ci[0] > 0,
        "always_abstain_U": 0.0,
        "learnability": {
            "train_sizes": sizes,
            "accuracies": accuracies,
            "improves": accuracies[-1] > accuracies[0],
        },
        "blocks": len(blocks),
        "parameters": {
            "k_ASSUMPTION": cap,
            "kappa_ASSUMPTION": kappa,
            "u_ASSUMPTION": unit,
            "ceiling_threshold_ASSUMPTION": ceiling_threshold,
        },
    }
    result["status"] = "DEVELOPMENT_DIAGNOSTIC"
    return result


def read_records(path):
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
