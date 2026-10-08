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
EXPOSURE_UNIT = "per_question_draws"
WINDOW_MODEL = "sequential_uniform_live_cases.v1"


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


def _one_path(remaining, *, seed, k, replicate, windows):
    rng = random.Random(f"{seed}:{k}:{replicate}")
    available = dict(remaining)
    drawn = []
    for _ in range(windows):
        live = sorted(case for case, count in available.items() if count > 0)
        if len(live) < k:
            drawn.extend([None] * (windows - len(drawn)))
            break
        chosen = rng.sample(live, k)
        for case in chosen:
            available[case] -= 1
        drawn.append(chosen)
    return drawn


def cross_batch_curve(
    case_exposure,
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
            estimate = detected[position] / replicates if all_feasible else None
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
                        nonzero_total[position] / replicates if all_feasible else None
                    ),
                }
            )
    first_by_k = []
    for k in range(1, max_questions + 1):
        eligible = [
            point
            for point in points
            if point["questions_per_batch"] == k and point["exposure_feasible"]
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
