"""Producer-side V2 bank plan and aggregate checks; never runs a solver.

The registered question-law drawer supplies committed contexts from P. This
module does not invent a population, a proposal law, a reference policy or a
value threshold. Its full plan and jobs are producer-only; `bank.check` sees
only the public development records.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter

from . import bank
from .core import LabRefused

SCHEMA = "carbon.value-v2.bank-plan.v1"
REGISTRATION = "carbon.value-v2.bank-registration.v1"
DRAWS = "carbon.value-v2.question-draws.v1"
COST = "carbon.value-v2.reference-cost.v1"
JOBS = "carbon.value-v2.launcher-jobs.v1"
STATUSES = frozenset({"FEASIBLE", "INFEASIBLE", "UNRESOLVED", "FAILED_REFERENCE"})


def digest(value):
    try:
        body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise LabRefused("bank_noncanonical_input") from error
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _sha(value):
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(c in "0123456789abcdef" for c in value[7:])
    )


def _token(value):
    return isinstance(value, str) and bool(value) and len(value) <= 128


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _reference_status_rule(value):
    """Validate the registered rung and band contract, without choosing it."""
    fields = {
        "id",
        "margin_quantity",
        "margin_unit",
        "coarse_rung",
        "fine_rung",
        "coarse_window",
        "feasible_direction",
        "bands",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or any(
            not _token(value.get(key))
            for key in ("id", "margin_quantity", "margin_unit", "coarse_rung")
        )
    ):
        raise LabRefused("bank_reference_status_rule")
    if value.get("feasible_direction") != "positive":
        raise LabRefused("bank_reference_status_rule")
    fine = value["fine_rung"]
    window = value["coarse_window"]
    if (fine is None) != (window is None) or (fine is not None and not _token(fine)):
        raise LabRefused("bank_reference_status_rule")
    expected_rungs = {value["coarse_rung"]} | ({fine} if fine is not None else set())
    if (
        len(expected_rungs) != (2 if fine is not None else 1)
        or not isinstance(value["bands"], dict)
        or set(value["bands"]) != expected_rungs
    ):
        raise LabRefused("bank_reference_status_rule")
    for band in [*value["bands"].values(), *([window] if window is not None else [])]:
        if (
            not isinstance(band, list)
            or len(band) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in band)
            or band[0] >= band[1]
        ):
            raise LabRefused("bank_reference_status_rule")
    return value


def plan(registration, draws, *, definition_bytes, split_seed):
    """Enumerate the precommitted draw under every action and condition.

    The caller is the producer. `draws_digest` and both seed commitments must
    be registered before any reference result; this function cannot draw P.
    """
    if not isinstance(registration, dict) or registration.get("schema") != REGISTRATION:
        raise LabRefused("bank_registration_schema")
    if not isinstance(draws, dict) or draws.get("schema") != DRAWS:
        raise LabRefused("bank_draws_schema")
    definition = json.loads(definition_bytes)
    if definition.get("id") != "VALUE-METRIC-V2" or definition.get("revision") != 2:
        raise LabRefused("bank_definition_version")
    if (
        registration.get("definition_digest")
        != "sha256:" + hashlib.sha256(definition_bytes).hexdigest()
    ):
        raise LabRefused("bank_definition_digest")
    for field in (
        "question_law_digest",
        "population_digest",
        "proposal_digest",
        "weights_digest",
        "image_digest",
        "overlay_lock_digest",
        "mms_acceptance_digest",
        "validity_envelope_digest",
        "reference_policy_digest",
        "cost_policy_digest",
        "block_independence_digest",
        "draws_digest",
        "split_seed_commitment",
    ):
        if not _sha(registration.get(field)):
            raise LabRefused("bank_registration_digest_" + field)
    if registration["draws_digest"] != digest(draws):
        raise LabRefused("bank_draws_digest")
    if draws.get("question_law_digest") != registration["question_law_digest"]:
        raise LabRefused("bank_draw_law_mismatch")
    if (
        draws.get("draw_role") != "P"
        or draws.get("population_digest") != registration["population_digest"]
        or draws.get("weights_digest") != registration["weights_digest"]
    ):
        raise LabRefused("bank_draw_population_mismatch")
    if not _sha(draws.get("drawer_seed_commitment")):
        raise LabRefused("bank_draw_seed_commitment")
    if not isinstance(split_seed, str) or not split_seed:
        raise LabRefused("bank_split_seed_missing")
    split_commitment = "sha256:" + hashlib.sha256(split_seed.encode()).hexdigest()
    if split_commitment != registration["split_seed_commitment"]:
        raise LabRefused("bank_split_seed_commitment")
    if registration.get("objective_aggregation") != "worst_case":
        raise LabRefused("bank_objective_aggregation_unsupported")
    if registration.get("objective_sense") != "minimize":
        raise LabRefused("bank_objective_sense_unsupported")
    _reference_status_rule(registration.get("reference_status_rule"))
    separation = registration.get("train_separation")
    if (
        not isinstance(separation, dict)
        or separation.get("status") != "PASS"
        or not _sha(separation.get("evidence_digest"))
    ):
        raise LabRefused("bank_train_separation_unregistered")
    cheap = registration.get("cheap_arm_registration")
    if (
        not isinstance(cheap, dict)
        or cheap.get("status") != "FROZEN_BEFORE_DRAW"
        or not _sha(cheap.get("evidence_digest"))
    ):
        raise LabRefused("bank_cheap_arm_not_frozen")
    alpha = registration.get("alpha")
    if not _positive(alpha) or alpha >= 1:
        raise LabRefused("bank_alpha_human_input")
    minimum = math.ceil(math.log2(1 / alpha))
    actions = registration.get("actions")
    if (
        not isinstance(actions, list)
        or not actions
        or any(
            not isinstance(a, dict) or not _token(a.get("id")) or "value" not in a
            for a in actions
        )
    ):
        raise LabRefused("bank_actions_registration")
    action_ids = [a["id"] for a in actions]
    if len(set(action_ids)) != len(action_ids):
        raise LabRefused("bank_duplicate_action")
    neighbours = registration.get("neighbour_declarations")
    if not isinstance(neighbours, list) or any(
        not isinstance(n, dict) or not _token(n.get("id")) for n in neighbours
    ):
        raise LabRefused("bank_neighbour_declarations_missing")
    tasks = {"target", *(n["id"] for n in neighbours)}
    if len(tasks) != 1 + len(neighbours):
        raise LabRefused("bank_duplicate_task")
    contexts = draws.get("contexts")
    if not isinstance(contexts, list) or not contexts:
        raise LabRefused("bank_draws_empty")
    question_ids = []
    blocks = {}
    for q in contexts:
        if (
            not isinstance(q, dict)
            or not _token(q.get("question_id"))
            or not _token(q.get("block_id"))
            or q.get("task") not in tasks
            or q.get("fallback_action") not in action_ids
            or not _positive(q.get("weight"))
            or not isinstance(q.get("context"), dict)
            or not isinstance(q.get("physical_context"), dict)
            or not isinstance(q.get("conditions"), list)
            or not q["conditions"]
            or any(
                not isinstance(c, dict)
                or not _token(c.get("id"))
                or not isinstance(c.get("value"), dict)
                for c in q["conditions"]
            )
        ):
            raise LabRefused("bank_draw_question_shape")
        condition_ids = [c["id"] for c in q["conditions"]]
        if len(condition_ids) != len(set(condition_ids)):
            raise LabRefused("bank_duplicate_condition")
        question_ids.append(q["question_id"])
        blocks.setdefault(q["block_id"], set()).add(q["task"])
    if len(set(question_ids)) != len(question_ids):
        raise LabRefused("bank_duplicate_question")
    if any(seen != tasks for seen in blocks.values()):
        raise LabRefused("bank_block_missing_task")
    if len(blocks) // 2 < minimum:
        raise LabRefused("bank_confirmation_blocks_below_alpha_minimum")
    ordered_blocks = sorted(
        blocks,
        key=lambda b: (hashlib.sha256((split_seed + ":" + b).encode()).hexdigest(), b),
    )
    confirmation = set(ordered_blocks[: len(blocks) // 2])
    questions = [
        {
            **q,
            "half": "confirmation" if q["block_id"] in confirmation else "development",
        }
        for q in contexts
    ]
    jobs_by_id = {}
    requirements = []
    job_block = {}
    for q in questions:
        for action in actions:
            for condition in q["conditions"]:
                key = {
                    "image_digest": registration["image_digest"],
                    "reference_policy_digest": registration["reference_policy_digest"],
                    "physical_context": q["physical_context"],
                    "action": action["value"],
                    "condition": condition["value"],
                }
                job_id = digest(key)
                if job_id in job_block and job_block[job_id] != q["block_id"]:
                    raise LabRefused("bank_block_reference_case_overlap")
                job_block[job_id] = q["block_id"]
                requirements.append(
                    {
                        "question_id": q["question_id"],
                        "action_id": action["id"],
                        "condition_id": condition["id"],
                        "job_id": job_id,
                    }
                )
                jobs_by_id.setdefault(
                    job_id,
                    {
                        "job_id": job_id,
                        "role": "HELDOUT_REFERENCE",
                        "half": q["half"],
                        "action": action["value"],
                        "context": q["physical_context"],
                        "condition": condition["value"],
                        "image_digest": registration["image_digest"],
                        "overlay_lock_digest": registration["overlay_lock_digest"],
                        "reference_policy_digest": registration[
                            "reference_policy_digest"
                        ],
                    },
                )
    manifest = {
        field: registration[field]
        for field in (
            "definition_digest",
            "question_law_digest",
            "population_digest",
            "proposal_digest",
            "weights_digest",
            "image_digest",
            "overlay_lock_digest",
            "mms_acceptance_digest",
            "validity_envelope_digest",
            "reference_policy_digest",
            "cost_policy_digest",
            "block_independence_digest",
            "cheap_arm_registration",
            "objective_aggregation",
            "objective_sense",
            "reference_status_rule",
            "neighbour_declarations",
        )
    }
    manifest.update(
        {
            "drawer_seed_commitment": draws["drawer_seed_commitment"],
            "train_separation": "PASS",
            "train_separation_evidence_digest": registration["train_separation"][
                "evidence_digest"
            ],
            "draws_digest": registration["draws_digest"],
            "split_seed_commitment": split_commitment,
            "confirmation_blocks": len(confirmation),
            "minimum_confirmation_blocks": minimum,
        }
    )
    return {
        "schema": SCHEMA,
        "scope": "PRODUCER_ONLY",
        "registration_digest": digest(registration),
        "reference_policy_digest": registration["reference_policy_digest"],
        "cost_policy_digest": registration["cost_policy_digest"],
        "action_ids": action_ids,
        "manifest": manifest,
        "questions": questions,
        "requirements": requirements,
        "jobs": list(jobs_by_id.values()),
    }


def _require_registered_plan(
    planned, registration, draws, definition_bytes, split_seed
):
    """Replay from registered producer inputs before trusting a serialized plan."""
    if not isinstance(planned, dict):
        raise LabRefused("bank_plan_schema")
    replay = plan(
        registration, draws, definition_bytes=definition_bytes, split_seed=split_seed
    )
    if digest(planned) != digest(replay):
        raise LabRefused("bank_plan_content_mismatch")


def launcher_jobs(planned, *, registration, draws, definition_bytes, split_seed):
    """Project only physical work needed by a producer-controlled solve worker."""
    _require_registered_plan(planned, registration, draws, definition_bytes, split_seed)
    allowed = (
        "job_id",
        "role",
        "action",
        "context",
        "condition",
        "image_digest",
        "overlay_lock_digest",
        "reference_policy_digest",
    )
    return {
        "schema": JOBS,
        "scope": "PRODUCER_WORKER_ONLY",
        "jobs": [{key: job[key] for key in allowed} for job in planned["jobs"]],
    }


def check_solved(
    planned,
    records,
    *,
    registration,
    draws,
    definition_bytes,
    split_seed,
    **winnability,
):
    """Check complete producer records, then evaluate only the public half.

    The return value contains aggregate counts, never confirmation cases,
    actions, values or protected IDs. The full `planned` input stays private.
    """
    _require_registered_plan(planned, registration, draws, definition_bytes, split_seed)
    expected = {q["question_id"]: q for q in planned["questions"]}
    expected_jobs = {
        (j["question_id"], j["action_id"], j["condition_id"]): j["job_id"]
        for j in planned["requirements"]
    }
    status_rule = planned["manifest"]["reference_status_rule"]
    if (
        not isinstance(records, list)
        or len(records) != len(expected)
        or {r.get("question_id") for r in records if isinstance(r, dict)}
        != set(expected)
    ):
        raise LabRefused("bank_solved_question_coverage")
    by_half = {"development": [], "confirmation": []}
    solve_digests = {}
    for r in records:
        q = expected[r["question_id"]]
        for field in ("block_id", "task", "half", "fallback_action", "weight"):
            if r.get(field) != q[field]:
                raise LabRefused("bank_solved_identity_mismatch")
        if not isinstance(r.get("actions"), dict) or set(r["actions"]) != set(
            planned["action_ids"]
        ):
            raise LabRefused("bank_solved_action_coverage")
        ids = [c["id"] for c in q["conditions"]]
        for action_id, conditions in r["actions"].items():
            if (
                not isinstance(conditions, list)
                or [c.get("condition_id") for c in conditions] != ids
            ):
                raise LabRefused("bank_solved_condition_coverage")
            if any(
                c.get("status") not in STATUSES
                or c.get("job_id")
                != expected_jobs.get((r["question_id"], action_id, c["condition_id"]))
                or not _sha(c.get("record_sha256"))
                or c.get("image_digest") != planned["manifest"]["image_digest"]
                or c.get("overlay_lock_digest")
                != planned["manifest"]["overlay_lock_digest"]
                or (
                    c["status"] == "FAILED_REFERENCE"
                    and c.get("retry_exhausted") is not True
                )
                or (
                    c["status"] != "FAILED_REFERENCE"
                    and (
                        not isinstance(c.get("margins"), dict)
                        or not c["margins"]
                        or any(
                            not _token(quantity)
                            or type(margin) not in (int, float)
                            or not math.isfinite(margin)
                            for quantity, margin in c["margins"].items()
                        )
                    )
                )
                or (
                    c["status"] in ("FEASIBLE", "UNRESOLVED")
                    and not (
                        type(c.get("objective")) in (int, float)
                        and math.isfinite(c["objective"])
                    )
                )
                for c in conditions
            ):
                raise LabRefused("bank_solved_reference_record")
            for c in conditions:
                rung = c.get("rung")
                band = status_rule["bands"].get(rung)
                if (
                    c.get("reference_rule_id") != status_rule["id"]
                    or band is None
                    or c.get("band") != band
                    or c.get("band_unit") != status_rule["margin_unit"]
                ):
                    raise LabRefused("bank_reference_rung_band")
                if c["status"] != "FAILED_REFERENCE":
                    margin = c["margins"].get(status_rule["margin_quantity"])
                    if type(margin) not in (int, float) or not math.isfinite(margin):
                        raise LabRefused("bank_reference_margin_quantity")
                    window = status_rule["coarse_window"]
                    if window is not None:
                        coarse_margin = c.get("coarse_margin")
                        if type(coarse_margin) not in (int, float) or not math.isfinite(
                            coarse_margin
                        ):
                            raise LabRefused("bank_reference_coarse_margin")
                        if (
                            rung == status_rule["coarse_rung"]
                            and coarse_margin != margin
                        ):
                            raise LabRefused("bank_reference_coarse_margin")
                        if (
                            window[0] < coarse_margin < window[1]
                            and rung != status_rule["fine_rung"]
                            and c["status"] in ("FEASIBLE", "INFEASIBLE")
                        ):
                            raise LabRefused("bank_in_window_unresolved_required")
                    if c["status"] == "FEASIBLE" and margin < band[1]:
                        raise LabRefused("bank_reference_band_status")
                previous = solve_digests.setdefault(c["job_id"], c["record_sha256"])
                if previous != c["record_sha256"]:
                    raise LabRefused("bank_reused_solve_digest_mismatch")
        computed, _ = bank.classify(r)
        if r.get("class") != computed:
            raise LabRefused("bank_class_mismatch")
        by_half[r["half"]].append(r)
    if not by_half["development"] or not by_half["confirmation"]:
        raise LabRefused("bank_split_empty")
    blocks = {half: {q["block_id"] for q in rows} for half, rows in by_half.items()}
    if blocks["development"] & blocks["confirmation"]:
        raise LabRefused("bank_block_crosses_halves")
    if len(blocks["confirmation"]) < planned["manifest"]["minimum_confirmation_blocks"]:
        raise LabRefused("bank_confirmation_blocks_below_alpha_minimum")
    counts = {
        half: dict(Counter(q["class"] for q in rows)) for half, rows in by_half.items()
    }
    determined = {
        half: dict(Counter(q["class"] for q in rows if bank.classify(q)[1]))
        for half, rows in by_half.items()
    }
    shares = {
        half: counts[half].get("SCORED", 0) / len(rows)
        for half, rows in by_half.items()
    }
    overall_scored_share = sum(c.get("SCORED", 0) for c in counts.values()) / len(
        records
    )
    development = bank.check(
        planned["manifest"],
        by_half["development"],
        definition_bytes=definition_bytes,
        **winnability,
    )
    structural_ready = overall_scored_share >= 0.5
    measured = development.get("winnability")
    if not structural_ready or measured is None:
        status = "INSUFFICIENT_EVIDENCE"
    elif (
        measured["cheap_below_assumed_threshold"]
        and measured["paired_lower_positive"]
        and measured["always_abstain_U"] == 0
        and measured["learnability"]["improves"]
    ):
        status = "DEVELOPMENT_WINNABLE_DIAGNOSTIC"
    else:
        status = "DEVELOPMENT_NOT_WINNABLE_DIAGNOSTIC"
    return {
        "status": status,
        "structural_ready": structural_ready,
        "scope": "AGGREGATES_ONLY_NO_CONFIRMATION_VALUES",
        "question_count": len(records),
        "job_count": len(planned["jobs"]),
        "block_counts": {half: len(ids) for half, ids in blocks.items()},
        "class_counts": counts,
        "decision_determined_with_unresolved_by_class": determined,
        "scored_share": shares,
        "overall_scored_share": overall_scored_share,
        "development_winnability": development,
    }


def reference_cost(
    planned, policy, coarse=None, *, registration, draws, definition_bytes, split_seed
):
    """Cost actual planned jobs; refinement depends on this bank's margins."""
    _require_registered_plan(planned, registration, draws, definition_bytes, split_seed)
    if (
        not isinstance(policy, dict)
        or policy.get("schema") != COST
        or digest(policy) != planned.get("cost_policy_digest")
        or policy.get("reference_policy_digest")
        != planned.get("reference_policy_digest")
    ):
        raise LabRefused("bank_cost_policy_identity")
    for key in ("coarse_cpu_s", "coarse_wall_s"):
        if not _positive(policy.get(key)):
            raise LabRefused("bank_reference_cost_invalid")
    jobs = planned["jobs"]
    cpu_s = len(jobs) * policy["coarse_cpu_s"]
    wall_s = len(jobs) * policy["coarse_wall_s"]
    out = {
        "coarse_jobs": len(jobs),
        "coarse_cpu_hours": cpu_s / 3600,
        "coarse_serial_wall_hours": wall_s / 3600,
        "refinement_status": "NOT_REQUIRED",
        "in_window_share": None,
        "refinement_jobs": [],
        "total_cpu_hours": cpu_s / 3600,
        "total_serial_wall_hours": wall_s / 3600,
    }
    refinement = policy.get("refinement")
    status_rule = planned["manifest"]["reference_status_rule"]
    if refinement is None:
        if status_rule["fine_rung"] is not None:
            raise LabRefused("bank_required_refinement_cost_missing")
        return out
    if not isinstance(refinement, dict):
        raise LabRefused("bank_refinement_policy_invalid")
    for key in ("fine_cpu_s", "fine_wall_s", "trigger_cpu_s", "trigger_wall_s"):
        if not _positive(refinement.get(key)):
            raise LabRefused("bank_refinement_cost_invalid")
    window = refinement.get("margin_window")
    if not isinstance(window, (list, tuple)) or len(window) != 2:
        raise LabRefused("bank_refinement_policy_invalid")
    low, high = window
    fraction = refinement.get("trigger_fraction")
    if (
        type(low) not in (int, float)
        or type(high) not in (int, float)
        or not math.isfinite(low)
        or not math.isfinite(high)
        or not low < high
        or not _token(refinement.get("margin_quantity"))
        or not _token(refinement.get("margin_unit"))
        or type(fraction) not in (int, float)
        or not math.isfinite(fraction)
        or not 0 <= fraction <= 1
        or refinement.get("margin_quantity") != status_rule["margin_quantity"]
        or refinement.get("margin_unit") != status_rule["margin_unit"]
        or window != status_rule["coarse_window"]
        or refinement.get("fine_rung") != status_rule["fine_rung"]
        or not _token(refinement.get("trigger_rung"))
        or refinement.get("trigger_rung") in status_rule["bands"]
    ):
        raise LabRefused("bank_refinement_policy_invalid")
    if coarse is None:
        out["refinement_status"] = "UNKNOWN_UNTIL_COARSE"
        out["total_cpu_hours"] = None
        out["total_serial_wall_hours"] = None
        return out
    if not isinstance(coarse, dict) or set(coarse) != {j["job_id"] for j in jobs}:
        raise LabRefused("bank_coarse_coverage")
    in_window = []
    for job in jobs:
        row = coarse[job["job_id"]]
        if (
            not isinstance(row, dict)
            or not _sha(row.get("record_sha256"))
            or row.get("image_digest") != job["image_digest"]
            or row.get("overlay_lock_digest") != job["overlay_lock_digest"]
            or row.get("reference_policy_digest") != job["reference_policy_digest"]
            or row.get("margin_quantity") != refinement["margin_quantity"]
            or row.get("margin_unit") != refinement["margin_unit"]
            or not (
                type(row.get("margin")) in (int, float) and math.isfinite(row["margin"])
            )
        ):
            raise LabRefused("bank_coarse_margin_record")
        if low < row["margin"] < high:
            in_window.append(job["job_id"])
    fine_jobs = [
        {
            "source_job_id": job_id,
            "rung": refinement["fine_rung"],
            "reference_policy_digest": planned["reference_policy_digest"],
            "cost_policy_digest": digest(policy),
        }
        for job_id in in_window
    ]
    count = math.ceil(fraction * len(in_window))
    chosen = sorted(
        in_window, key=lambda job_id: hashlib.sha256(job_id.encode()).hexdigest()
    )[:count]
    trigger_jobs = [
        {
            "source_job_id": job_id,
            "rung": refinement["trigger_rung"],
            "reference_policy_digest": planned["reference_policy_digest"],
            "cost_policy_digest": digest(policy),
        }
        for job_id in chosen
    ]
    cpu_s += (
        len(fine_jobs) * refinement["fine_cpu_s"]
        + len(trigger_jobs) * refinement["trigger_cpu_s"]
    )
    wall_s += (
        len(fine_jobs) * refinement["fine_wall_s"]
        + len(trigger_jobs) * refinement["trigger_wall_s"]
    )
    out.update(
        {
            "refinement_status": "BANK_COMPOSITION_MEASURED",
            "in_window_share": len(in_window) / len(jobs),
            "fine_jobs": len(fine_jobs),
            "trigger_jobs": len(trigger_jobs),
            "refinement_jobs": fine_jobs + trigger_jobs,
            "total_cpu_hours": cpu_s / 3600,
            "total_serial_wall_hours": wall_s / 3600,
        }
    )
    return out
