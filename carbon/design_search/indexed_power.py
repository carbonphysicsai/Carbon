"""Producer-only clustered power diagnostics for indexed design decisions."""

from __future__ import annotations

import math

from carbon.design_search import (
    controls,
    diversity,
    indexed,
    power,
    power_accumulation,
    reference_resolution,
    tasks,
)

REPORT_SCHEMA = "carbon.design-search.indexed-power-report.v1"


def _panels(rows, registered):
    if type(rows) is not list or len(rows) != len(registered["indices"]):
        raise tasks.TaskError("complete indexed predictor panels required")
    out = []
    for row, index_row in zip(rows, registered["indices"]):
        if (
            type(row) is not dict
            or set(row) != {"index_value", "panel"}
            or row["index_value"] != index_row["index_value"]
        ):
            raise tasks.TaskError("indexed predictor panel order changed")
        out.append(power._panel(row["panel"], index_row["task"]))
    return out


def _state_and_winner(registered, panels, settled=None):
    if settled is not None:
        return reference_resolution.indexed_state_and_winner(
            registered, panels, settled
        )
    states = []
    winners = []
    resolved = True
    for row, panel in zip(registered["indices"], panels):
        subtask = row["task"]
        truth = tasks.assess(subtask, panel, reference=True)
        resolved &= all(value["feasible"] is not None for value in truth.values())
        states.append(tasks.reference_state(subtask, truth))
        winners.append(tasks.select(subtask, truth))
    if not resolved:
        return "UNRESOLVED", None
    if any(state == "NONE_FEASIBLE" for state in states):
        return "NONE_FEASIBLE", None
    return "FEASIBLE_EXISTS", tasks.digest(winners)


def _validate(bank, laws, registration, good):
    power._registered_good(good)
    controls.validate_controls(registration, task=None)
    if "refinement_rule" in bank:
        reference_resolution.validate_rule(bank["refinement_rule"])
    if (
        type(bank) is not dict
        or type(bank.get("indexed_power_cases")) is not list
        or not bank["indexed_power_cases"]
        or type(laws) is not dict
        or not laws
        or not set(laws) <= {"grid", "continuous"}
        or any(type(laws[kind]) is not dict for kind in laws)
        or any(laws[kind].get("kind") != kind for kind in laws)
        or len({laws[kind].get("batch_size") for kind in laws}) != 1
    ):
        raise tasks.TaskError("registered indexed power bank and laws required")
    diversity_views = {
        kind: diversity.diversity_report(bank, law) for kind, law in laws.items()
    }
    cases = {row["case"]: row for row in bank["cases"]}
    if len(cases) != len(bank["cases"]):
        raise tasks.TaskError("duplicate indexed power question")
    good_rows = {}
    for row in good["cases"]:
        if (
            type(row) is not dict
            or set(row) != {"case", "predictions"}
            or row["case"] in good_rows
        ):
            raise tasks.TaskError("invalid indexed reference predictor")
        good_rows[row["case"]] = row["predictions"]
    if set(good_rows) != set(cases):
        raise tasks.TaskError("indexed reference predictor cases differ")
    support = (
        {row["support_case"] for row in bank["indexed_power_cases"]}
        if bank.get("exposure_unit") == power_accumulation.EXPOSURE_UNIT
        else {row["support_case"] for row in bank["exposure"]}
    )
    rows = {}
    bank_identity = {}
    comparison_identity = None
    for entry in bank["indexed_power_cases"]:
        if (
            type(entry) is not dict
            or set(entry)
            != (
                {"case", "support_case", "task", "reference"}
                | ({"settled"} if "refinement_rule" in bank else set())
            )
            or entry["case"] not in cases
            or entry["case"] in rows
            or entry["support_case"] not in support
        ):
            raise tasks.TaskError("invalid indexed power case")
        registered = entry["task"]
        indexed.validate_indexed(registered)
        reference = _panels(entry["reference"], registered)
        known_good = _panels(good_rows[entry["case"]], registered)
        if known_good != reference:
            raise tasks.TaskError("indexed good predictor differs from reference")
        state, winner = _state_and_winner(
            registered, reference, settled=entry.get("settled")
        )
        if (
            cases[entry["case"]]["state"] != state
            or cases[entry["case"]]["winner"] != winner
        ):
            raise tasks.TaskError("indexed case summary differs from reference")
        for subtask in (row["task"] for row in registered["indices"]):
            controls.validate_controls(registration, task=subtask)
        signature = (
            registered["identity"]["objective"],
            registered["identity"]["value_equivalence"],
            registered["identity"]["index_axis"],
            [row["index_value"] for row in registered["indices"]],
        )
        if comparison_identity is None:
            comparison_identity = signature
        elif signature != comparison_identity:
            raise tasks.TaskError(
                "indexed power questions need one objective, tolerance and index axis"
            )
        material = tasks.digest(
            {
                "banks": [row["task"]["bank_digest"] for row in registered["indices"]],
                "reference": entry["reference"],
            }
        )
        prior = bank_identity.setdefault(entry["support_case"], material)
        if prior != material:
            raise tasks.TaskError(
                "shared indexed bank has different reference material"
            )
        rows[entry["case"]] = (
            registered,
            reference,
            known_good,
            entry["support_case"],
            entry.get("settled"),
        )
    if set(rows) != set(cases) or support != {row[3] for row in rows.values()}:
        raise tasks.TaskError("indexed power bank does not cover exposure ledger")
    return diversity_views, rows, comparison_identity


def _run_case(registered, reference, known_good, specs, settled=None):
    action_index = [
        {
            tasks.digest(action): candidate
            for candidate, action in row["task"]["actions"].items()
        }
        for row in registered["indices"]
    ]
    values = [row["index_value"] for row in registered["indices"]]
    positions = {tasks.digest(value): i for i, value in enumerate(values)}
    queried = [set() for _ in values]

    def good(index_value, action, condition):
        position = positions[tasks.digest(index_value)]
        key = tasks.digest(action)
        queried[position].add(key)
        return dict(
            known_good[position][(action_index[position][key], condition["id"])]
        )

    good_run = tasks.run_indexed_optimizer(registered, good, model_id="REFERENCE")
    panels = [
        {"index_value": value, "values": panel}
        for value, panel in zip(values, reference)
    ]
    judge = (
        (
            lambda commitment: reference_resolution.judge_indexed(
                registered, commitment, panels, settled
            )
        )
        if settled is not None
        else (lambda commitment: tasks.judge_indexed(registered, commitment, panels))
    )
    good_outcome = judge(good_run["commitment"])
    control_outcomes = []
    for control_index, spec in enumerate(specs):

        def predict(index_value, action, condition, spec=spec):
            position = positions[tasks.digest(index_value)]
            key = tasks.digest(action)
            row = known_good[position][(action_index[position][key], condition["id"])]
            return controls.task_control_prediction(
                registered["indices"][position]["task"],
                spec,
                action,
                condition,
                row,
                accurate_actions=queried[position],
            )

        run = tasks.run_indexed_optimizer(
            registered, predict, model_id=f"CONTROL-{control_index}"
        )
        control_outcomes.append(judge(run["commitment"]))
    return good_outcome, control_outcomes


def indexed_power_report(
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
    """Report map and per-index separation with shared-bank clustering."""
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
        raise tasks.TaskError("explicit indexed power parameters required")
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
    diversity_views, rows, comparison = _validate(
        bank, laws, registration, good_predictor
    )
    outcomes = {}
    clusters = {}
    for case, (registered, reference, known_good, cluster, settled) in rows.items():
        outcomes[case] = _run_case(
            registered, reference, known_good, registration["controls"], settled
        )
        clusters[case] = cluster
    index_count = len(comparison[3])
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

        def view(data, law=law, maximum=maximum, exposure=exposure, kind=kind):
            return {
                label: (
                    power._view(
                        law,
                        measure,
                        data,
                        clusters,
                        registration["controls"],
                        alpha=alpha,
                        target=power_target,
                        seed=simulation_seed,
                        replicates=replicates,
                        maximum=maximum,
                    )
                    if label != "P" or diversity_views[kind]["P"] is not None
                    else None
                )
                for label, measure in (("P", "p_mass"), ("Q", "q_mass"))
            }

        per_index = []
        for position in range(index_count):
            sub_outcomes = {
                case: (
                    result[0]["per_index"][position]["outcome"],
                    [
                        control["per_index"][position]["outcome"]
                        for control in result[1]
                    ],
                )
                for case, result in outcomes.items()
            }
            per_index.append({"index_position": position, "views": view(sub_outcomes)})
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
            "aggregate": view(outcomes),
            "per_index": per_index,
        }
    bank_curve = None
    if accumulation is not None:
        per_index_curve = []
        for position in range(index_count):
            sub_outcomes = {
                case: (
                    result[0]["per_index"][position]["outcome"],
                    [
                        control["per_index"][position]["outcome"]
                        for control in result[1]
                    ],
                )
                for case, result in outcomes.items()
            }
            per_index_curve.append(
                {
                    "index_position": position,
                    "view": power._bank_cross_batch_view(
                        sub_outcomes,
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
                    ),
                }
            )
        bank_curve = {
            "aggregate": power._bank_cross_batch_view(
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
            ),
            "per_index": per_index_curve,
        }
    return {
        "schema": REPORT_SCHEMA,
        "material": "DEVELOPMENT",
        "method": "one_sided_exact_sign_test_by_shared_bank.v1",
        "alpha": alpha,
        "power_target": power_target,
        "replicates": replicates,
        "max_questions_requested": max_questions,
        "index_count": index_count,
        "regret_unit": comparison[0]["unit"],
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
