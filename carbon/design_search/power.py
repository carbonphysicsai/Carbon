"""Aggregate producer power diagnostics for registered design questions.

This DEVELOPMENT harness uses synthetic reference tables only. It never
chooses an alpha, power target, severity, question law or score policy.
"""

from __future__ import annotations

import bisect
import math
import random

from carbon.design_search import (
    controls,
    diversity,
    power_accumulation,
    reference_resolution,
    tasks,
)

GOOD_SCHEMA = "carbon.design-search.reference-predictor.v1"
REPORT_SCHEMA = "carbon.design-search.power-report.v1"
METRICS = ("false_feasible", "missed_opportunity", "regret")


def register_good_predictor(cases):
    body = {"schema": GOOD_SCHEMA, "cases": cases}
    return {**body, "registration_digest": tasks.digest(body)}


def _registered_good(good):
    if (
        type(good) is not dict
        or set(good) != {"schema", "cases", "registration_digest"}
        or good["schema"] != GOOD_SCHEMA
        or good["registration_digest"]
        != tasks.digest({k: v for k, v in good.items() if k != "registration_digest"})
        or type(good["cases"]) is not list
    ):
        raise tasks.TaskError("registered reference predictor required")


def _panel(rows, task):
    if type(rows) is not list:
        raise tasks.TaskError("complete reference panel required")
    expected = {(c, k["id"]) for c in task["candidates"] for k in task["conditions"]}
    needed = {task["objective"]["quantity"]}
    needed.update(limit["quantity"] for limit in task["limits"])
    if task["secondary"] is not None:
        needed.add(task["secondary"]["quantity"])
    panel = {}
    for row in rows:
        if (
            type(row) is not dict
            or set(row) != {"candidate", "condition", "values"}
            or (row["candidate"], row["condition"]) not in expected
            or (row["candidate"], row["condition"]) in panel
            or type(row["values"]) is not dict
            or not needed <= set(row["values"])
            or any(
                type(value) not in (int, float) or not math.isfinite(value)
                for value in row["values"].values()
            )
        ):
            raise tasks.TaskError("invalid reference predictor panel")
        panel[(row["candidate"], row["condition"])] = row["values"]
    if set(panel) != expected:
        raise tasks.TaskError("reference predictor panel is incomplete")
    return panel


def _validate_inputs(bank, laws, registration, good):
    _registered_good(good)
    if (
        type(laws) is not dict
        or not laws
        or not set(laws) <= {"grid", "continuous"}
        or any(type(laws[k]) is not dict for k in laws)
        or any(laws[k].get("kind") != k for k in laws)
        or len({laws[k].get("batch_size") for k in laws}) != 1
    ):
        raise tasks.TaskError("matching registered question laws required")
    diversity_views = {
        kind: diversity.diversity_report(bank, law) for kind, law in laws.items()
    }
    if type(bank.get("power_cases")) is not list or not bank["power_cases"]:
        raise tasks.TaskError("sealed power cases required")
    if "refinement_rule" in bank:
        reference_resolution.validate_rule(bank["refinement_rule"])
    controls.validate_controls(registration, task=None)
    case_rows = {row["case"]: row for row in bank["cases"]}
    support = (
        {row["support_case"] for row in bank["power_cases"]}
        if bank.get("exposure_unit") == power_accumulation.EXPOSURE_UNIT
        else {row["support_case"] for row in bank["exposure"]}
    )
    good_rows = {}
    for row in good["cases"]:
        if (
            type(row) is not dict
            or set(row) != {"case", "predictions"}
            or row["case"] in good_rows
        ):
            raise tasks.TaskError("invalid reference predictor case")
        good_rows[row["case"]] = row["predictions"]
    if set(good_rows) != set(case_rows):
        raise tasks.TaskError("reference predictor cases do not match sealed bank")
    power_rows = {}
    bank_group_identity = {}
    objective_identity = None
    for row in bank["power_cases"]:
        if (
            type(row) is not dict
            or set(row)
            != (
                {"case", "support_case", "task", "reference"}
                | ({"settled"} if "refinement_rule" in bank else set())
            )
            or row["case"] not in case_rows
            or row["case"] in power_rows
            or row["support_case"] not in support
            or type(row["task"]) is not dict
            or row["task"].get("schema") != tasks.RUNNABLE_SCHEMA
        ):
            raise tasks.TaskError("invalid sealed power case")
        task = row["task"]
        tasks._verify_task_digest(task)
        current_objective = (
            task["objective"]["quantity"],
            task["objective"]["unit"],
            task["objective"]["sense"],
        )
        if objective_identity is None:
            objective_identity = current_objective
        elif current_objective != objective_identity:
            raise tasks.TaskError("power questions must share an objective definition")
        reference = _panel(row["reference"], task)
        known_good = _panel(good_rows[row["case"]], task)
        if known_good != reference:
            raise tasks.TaskError(
                "known-good predictor differs from full reference panel"
            )
        if "settled" in row:
            truth = reference_resolution.assessed(task, reference, row["settled"])
            state, winner = reference_resolution.state_and_winner(task, truth)
        else:
            truth = tasks.assess(task, reference, reference=True)
            resolved = all(v["feasible"] is not None for v in truth.values())
            state = tasks.reference_state(task, truth) if resolved else "UNRESOLVED"
            winner = tasks.select(task, truth) if resolved else None
        if (
            case_rows[row["case"]]["state"] != state
            or case_rows[row["case"]]["winner"] != winner
        ):
            raise tasks.TaskError("sealed case summary differs from reference panel")
        for spec in registration["controls"]:
            controls._validate_control(spec, task)
        identity = tasks.digest(
            {
                "bank": task["bank_digest"],
                "reference_bank": task["identity"]["reference_bank"],
                "reference": row["reference"],
            }
        )
        previous = bank_group_identity.setdefault(row["support_case"], identity)
        if previous != identity:
            raise tasks.TaskError(
                "shared bank cluster has different reference material"
            )
        power_rows[row["case"]] = (
            task,
            reference,
            known_good,
            row["support_case"],
            row.get("settled"),
        )
    if set(power_rows) != set(case_rows):
        raise tasks.TaskError("sealed power cases do not cover bank")
    if support != {row[3] for row in power_rows.values()}:
        raise tasks.TaskError("exposure ledger and power bank clusters differ")
    return diversity_views, power_rows, objective_identity[1]


def _run_case(task, reference, known_good, specs, settled=None):
    action_index = {
        tasks.digest(action): candidate for candidate, action in task["actions"].items()
    }
    queried = set()

    def lookup(action, condition):
        key = tasks.digest(action)
        queried.add(key)
        return dict(known_good[(action_index[key], condition["id"])])

    good_commit = tasks.run_optimizer(task, lookup, model_id="REFERENCE")["commitment"]
    judge = (
        (
            lambda commitment: reference_resolution.judge(
                task, commitment, reference, settled
            )
        )
        if settled is not None
        else (lambda commitment: tasks.judge(task, commitment, reference))
    )
    good_outcome = judge(good_commit)
    out = []
    for index, spec in enumerate(specs):

        def predict(action, condition, spec=spec):
            row = known_good[(action_index[tasks.digest(action)], condition["id"])]
            return controls.task_control_prediction(
                task, spec, action, condition, row, accurate_actions=queried
            )

        commitment = tasks.run_optimizer(task, predict, model_id=f"CONTROL-{index}")[
            "commitment"
        ]
        out.append(judge(commitment))
    return good_outcome, out


def _loss(outcome, metric):
    if outcome["reference_resolved"] is not True:
        return None
    if metric == "false_feasible":
        return float(outcome["kind"] == "SELECTED_INFEASIBLE")
    if metric == "missed_opportunity":
        return float(outcome["kind"] == "MISSED_OPPORTUNITY")
    return outcome["regret"]


def _weighted(values, masses):
    denominator = sum(masses[c] for c, value in values.items() if value is not None)
    return (
        sum(masses[c] * value for c, value in values.items() if value is not None)
        / denominator
        if denominator
        else None
    )


def _rate(outcomes, kind, resolved, masses):
    return _weighted(
        {
            case: float(value["kind"] == kind) if resolved[case] else None
            for case, value in outcomes.items()
        },
        masses,
    )


def _sign_test_p(cluster_differences):
    positive = sum(value > 0 for value in cluster_differences.values())
    negative = sum(value < 0 for value in cluster_differences.values())
    nonzero = positive + negative
    if not nonzero or not positive:
        return 1.0, nonzero
    return (
        sum(math.comb(nonzero, i) for i in range(positive, nonzero + 1)) / (2**nonzero),
        nonzero,
    )


def _draws(law, key, *, seed, replicates, maximum):
    cumulative = []
    total = 0.0
    for bin_ in law["bins"]:
        total += bin_[key]
        cumulative.append(total)
    rng = random.Random(seed)
    return [
        [
            law["bins"][
                min(bisect.bisect_left(cumulative, rng.random()), len(cumulative) - 1)
            ]["case"]
            for _ in range(maximum)
        ]
        for _ in range(replicates)
    ]


def _power_curve(
    law,
    key,
    differences,
    clusters,
    *,
    alpha,
    target,
    seed,
    replicates,
    maximum,
    registered_batch,
):
    if maximum == 0:
        return {
            "first_questions_meeting_target_estimate": None,
            "at_registered_batch_size": None,
            "points": [],
        }
    batches = _draws(law, key, seed=seed, replicates=replicates, maximum=maximum)
    points = []
    for k in range(1, maximum + 1):
        detected = 0
        nonzero_total = 0
        for batch in batches:
            grouped = {}
            for case in batch[:k]:
                difference = differences.get(case)
                if difference is not None:
                    group = clusters[case]
                    grouped[group] = grouped.get(group, 0.0) + difference
            p, nonzero = _sign_test_p(grouped)
            detected += p <= alpha
            nonzero_total += nonzero
        estimate = detected / replicates
        points.append(
            {
                "questions": k,
                "estimated_detection_probability": estimate,
                "monte_carlo_standard_error": math.sqrt(
                    estimate * (1 - estimate) / replicates
                ),
                "mean_nonzero_bank_clusters": nonzero_total / replicates,
            }
        )
    # A single Monte Carlo crossing can be noise. Require the target at this
    # size and every larger simulated size before reporting an estimate.
    first = next(
        (
            point["questions"]
            for index, point in enumerate(points)
            if all(
                later["estimated_detection_probability"] >= target
                for later in points[index:]
            )
        ),
        None,
    )
    return {
        "first_questions_meeting_target_estimate": first,
        "at_registered_batch_size": (
            points[registered_batch - 1] if registered_batch <= maximum else None
        ),
        "points": points,
    }


def _view(
    law,
    key,
    cases,
    clusters,
    specs,
    *,
    alpha,
    target,
    seed,
    replicates,
    maximum,
):
    masses = {case: 0.0 for case in cases}
    for bin_ in law["bins"]:
        masses[bin_["case"]] += bin_[key]
    controls_out = []
    good = {case: value[0] for case, value in cases.items()}
    for index, spec in enumerate(specs):
        model = {case: value[1][index] for case, value in cases.items()}
        resolved = {
            case: good[case]["reference_resolved"] is True
            and model[case]["reference_resolved"] is True
            for case in cases
        }
        metrics = {}
        for metric in METRICS:
            good_loss = {case: _loss(value, metric) for case, value in good.items()}
            model_loss = {case: _loss(value, metric) for case, value in model.items()}
            common = {
                case: (
                    (model_loss[case] - good_loss[case])
                    if model_loss[case] is not None and good_loss[case] is not None
                    else None
                )
                for case in cases
            }
            metric_view = {
                "good": _weighted(
                    {c: good_loss[c] if common[c] is not None else None for c in cases},
                    masses,
                ),
                "control": _weighted(
                    {
                        c: model_loss[c] if common[c] is not None else None
                        for c in cases
                    },
                    masses,
                ),
                "common_mass": sum(masses[c] for c in cases if common[c] is not None),
                "power": _power_curve(
                    law,
                    key,
                    common,
                    clusters,
                    alpha=alpha,
                    target=target,
                    seed=seed,
                    replicates=replicates,
                    maximum=maximum,
                    registered_batch=law["batch_size"],
                ),
            }
            metrics[metric] = metric_view
        controls_out.append(
            {
                "control_index": index,
                "kind": spec["kind"],
                "scope": spec.get("scope"),
                "severity": spec["severity"],
                "metrics": metrics,
                "unscored_control_mass": sum(
                    masses[case]
                    for case in cases
                    if good[case]["reference_resolved"] is True
                    and model[case]["reference_resolved"] is not True
                ),
                "abstention_outcomes": {
                    "good": {
                        "missed_opportunity": _rate(
                            good, "MISSED_OPPORTUNITY", resolved, masses
                        ),
                        "correct_abstention": _rate(
                            good, "CORRECT_ABSTENTION", resolved, masses
                        ),
                    },
                    "control": {
                        "missed_opportunity": _rate(
                            model, "MISSED_OPPORTUNITY", resolved, masses
                        ),
                        "correct_abstention": _rate(
                            model, "CORRECT_ABSTENTION", resolved, masses
                        ),
                    },
                },
            }
        )
    return {
        "unresolved_mass": sum(
            masses[c] for c in cases if good[c]["reference_resolved"] is not True
        ),
        "controls": controls_out,
    }


def _bank_cross_batch_view(
    cases,
    clusters,
    specs,
    case_exposure,
    window_sampling,
    *,
    alpha,
    target,
    seed,
    replicates,
    max_questions,
    accumulation,
):
    """Conditional finite-bank curves, separate from population P and draw Q."""
    controls_out = []
    for index, spec in enumerate(specs):
        good = {case: result[0] for case, result in cases.items()}
        model = {case: result[1][index] for case, result in cases.items()}
        curves = {}
        for metric in METRICS:
            differences = {}
            for case in cases:
                good_loss = _loss(good[case], metric)
                model_loss = _loss(model[case], metric)
                differences[case] = (
                    model_loss - good_loss
                    if model_loss is not None and good_loss is not None
                    else None
                )
            curves[metric] = power_accumulation.cross_batch_curve(
                case_exposure,
                window_sampling,
                differences,
                clusters,
                alpha=alpha,
                target=target,
                seed=seed,
                replicates=replicates,
                max_questions=max_questions,
                accumulation=accumulation,
            )
        controls_out.append(
            {
                "control_index": index,
                "kind": spec["kind"],
                "scope": spec.get("scope"),
                "severity": spec["severity"],
                "metrics": curves,
            }
        )
    return {
        "basis": "conditional_on_sealed_bank",
        "window_model": power_accumulation.WINDOW_MODEL,
        "controls": controls_out,
    }


def power_report(
    bank,
    grid_law,
    continuous_law,
    registration,
    good_predictor,
    *,
    alpha,
    power_target,
    simulation_seed,
    replicates,
    max_questions,
    accumulation=None,
):
    """Run frozen optimizers and estimate per-metric clustered separation."""
    if type(bank) is dict and "indexed_power_cases" in bank:
        from carbon.design_search.indexed_power import indexed_power_report

        return indexed_power_report(
            bank,
            grid_law,
            continuous_law,
            registration,
            good_predictor,
            alpha=alpha,
            power_target=power_target,
            simulation_seed=simulation_seed,
            replicates=replicates,
            max_questions=max_questions,
            accumulation=accumulation,
        )
    if (
        type(alpha) not in (int, float)
        or not math.isfinite(alpha)
        or not 0 < alpha < 1
        or type(power_target) not in (int, float)
        or not math.isfinite(power_target)
        or not 0 < power_target < 1
        or type(simulation_seed) is not int
        or simulation_seed < 0
        or type(replicates) is not int
        or replicates <= 0
        or type(max_questions) is not int
        or max_questions <= 0
    ):
        raise tasks.TaskError(
            "explicit alpha, power target and simulation budget required"
        )
    if accumulation is not None:
        power_accumulation.validate_accumulation(accumulation)
        if (
            type(bank) is not dict
            or bank.get("exposure_unit") != accumulation["exposure_unit"]
        ):
            raise tasks.TaskError("sealed bank exposure unit differs from accumulation")
    laws = {
        kind: law
        for kind, law in (("grid", grid_law), ("continuous", continuous_law))
        if law is not None
    }
    diversity_views, power_rows, regret_unit = _validate_inputs(
        bank, laws, registration, good_predictor
    )
    outcomes = {}
    clusters = {}
    for case, (task, reference, good, cluster, settled) in power_rows.items():
        outcomes[case] = _run_case(
            task, reference, good, registration["controls"], settled
        )
        clusters[case] = cluster
    report_laws = {}
    for kind, law in laws.items():
        exposure = diversity_views[kind]["exposure_remaining"]
        maximum = (
            (
                min(max_questions, diversity_views[kind]["available_questions"])
                if diversity_views[kind]["batch_drawable"]
                else 0
            )
            if diversity_views[kind]["exposure_unit"]
            == power_accumulation.EXPOSURE_UNIT
            else (
                min(max_questions, exposure)
                if diversity_views[kind]["exposure_unit"] == "question_draws"
                else (max_questions if exposure else 0)
            )
        )
        report_laws[kind] = {
            "registered_batch_size": law["batch_size"],
            "exposure_remaining": exposure,
            "batch_drawable": diversity_views[kind]["batch_drawable"],
            "mass_l1_error_bound": diversity_views[kind]["basis"][
                "mass_l1_error_bound"
            ],
            "max_draw_probability_error_bound": min(
                1.0,
                maximum * diversity_views[kind]["basis"]["mass_l1_error_bound"],
            ),
            "P": (
                _view(
                    law,
                    "p_mass",
                    outcomes,
                    clusters,
                    registration["controls"],
                    alpha=alpha,
                    target=power_target,
                    seed=simulation_seed,
                    replicates=replicates,
                    maximum=maximum,
                )
                if diversity_views[kind]["P"] is not None
                else None
            ),
            "Q": _view(
                law,
                "q_mass",
                outcomes,
                clusters,
                registration["controls"],
                alpha=alpha,
                target=power_target,
                seed=simulation_seed,
                replicates=replicates,
                maximum=maximum,
            ),
        }
    bank_curve = (
        _bank_cross_batch_view(
            outcomes,
            clusters,
            registration["controls"],
            bank["case_exposure"],
            bank["window_sampling"],
            alpha=alpha,
            target=power_target,
            seed=simulation_seed,
            replicates=replicates,
            max_questions=max_questions,
            accumulation=accumulation,
        )
        if accumulation is not None
        else None
    )
    return {
        "schema": REPORT_SCHEMA,
        "material": "DEVELOPMENT",
        "method": "one_sided_exact_sign_test_by_shared_bank.v1",
        "alpha": alpha,
        "power_target": power_target,
        "replicates": replicates,
        "max_questions_requested": max_questions,
        "regret_unit": regret_unit,
        "laws": report_laws,
        **({"sealed_bank_cross_batch": bank_curve} if bank_curve is not None else {}),
        **(
            {
                "accumulation": {
                    "schema": power_accumulation.SCHEMA,
                    "exposure_unit": accumulation["exposure_unit"],
                    "max_windows_requested": accumulation["max_windows"],
                }
            }
            if accumulation is not None
            else {}
        ),
        "claims": {"score_use_approved": False, "power_qualified": False},
    }
