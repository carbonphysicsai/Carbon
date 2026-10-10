"""Conditional cross-window power on a sealed, finite design-question bank.

The bank ledger counts exposure per question and samples distinct live cases
within each window. Repeated questions may appear in later sequential windows
until their registered exposure limit retires them. Repeated questions from one
solved reference bank still contribute only one sign-test cluster.
"""

from __future__ import annotations

import math
import random

from carbon.design_search import tasks

SCHEMA = "carbon.design-search.power-accumulation.v1"
SAMPLING_SCHEMA = "carbon.design-search.window-sampling.v1"
EXPOSURE_UNIT = "per_question_draws"
WINDOW_MODEL = "sequential_registered_stratum_quotas.v1"


def register_accumulation(*, exposure_unit, max_windows):
    """Register the finite-bank window model and simulation horizon."""
    body = {
        "schema": SCHEMA,
        "exposure_unit": exposure_unit,
        "max_windows": max_windows,
        "window_model": WINDOW_MODEL,
    }
    registered = {**body, "registration_digest": tasks.digest(body)}
    validate_accumulation(registered)
    return registered


def validate_accumulation(registration):
    if (
        type(registration) is not dict
        or set(registration)
        != {
            "schema",
            "exposure_unit",
            "max_windows",
            "window_model",
            "registration_digest",
        }
        or registration["schema"] != SCHEMA
        or registration["exposure_unit"] != EXPOSURE_UNIT
        or type(registration["max_windows"]) is not int
        or registration["max_windows"] <= 0
        or registration["window_model"] != WINDOW_MODEL
        or registration["registration_digest"]
        != tasks.digest(
            {
                key: value
                for key, value in registration.items()
                if key != "registration_digest"
            }
        )
    ):
        raise tasks.TaskError("registered per-question accumulation required")


def validate_case_exposure(rows, cases):
    """Return case-to-remaining-draws after validating the sealed ledger."""
    if type(rows) is not list or len(rows) != len(cases):
        raise tasks.TaskError("complete per-question exposure ledger required")
    remaining = {}
    for row in rows:
        if (
            type(row) is not dict
            or set(row) != {"case", "limit", "used"}
            or type(row["case"]) is not str
            or row["case"] not in cases
            or row["case"] in remaining
            or type(row["limit"]) is not int
            or row["limit"] <= 0
            or type(row["used"]) is not int
            or not 0 <= row["used"] <= row["limit"]
        ):
            raise tasks.TaskError("invalid per-question exposure row")
        remaining[row["case"]] = row["limit"] - row["used"]
    if set(remaining) != set(cases):
        raise tasks.TaskError("per-question exposure coverage differs")
    return remaining


def register_window_sampling(*, case_strata, quotas_by_k):
    """Bind the producer's per-case strata and exact quota for each k."""
    body = {
        "schema": SAMPLING_SCHEMA,
        "case_strata": case_strata,
        "quotas_by_k": quotas_by_k,
    }
    return {**body, "registration_digest": tasks.digest(body)}


def validate_window_sampling(registration, cases, max_questions):
    if (
        type(registration) is not dict
        or set(registration)
        != {"schema", "case_strata", "quotas_by_k", "registration_digest"}
        or registration["schema"] != SAMPLING_SCHEMA
        or registration["registration_digest"]
        != tasks.digest(
            {
                key: value
                for key, value in registration.items()
                if key != "registration_digest"
            }
        )
        or type(registration["case_strata"]) is not list
        or type(registration["quotas_by_k"]) is not list
    ):
        raise tasks.TaskError("registered window sampling required")
    strata = {}
    for row in registration["case_strata"]:
        if (
            type(row) is not dict
            or set(row) != {"case", "stratum"}
            or type(row["case"]) is not str
            or row["case"] not in cases
            or row["case"] in strata
            or type(row["stratum"]) is not str
            or not row["stratum"]
        ):
            raise tasks.TaskError("window case stratum registration invalid")
        strata[row["case"]] = row["stratum"]
    if set(strata) != set(cases):
        raise tasks.TaskError("window case strata do not cover sealed bank")
    quotas_by_k = {}
    for row in registration["quotas_by_k"]:
        if (
            type(row) is not dict
            or set(row) != {"questions_per_batch", "quotas"}
            or type(row["questions_per_batch"]) is not int
            or row["questions_per_batch"] <= 0
            or row["questions_per_batch"] in quotas_by_k
            or type(row["quotas"]) is not dict
            or not row["quotas"]
            or any(
                type(name) is not str
                or not name
                or type(count) is not int
                or count <= 0
                for name, count in row["quotas"].items()
            )
            or sum(row["quotas"].values()) != row["questions_per_batch"]
            or ("all" in row["quotas"] and len(row["quotas"]) != 1)
            or any(
                name != "all" and name not in set(strata.values())
                for name in row["quotas"]
            )
        ):
            raise tasks.TaskError("registered window quota invalid")
        quotas_by_k[row["questions_per_batch"]] = row["quotas"]
    if not set(range(1, max_questions + 1)) <= set(quotas_by_k):
        raise tasks.TaskError("window quotas missing a requested k")
    return strata, quotas_by_k


def _one_path(remaining, strata, quotas, *, seed, k, replicate, windows):
    rng = random.Random(f"{seed}:{k}:{replicate}")
    available = dict(remaining)
    drawn = []
    for _ in range(windows):
        live = sorted(case for case, count in available.items() if count > 0)
        chosen = []
        for stratum, count in sorted(quotas.items()):
            pool = [
                case for case in live if stratum == "all" or strata[case] == stratum
            ]
            if len(pool) < count:
                chosen = None
                break
            chosen.extend(rng.sample(pool, count))
        if chosen is None:
            drawn.extend([None] * (windows - len(drawn)))
            break
        for case in chosen:
            available[case] -= 1
        drawn.append(chosen)
    return drawn


def cross_batch_curve(
    case_exposure,
    window_sampling,
    differences,
    clusters,
    *,
    alpha,
    target,
    seed,
    replicates,
    max_questions,
    accumulation,
):
    """Estimate detection for k distinct cases per sequential window.

    A cell with any simulated bank shortage has no detection estimate. This
    sealed-bank conditional simulation does not extrapolate new producer draws
    or future top-ups. It models no overlapping active windows.
    """
    validate_accumulation(accumulation)
    if (
        type(seed) is not int
        or seed < 0
        or type(replicates) is not int
        or replicates <= 0
        or type(max_questions) is not int
        or max_questions <= 0
        or type(differences) is not dict
        or type(clusters) is not dict
        or set(differences) != set(clusters)
    ):
        raise tasks.TaskError("finite registered cross-batch inputs required")
    remaining = validate_case_exposure(case_exposure, differences)
    scorable = any(
        remaining[case] > 0 and difference is not None
        for case, difference in differences.items()
    )
    strata, quotas_by_k = validate_window_sampling(
        window_sampling, differences, max_questions
    )
    from carbon.design_search.power import _sign_test_p

    points = []
    maximum_windows = accumulation["max_windows"]
    for k in range(1, max_questions + 1):
        detected = [0] * maximum_windows
        feasible = [0] * maximum_windows
        nonzero_total = [0] * maximum_windows
        for replicate in range(replicates):
            path = _one_path(
                remaining,
                strata,
                quotas_by_k[k],
                seed=seed,
                k=k,
                replicate=replicate,
                windows=maximum_windows,
            )
            grouped = {}
            for position, chosen in enumerate(path):
                if chosen is None:
                    continue
                for case in chosen:
                    difference = differences[case]
                    if difference is not None:
                        cluster = clusters[case]
                        grouped[cluster] = grouped.get(cluster, 0.0) + difference
                p, nonzero = _sign_test_p(grouped)
                feasible[position] += 1
                detected[position] += p <= alpha
                nonzero_total[position] += nonzero
        for position in range(maximum_windows):
            all_feasible = feasible[position] == replicates
            estimate = (
                detected[position] / replicates if all_feasible and scorable else None
            )
            points.append(
                {
                    "questions_per_batch": k,
                    "windows": position + 1,
                    "total_questions": k * (position + 1),
                    "exposure_feasible": all_feasible,
                    "run_feasible_probability": feasible[position] / replicates,
                    "estimated_detection_probability": estimate,
                    "monte_carlo_standard_error": (
                        math.sqrt(estimate * (1 - estimate) / replicates)
                        if estimate is not None
                        else None
                    ),
                    "mean_nonzero_bank_clusters": (
                        nonzero_total[position] / replicates
                        if all_feasible and scorable
                        else None
                    ),
                }
            )
    first_by_k = []
    for k in range(1, max_questions + 1):
        eligible = [
            point
            for point in points
            if point["questions_per_batch"] == k
            and point["exposure_feasible"]
            and point["estimated_detection_probability"] is not None
        ]
        first = next(
            (
                point["windows"]
                for position, point in enumerate(eligible)
                if all(
                    later["estimated_detection_probability"] >= target
                    for later in eligible[position:]
                )
            ),
            None,
        )
        first_by_k.append(
            {
                "questions_per_batch": k,
                "first_windows_meeting_target_estimate": first,
            }
        )
    return {
        "schema": SCHEMA,
        "window_model": WINDOW_MODEL,
        "conditional_on_sealed_bank": True,
        "future_batch_probability": False,
        "exposure_unit": EXPOSURE_UNIT,
        "question_count": len(remaining),
        "total_remaining_question_draws": sum(remaining.values()),
        "max_windows_requested": maximum_windows,
        "first_windows_by_questions_per_batch": first_by_k,
        "points": points,
    }
