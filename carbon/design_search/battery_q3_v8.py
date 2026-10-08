"""Read-only producer reports for the sealed battery Q3 v8 decision job.

The two report views deliberately have different estimands. The exact view
describes the sealed eight; the empirical view resamples all settled draws.
Neither estimates an unsolved continuous response surface or qualifies power.
"""

from __future__ import annotations

import json
import math
import os
import random
import stat
from pathlib import Path

from carbon.battery import domain
from carbon.battery import quiz_stratum as qs
from carbon.battery.value import contract as ev
from carbon.battery.value import decision as bd
from carbon.battery.value import quiz as bq
from carbon.challenge_validator import tuning
from carbon.design_search import controls, power, tasks

JOB = "battery-q3-v8"
LAW_SCHEMA = "carbon.battery.q3-v8.question-law.v1"
REPORT_SCHEMA = "carbon.battery.q3-v8.design-report.v1"
_STATE = ("FEASIBLE_EXISTS", "NONE_FEASIBLE", "UNRESOLVED")
_METRICS = ("false_feasible", "regret", "abstention")


def _refuse():
    raise tasks.TaskError("sealed battery Q3 v8 producer material is inconsistent")


def load_law(path):
    law = json.loads(Path(path).read_text(encoding="utf-8"))
    body = {
        "schema": LAW_SCHEMA,
        "job": JOB,
        "draw": {
            "rule": "independent_uniform_then_numpy_round_4",
            "t_amb_c": list(domain.INPUT_BOUNDS["t_amb_c"]),
            "soc0": list(domain.INPUT_BOUNDS["soc0"]),
            "protected_exclusion": {
                "rule": "both_axes_strict_less_than",
                "t_amb_c": qs.PROTECTED_T_C,
                "soc0": qs.PROTECTED_SOC,
            },
            "first_round": qs.q3_draws(1),
            "additional_per_round": qs.Q3_EXTRA,
        },
        "selection": {
            "rule": "first_settled_reference_feasible_in_draw_order",
            "requires_v8_refinement": True,
        },
        "batch_size": bq.Q3_K,
    }
    if type(law) is not dict or law != {
        **body,
        "registration_digest": tasks.digest(body),
    }:
        raise tasks.TaskError("registered battery Q3 v8 law required")
    return law


def _read_journal(path, document):
    entries = qs.seeds.SeedJournal(path).public()  # read-only; never loads the root
    matching = [
        entry
        for entry in entries
        if entry.get("kind") == "quiz" and entry.get("role") == document["role"]
    ]
    if (
        len(matching) != 1
        or matching[0].get("digest") != qs.digest(document)
        or matching[0].get("q3_scenarios") != bq.Q3_K
        or matching[0].get("q2_cases") != len(document["q2"])
        or matching[0].get("panel_version") != document["panel_version"]
    ):
        _refuse()
    return matching[0]["digest"]


def _neutral_task(entry, seal, contract):
    candidates = bq.q3_candidates()
    ids = [candidate["id"] for candidate in candidates]
    grammar = {
        "schema": tasks.GRAMMAR_SCHEMA,
        "version": "battery-q3-v8-lattice.v1",
        "variables": [
            {"name": "c1", "type": "number", "min": 0.5, "max": 2.0, "step": 0.125},
            {"name": "c2", "type": "number", "min": 0.2, "max": 1.0, "step": 0.1},
        ],
        "rules": [],
    }
    bands = contract["reference"]["uncertainty"]["bands"]
    thermal = next(
        c["threshold"] for c in contract["constraints"] if c["id"] == "peak_temperature"
    )
    return tasks.task(
        entry["scenario_id"],
        identity={
            "challenge": JOB,
            "contract_version": contract["version"],
            "action_grammar": grammar,
            "optimizer": {"class": "exhaustive", "version": "v1"},
            "query_budget": len(ids),
            "seed": 0,  # Exhaustive has no randomized path.
            "observer_version": "ev4-measure-q3-v8-projection.v1",
            "reference_bank": seal,
        },
        conditions=[{"id": "one-condition", "stratum": "v8-scenario"}],
        strata={"v8-scenario": {"p": 1.0, "q": 1.0, "w": 1.0}},
        candidates=ids,
        actions={c["id"]: {"c1": c["c1"], "c2": c["c2"]} for c in candidates},
        objective={
            "quantity": "time_to_cv_onset_s",
            "unit": "s",
            "sense": "min",
            "aggregate": "worst",
        },
        limits=[
            {
                "quantity": "reach_class",
                "unit": "verdict",
                "op": ">=",
                "value": 0,
                "band": 0.5,
            },
            {
                "quantity": "plating_margin_v",
                "unit": "V",
                "op": ">=",
                "value": 0,
                "band": bands["plating_margin_v"],
            },
            {
                "quantity": "peak_temperature_c",
                "unit": "degC",
                "op": "<=",
                "value": thermal,
                "band": bands["peak_temperature_c"],
            },
        ],
    )


def _projection(contract, record):
    if record.get("status") != "OK" or not record.get("outputs"):
        return None
    measured = bd.measure(contract, record["outputs"])
    time = measured["time_to_cv_onset_s"]
    window = contract["objective"]["window_s"] - contract["objective"]["charge_start_s"]
    band = contract["reference"]["uncertainty"]["bands"]["time_to_cv_onset_s"]
    return {
        # Internal optimizer representation only. Undefined time remains
        # unreachable; this surrogate is never emitted as a physical value.
        "time_to_cv_onset_s": window + 1 if time is None else time,
        "reach_class": -1 if time is None else (0 if time > window - band else 1),
        "plating_margin_v": measured["plating_margin_v"],
        "peak_temperature_c": measured["peak_temperature_c"],
    }


def _case(entry, settled, points, refined, contract, seal):
    scenario = qs.scenario(entry)
    candidates = bq.q3_candidates()
    grid = bq.q3_grid(contract, scenario)
    refs = {job["case_id"]: settled[job["case_id"]] for job in grid}
    native = bd.assess_reference(
        contract,
        scenario,
        candidates,
        {
            (candidate["id"], 0): refs[grid[index]["case_id"]]
            for index, candidate in enumerate(candidates)
        },
    )
    winner = bd.best_in_set(candidates, native)
    state = (
        "FEASIBLE_EXISTS"
        if winner is not None
        else (
            "NONE_FEASIBLE"
            if all(row["status"] == bd.INFEASIBLE for row in native.values())
            else "UNRESOLVED"
        )
    )
    summary = qs.refine_summary(
        contract, entry, points[entry["scenario_id"]], refined, settled
    )
    task = _neutral_task(entry, seal, contract)
    projections = {
        candidate["id"]: _projection(contract, refs[grid[index]["case_id"]])
        for index, candidate in enumerate(candidates)
    }
    neutral = {
        (name, "one-condition"): row
        for name, row in projections.items()
        if row is not None
    }
    assessed = tasks.assess(task, neutral, reference=True)
    expected = {
        bd.FEASIBLE: True,
        bd.INFEASIBLE: False,
        bd.UNRESOLVED: None,
        bd.UNAVAILABLE: None,
    }
    if any(
        assessed[name]["feasible"] is not expected[row["status"]]
        for name, row in native.items()
    ):
        _refuse()
    return {
        "task": task,
        "native": native,
        "projections": projections,
        "state": state,
        "winner": winner,
        "close_call": summary["residual"] > 0,
        "refinement_demand": summary["refine_points"] > 0,
        "contract": contract,
    }


def load_bank(work, journal, law_path, *, repository=None):
    """Load and verify Q3 only, without writing or reading the private root."""
    load_law(law_path)
    root = (
        Path(repository)
        if repository is not None
        else Path(__file__).resolve().parents[2]
    )
    work = tuning._outside_repository(work)
    info = os.lstat(work)
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        _refuse()
    document = qs.check(tuning._read_private(work / "quiz.json"))
    draws = tuning._read_private(work / "draws.json")
    if (
        draws.get("schema") != tuning.QUIZ_DRAWS_SCHEMA
        or draws.get("role") != document["role"]
        or type(draws.get("round")) is not int
        or draws["round"] < 1
        or type(draws.get("q3")) is not list
        or len(draws["q3"]) != qs.q3_draws(draws["round"])
        or type(draws.get("q2")) is not list
    ):
        _refuse()
    seal = _read_journal(journal, document)
    contract = qs.contract(root)
    standard, points, refined, settled = tuning._settled(work, contract, draws["q3"])
    expected, redraws = qs.q3_select(contract, draws["q3"], settled)
    if (
        len(expected) != bq.Q3_K
        or document["redraws"] != redraws
        or document["q3"]
        != qs.with_refine(contract, expected, points, refined, settled)
        or not {row["case_id"] for row in document["q2"]}
        <= {row["case_id"] for row in draws["q2"]}
    ):
        _refuse()
    cases = []
    kept = {entry["scenario_id"] for entry in expected}
    seen = set()
    for entry in draws["q3"]:
        if (
            type(entry) is not dict
            or set(entry) != {"scenario_id", "condition", "attempt"}
            or entry["scenario_id"] in seen
            or type(entry["attempt"]) is not int
            or entry["attempt"] < 0
            or type(entry["condition"]) is not list
            or len(entry["condition"]) != 2
        ):
            _refuse()
        seen.add(entry["scenario_id"])
        grid = bq.q3_grid(contract, qs.scenario(entry))
        for job in grid:
            record = standard.get(job["case_id"])
            if record is None or record.get("inputs") not in (
                None,
                {k: job[k] for k in ("c1", "c2", "t_amb_c", "soc0")},
            ):
                _refuse()
        case = _case(entry, settled, points, refined, contract, seal)
        case["kept"] = entry["scenario_id"] in kept
        cases.append(case)
    return {
        "job": JOB,
        "seal": seal,
        "cases": cases,
        "round": draws["round"],
        "protected_redraws": redraws["q3_protected"],
    }


def _mix(cases):
    n = len(cases)
    return {
        state: sum(case["state"] == state for case in cases) / n if n else None
        for state in _STATE
    }


def _diversity(cases):
    n = len(cases)
    return {
        "count": n,
        "distinct_winners": len(
            {case["winner"] for case in cases if case["winner"] is not None}
        ),
        "status_mix": _mix(cases),
        "close_call_rate": sum(case["close_call"] for case in cases) / n if n else None,
        "refinement_demand_rate": (
            sum(case["refinement_demand"] for case in cases) / n if n else None
        ),
    }


def _percentile(values, p):
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    low = math.floor(index)
    high = math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def _interval(values, level):
    if not values:
        return None
    tail = (1 - level) / 2
    return {
        "mean": sum(values) / len(values),
        "predictive_interval": [
            _percentile(values, tail),
            _percentile(values, 1 - tail),
        ],
    }


def _round_sample(cases, rng):
    # Outer resample represents uncertainty from the small settled support.
    # Inner draws represent a fresh v8 batch. v8 adds four draws per round
    # until eight feasible scenarios have been selected.
    support = [cases[rng.randrange(len(cases))] for _ in cases]
    if not any(case["state"] == "FEASIBLE_EXISTS" for case in support):
        return [], [], 0
    kept = []
    not_kept = []
    rounds = 0
    while len(kept) < bq.Q3_K and rounds < 100:
        width = qs.q3_draws(1) if rounds == 0 else qs.Q3_EXTRA
        for _ in range(width):
            case = support[rng.randrange(len(support))]
            if case["state"] == "FEASIBLE_EXISTS" and len(kept) < bq.Q3_K:
                kept.append(case)
            else:
                not_kept.append(case)
        rounds += 1
    return kept, not_kept, rounds


def _empirical(cases, *, seed, replicates, interval_level, statistic):
    rng = random.Random(seed)
    samples = [_round_sample(cases, rng) for _ in range(replicates)]
    complete = [sample for sample in samples if len(sample[0]) == bq.Q3_K]
    if not complete:
        return {
            "completion_rate": 0.0,
            "first_round_completion_rate": 0.0,
            "conditional_on_completed_batch": None,
        }
    values = [statistic(kept, other) for kept, other, _rounds in complete]
    return {
        "completion_rate": len(complete) / replicates,
        "first_round_completion_rate": sum(
            rounds == 1 for _kept, _other, rounds in samples
        )
        / replicates,
        "mean_rounds_to_fill": sum(rounds for _kept, _other, rounds in complete)
        / len(complete),
        "conditional_on_completed_batch": values,
    }


def diversity_report(bank, *, seed, replicates, interval_level):
    _parameters(seed, replicates, interval_level)
    cases = bank["cases"]
    kept = [case for case in cases if case["kept"]]
    other = [case for case in cases if not case["kept"]]
    empirical = _empirical(
        cases,
        seed=seed,
        replicates=replicates,
        interval_level=interval_level,
        statistic=lambda k, o: (_diversity(k), _diversity(o)),
    )
    future = None
    if empirical["conditional_on_completed_batch"] is not None:
        pairs = empirical["conditional_on_completed_batch"]
        future = {
            group: {
                "expected_distinct_winners": _interval(
                    [pair[index]["distinct_winners"] for pair in pairs], interval_level
                ),
                "status_mix": {
                    state: _interval(
                        [
                            pair[index]["status_mix"][state]
                            for pair in pairs
                            if pair[index]["count"]
                        ],
                        interval_level,
                    )
                    for state in _STATE
                },
                "close_call_rate": _interval(
                    [
                        pair[index]["close_call_rate"]
                        for pair in pairs
                        if pair[index]["count"]
                    ],
                    interval_level,
                ),
                "refinement_demand_rate": _interval(
                    [
                        pair[index]["refinement_demand_rate"]
                        for pair in pairs
                        if pair[index]["count"]
                    ],
                    interval_level,
                ),
            }
            for group, index in (("kept", 0), ("not_kept", 1))
        }
    return {
        **_header(bank, "diversity"),
        "exact_sealed_batch": {
            "label": "conditional on sealed batch; not a future-batch probability",
            "kept": _diversity(kept),
        },
        "observed_draw_pool": {
            "draws": len(cases),
            "kept": _diversity(kept),
            "not_kept": _diversity(other),
        },
        "empirical_future_batch": {
            "label": "bootstrap over settled unprotected draws, applying v8 four-draw extension rounds",
            "replicates": replicates,
            "interval_level": interval_level,
            "simulation_round_cap": 100,
            "completion_rate": empirical["completion_rate"],
            "first_round_completion_rate": empirical["first_round_completion_rate"],
            "mean_rounds_to_fill": empirical.get("mean_rounds_to_fill"),
            "conditional_on_completed_batch": future,
        },
    }


def _parameters(seed, replicates, interval_level):
    if (
        type(seed) is not int
        or seed < 0
        or type(replicates) is not int
        or replicates <= 0
        or type(interval_level) not in (int, float)
        or not 0 < interval_level < 1
    ):
        raise tasks.TaskError(
            "explicit positive bootstrap budget, seed and interval level required"
        )


def _header(bank, kind):
    return {
        "schema": REPORT_SCHEMA,
        "report": kind,
        "material": "DEVELOPMENT",
        "job_identity": JOB,
        "sealed_batch_digest": bank["seal"],
        "draw_process": "v8 Q3 accepted ambient/SOC draws; protected draws excluded",
        "scenario_stratum": "one accepted unprotected ambient/SOC condition per decision",
        "measure_definitions": {
            "close_call_rate": "share of scenarios with a residual unresolved lattice point after v8 refinement",
            "refinement_demand_rate": "share of scenarios with at least one v8 near-band refined-solve job",
        },
        "warning": "small settled draw sample; intervals may be wide and are not scientific qualification",
        "exposure_remaining": None,
        "exposure_note": "v8 quiz work has no design-bank exposure ledger; owner must track retirement separately",
        "claims": {
            "score_use_approved": False,
            "power_qualified": False,
            "ev_buyer_job_measured": False,
        },
    }


def _control_set(severities):
    specs = [
        {
            "schema": controls.CONTROL_SCHEMA,
            "name": "edge",
            "kind": "edge_optimist",
            "severity": severities["edge"],
            "limit_quantities": ["plating_margin_v", "peak_temperature_c"],
        },
        {
            "schema": controls.CONTROL_SCHEMA,
            "name": "caution",
            "kind": "over_cautious",
            "severity": severities["caution"],
            "limit_quantities": ["plating_margin_v", "peak_temperature_c"],
        },
        {
            "schema": controls.CONTROL_SCHEMA,
            "name": "sign",
            "kind": "localized_sign_error",
            "severity": severities["sign"],
            "limit_quantities": ["plating_margin_v"],
            "region": {"action": {"c1": {"min": 1.5, "max": 2.0}}, "strata": []},
        },
        {
            "schema": controls.CONTROL_SCHEMA,
            "name": "path",
            "kind": "optimizer_or_lattice_aware",
            "severity": severities["path"],
            "limit_quantities": ["plating_margin_v", "peak_temperature_c"],
            "scope": "registered_search_path",
        },
    ]
    return controls.register_controls(specs)["controls"]


def _native_outcome(case, selected):
    contract = case["contract"]
    baseline = ev.candidate_id(contract["baseline"]["protocol"])
    return bd.outcome(contract, bq.q3_candidates(), selected, case["native"], baseline)


def _run_case(case, specs):
    task = case["task"]
    by_action = {tasks.digest(action): name for name, action in task["actions"].items()}
    queried = set()

    def good(action, _condition):
        queried.add(tasks.digest(action))
        row = case["projections"][by_action[tasks.digest(action)]]
        if row is None:
            raise ValueError("unavailable reference")
        return dict(row)

    good_run = tasks.run_optimizer(task, good, model_id="REFERENCE")
    out = {
        "good": _native_outcome(case, good_run["commitment"]["selected"]),
        "controls": [],
    }
    for index, spec in enumerate(specs):

        def predict(action, condition, spec=spec):
            row = case["projections"][by_action[tasks.digest(action)]]
            if row is None:
                raise ValueError("unavailable reference")
            return controls.task_control_prediction(
                task, spec, action, condition, row, accurate_actions=queried
            )

        run = tasks.run_optimizer(task, predict, model_id=f"CONTROL-{index}")
        out["controls"].append(_native_outcome(case, run["commitment"]["selected"]))
    return out


def _loss(outcome, metric, costs):
    kind = outcome["kind"]
    if metric == "false_feasible":
        return float(kind in ("SELECTED_INFEASIBLE", "SELECTED_UNRESOLVED"))
    if metric == "abstention":
        return float(kind in ("MISSED_OPPORTUNITY", "ABSTENTION_UNRESOLVED"))
    value = outcome["decision_loss"]
    if value is not None:
        return value
    return (
        costs["missed_opportunity"]
        if kind == "ABSTENTION_UNRESOLVED"
        else costs["false_acceptance"]
    )


def _power_summary(cases, outcomes, specs):
    indexed = {id(case): result for case, result in outcomes}
    n = len(cases)
    if not n:
        return None
    result = []
    for index, spec in enumerate(specs):
        metrics = {}
        for metric in _METRICS:
            good = [
                _loss(indexed[id(c)]["good"], metric, c["contract"]["mistake_costs"])
                for c in cases
            ]
            model = [
                _loss(
                    indexed[id(c)]["controls"][index],
                    metric,
                    c["contract"]["mistake_costs"],
                )
                for c in cases
            ]
            metrics[metric] = {
                "good": sum(good) / n,
                "control": sum(model) / n,
                "separation": (sum(model) - sum(good)) / n,
            }
        result.append({"kind": spec["kind"], "metrics": metrics})
    return result


def _detected(cases, case_outcomes, index, metric, alpha):
    grouped = {}
    for case in cases:
        row = case_outcomes[id(case)]
        costs = case["contract"]["mistake_costs"]
        difference = _loss(row["controls"][index], metric, costs) - _loss(
            row["good"], metric, costs
        )
        group = id(case)  # repeated draws of one solved bank retain one cluster
        grouped[group] = grouped.get(group, 0.0) + difference
    p, nonzero = power._sign_test_p(grouped)
    return p <= alpha, nonzero, p


def power_report(
    bank, *, seed, replicates, interval_level, alpha, power_target, severities
):
    _parameters(seed, replicates, interval_level)
    if (
        type(alpha) not in (int, float)
        or not 0 < alpha < 1
        or type(power_target) not in (int, float)
        or not 0 < power_target < 1
    ):
        raise tasks.TaskError("explicit alpha and power target required")
    if set(severities) != {"edge", "caution", "sign", "path"}:
        raise tasks.TaskError("all control severities required")
    specs = _control_set(severities)
    cases = bank["cases"]
    outcomes = [(case, _run_case(case, specs)) for case in cases]
    by_id = {id(case): row for case, row in outcomes}
    kept = [case for case in cases if case["kept"]]
    other = [case for case in cases if not case["kept"]]
    rng = random.Random(seed)
    simulated = [_round_sample(cases, rng) for _ in range(replicates)]
    complete = [sample for sample in simulated if len(sample[0]) == bq.Q3_K]
    exact = _power_summary(kept, outcomes, specs)
    future = []
    for index, spec in enumerate(specs):
        metrics = {}
        for metric in _METRICS:
            curve = []
            for k in range(1, bq.Q3_K + 1):
                detected = [
                    _detected(batch[:k], by_id, index, metric, alpha)[0]
                    for batch, _other, _rounds in complete
                ]
                curve.append(sum(detected) / len(detected) if detected else None)
            first = next(
                (
                    k
                    for k, value in enumerate(curve, 1)
                    if value is not None
                    and all(
                        later is not None and later >= power_target
                        for later in curve[k - 1 :]
                    )
                ),
                None,
            )
            metric_values = [
                _power_summary(batch, outcomes, specs)[index]["metrics"][metric][
                    "separation"
                ]
                for batch, _other, _rounds in complete
            ]
            metrics[metric] = {
                "separation": _interval(metric_values, interval_level),
                "estimated_detection_probability_by_questions": curve,
                "first_questions_meeting_target_estimate": first,
            }
        future.append(
            {"kind": spec["kind"], "severity": spec["severity"], "metrics": metrics}
        )
    return {
        **_header(bank, "power"),
        "method": "v8-pessimistic-outcomes; one-sided-exact-sign-test-by-shared-bank.v1",
        "metric_units": {
            "false_feasible": "fraction of v8 Q3 decisions",
            "regret": "EV4 decision-loss units, including v8 pessimistic unresolved pricing",
            "abstention": "fraction of v8 Q3 decisions",
        },
        "alpha": alpha,
        "power_target": power_target,
        "exact_sealed_batch": {
            "label": "conditional on sealed batch; not a future-batch probability",
            "kept": exact,
            "unresolved_candidate_scenarios": sum(
                any(
                    row["status"] in (bd.UNRESOLVED, bd.UNAVAILABLE)
                    for row in case["native"].values()
                )
                for case in kept
            ),
            "observed_detection_at_eight": [
                {
                    metric: _detected(kept, by_id, index, metric, alpha)[0]
                    for metric in _METRICS
                }
                for index in range(len(specs))
            ],
        },
        "observed_draw_pool": {
            "draws": len(cases),
            "kept": exact,
            "not_kept": _power_summary(other, outcomes, specs),
        },
        "empirical_future_batch": {
            "label": "bootstrap over settled unprotected draws, applying v8 four-draw extension rounds",
            "replicates": replicates,
            "interval_level": interval_level,
            "simulation_round_cap": 100,
            "completion_rate": len(complete) / replicates,
            "first_round_completion_rate": sum(
                rounds == 1 for _kept, _other, rounds in simulated
            )
            / replicates,
            "mean_rounds_to_fill": (
                sum(rounds for _kept, _other, rounds in complete) / len(complete)
                if complete
                else None
            ),
            "kept": future,
            "not_kept": [
                {
                    "kind": spec["kind"],
                    "metrics": {
                        metric: _interval(
                            [
                                _power_summary(other_batch, outcomes, specs)[index][
                                    "metrics"
                                ][metric]["separation"]
                                for _kept, other_batch, _rounds in complete
                                if other_batch
                            ],
                            interval_level,
                        )
                        for metric in _METRICS
                    },
                }
                for index, spec in enumerate(specs)
            ],
        },
        "limits": "Eight Q3 questions maximum in one batch; a missing target crossing is unresolved, not proof of low power. Lattice/path-aware control is accurate on this exhaustive path and needs off-lattice accuracy evidence.",
    }
