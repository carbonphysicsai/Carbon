"""Development-only toy competitors: no Challenge physics, hidden bank or solver."""

import copy
import json
from pathlib import Path

import pytest

from carbon.design_search import adaptive_arms as adaptive
from carbon.design_search import budget_registration as budgets
from carbon.design_search import equal_budget

REGISTRATION = (
    Path(__file__).resolve().parents[2]
    / "docs/development/challenge_pipeline/equal-budget-registration-v1.json"
)


def _cost(value):
    return {"wall_s": value, "core_s": value}


def _registration():
    raw = json.loads(REGISTRATION.read_text(encoding="utf-8"))
    body = {key: value for key, value in raw.items() if key != "registration_digest"}
    for tier, count, seconds in (("half", 2, 4), ("base", 4, 8), ("double", 8, 16)):
        body["challenge_budgets"]["motor"]["tiers"][tier] = {
            "solver_evaluations": count,
            "wall_s": seconds,
            "core_s": seconds,
        }
    return budgets.seal(body)


def _panel(*, cached=False, f02=False, battery=False):
    challenge = "battery-v3" if battery else "f02" if f02 else "motor"
    registration = _registration()
    n = 9 if f02 else 5
    base_jobs = []
    extra_jobs = []
    for group in range(2):
        candidates = []
        actions = []
        for index in range(n):
            design_id = f"d{index}"
            value = float(n - index)
            first = index == 0
            attempts = (
                [
                    {
                        "kind": "failed_reference",
                        "cost": _cost(0.5),
                        "planning_bound": _cost(0.5),
                    },
                    {"kind": "final", "cost": _cost(1.5), "planning_bound": _cost(1.5)},
                ]
                if first
                else [{"kind": "final", "cost": _cost(1), "planning_bound": _cost(1)}]
            )
            reference = {"status": "FEASIBLE", "value": value}
            if battery:
                reference["per_index"] = {
                    band: {"status": "FEASIBLE", "value": value}
                    for band in ("5", "15", "25", "35", "40")
                }
            margins = {"limit_a": 1.0, "limit_b": 2.0}
            if battery:
                margins = {
                    band: dict(margins) for band in ("5", "15", "25", "35", "40")
                }
            candidates.append(
                {
                    "design_id": design_id,
                    "reference": reference,
                    "solve_cost": _cost(2 if first else 1),
                    "planning_bound": _cost(2 if first else 1),
                    "screen_rank": {"model": n - index - 1, "baseline": index},
                }
            )
            actions.append(
                {
                    "design_id": design_id,
                    "branch": "toy-branch",
                    "coordinates": {"setting": index},
                    "margins": margins,
                    "unresolved_cause": None,
                    "warm_start_from": "d4" if cached and index != 4 else None,
                    "attempts": attempts,
                }
            )
        job_id = f"toy-job-{group}"
        base_jobs.append(
            {
                "job_id": job_id,
                "cluster_id": f"bank-{group}",
                "candidates": candidates,
                "solver_order": [row["design_id"] for row in candidates],
                "screen_cost": {"model": _cost(0.1), "baseline": _cost(0.1)},
            }
        )
        extra_jobs.append(
            {
                "job_id": job_id,
                "axes": [
                    {"name": "setting", "type": "ordinal", "values": list(range(n))}
                ],
                "actions": actions,
                "starts": ["d0"],
                "common_cache": (
                    [
                        {
                            "design_id": "d4",
                            "reference": copy.deepcopy(candidates[4]["reference"]),
                            "margins": copy.deepcopy(actions[4]["margins"]),
                        }
                    ]
                    if cached
                    else []
                ),
                "cache_source": (
                    {
                        "source_digest": "sha256:" + "c" * 64,
                        "rights": "PUBLIC_DEVELOPMENT",
                        "decision_rule_id": "toy-rule",
                        "condition_panel_digest": "sha256:" + "e" * 64,
                    }
                    if cached
                    else None
                ),
                "condition_panel_digest": "sha256:" + "e" * 64,
                "cache_acquisition": _cost(0.1 if cached else 0),
            }
        )
    base = equal_budget.seal(
        {
            "schema": equal_budget.SCHEMA,
            "evidence_class": "DEVELOPMENT",
            "challenge": challenge,
            "source_digest": "sha256:" + "a" * 64,
            "decision_rule_id": "toy-rule",
            "objective": {
                "direction": "min",
                "unit": "toy-units",
                **(
                    {
                        "index_weights": {
                            band: 0.2 for band in ("5", "15", "25", "35", "40")
                        }
                    }
                    if battery
                    else {}
                ),
            },
            "cost_basis": "ASSUMPTION",
            "execution_plan": "SERIAL_COMPLETE_PANELS",
            "budgets": [
                budgets.validate(registration).cap(challenge, tier).time_compute
                for tier in budgets.TIERS
            ],
            "jobs": base_jobs,
            "registrations": {
                "solver_search": "toy-fixed",
                "model_screen": "toy-model",
                "baseline_screen": "toy-baseline",
                "cost_plan": budgets.REGISTRATION_ID,
            },
        }
    )
    policy = adaptive.seal(
        {
            "schema": adaptive.POLICY_SCHEMA,
            "challenge": challenge,
            "calibration_digest": "sha256:" + "b" * 64,
            "pre_experiment_receipt": "sha256:" + "d" * 64,
            "direct": {
                "method": "finite_enumeration" if f02 else "pattern_multistart",
                "restarts": 3,
                "stagnation": 2,
                "startup_cost": _cost(0.1),
                "proposal_cost": _cost(0.01),
                "cache_lookup_cost": _cost(0.01),
            },
            "surrogate": {
                "method": "branch_rbf_or_exact_lookup",
                "initial_designs": 1,
                "length_scale": 1.0,
                "objective_scale": 1.0,
                "margin_scales": {"limit_a": 1.0, "limit_b": 1.0},
                "exploration": 0.1,
                "startup_cost": _cost(0.1),
                "proposal_cost": _cost(0.01),
                "fit_cost_per_observation": _cost(0.01),
                "cache_lookup_cost": _cost(0.01),
            },
            "model": {"cache_lookup_cost": _cost(0.01)},
        },
        "policy_digest",
    )
    return (
        adaptive.seal(
            {
                "schema": adaptive.SCHEMA,
                "base_panel": base,
                "policy": policy,
                "jobs": extra_jobs,
            },
            "adaptive_digest",
        ),
        registration,
    )


def _reseal(panel):
    return adaptive.seal(
        {key: value for key, value in panel.items() if key != "adaptive_digest"},
        "adaptive_digest",
    )


def test_deterministic_adaptation_and_prefix_only_proposals():
    panel, registration = _panel()
    first = adaptive.replay(panel, registration, "base")
    assert first == adaptive.replay(panel, registration, "base")
    trace = first["producer_only_traces"][0]["events"]
    proposals = [entry for entry in trace if entry["event"] == "PROPOSAL"]
    assert len(proposals) >= 2
    changed = copy.deepcopy(panel)
    # Future truth changes must not affect a proposal made before observing it.
    changed["base_panel"]["jobs"][0]["candidates"][1]["reference"]["value"] = 99.0
    changed["base_panel"] = equal_budget.seal(
        {
            key: value
            for key, value in changed["base_panel"].items()
            if key != "panel_digest"
        }
    )
    changed = _reseal(changed)
    revised = adaptive.replay(changed, registration, "base")["producer_only_traces"][0][
        "events"
    ]
    assert (
        proposals[0]["candidate_digest"]
        == next(entry for entry in revised if entry["event"] == "PROPOSAL")[
            "candidate_digest"
        ]
    )
    assert (
        proposals[0]["observed_prefix_digest"]
        == next(entry for entry in revised if entry["event"] == "PROPOSAL")[
            "observed_prefix_digest"
        ]
    )
    # Changing the first *observed* verdict changes the later direct path.
    changed = copy.deepcopy(panel)
    changed["base_panel"]["jobs"][0]["candidates"][0]["reference"] = {
        "status": "INFEASIBLE",
        "value": None,
    }
    changed["jobs"][0]["actions"][0]["margins"]["limit_a"] = -1
    changed["base_panel"] = equal_budget.seal(
        {
            key: value
            for key, value in changed["base_panel"].items()
            if key != "panel_digest"
        }
    )
    changed = _reseal(changed)
    alternate = adaptive.replay(changed, registration, "base")["producer_only_traces"][
        0
    ]["events"]
    assert (
        proposals[1]["candidate_digest"]
        != [entry for entry in alternate if entry["event"] == "PROPOSAL"][1][
            "candidate_digest"
        ]
    )


def test_direct_restart_challenger_uses_remaining_budget():
    panel, registration = _panel()
    changed = copy.deepcopy(panel)
    for job in changed["base_panel"]["jobs"]:
        for candidate in job["candidates"]:
            candidate["reference"]["value"] = 5.0
    changed["base_panel"] = equal_budget.seal(
        {
            key: value
            for key, value in changed["base_panel"].items()
            if key != "panel_digest"
        }
    )
    changed["policy"]["direct"]["stagnation"] = 1
    changed["policy"]["direct"]["restarts"] = 1
    changed["policy"] = adaptive.seal(
        {
            key: value
            for key, value in changed["policy"].items()
            if key != "policy_digest"
        },
        "policy_digest",
    )
    changed = _reseal(changed)
    trace = adaptive.replay(changed, registration, "double")["producer_only_traces"][0][
        "events"
    ]
    assert any(
        entry["event"] == "GLOBAL_EXPLORATION_AFTER_RESTART_LIMIT" for entry in trace
    )
    proposals = [entry for entry in trace if entry["event"] == "PROPOSAL"]
    assert (
        len(proposals) == 5
    )  # no artificial stop while complete panels remain affordable


def test_every_attempt_is_charged_and_full_panel_preflights():
    panel, registration = _panel()
    raw = adaptive.replay(panel, registration, "half")
    for row in raw["results"]:
        direct = row["arms"]["adaptive_solver"]
        assert direct["solver_attempts"] == 2
        assert direct["verified_count"] == 1
        assert direct["best_verified_value"] == 5.0
    trace = raw["producer_only_traces"][0]["events"]
    assert [
        entry["provenance"] for entry in trace if entry["event"] == "SOLVER_ATTEMPT"
    ] == ["failed_reference", "final"]
    assert any(entry["event"] == "STOP_SOLVE_OVER_BUDGET" for entry in trace)


def test_common_cache_warm_provenance_and_full_cost():
    panel, registration = _panel(cached=True)
    raw = adaptive.replay(panel, registration, "base")
    for arm in adaptive.ARMS:
        result = raw["results"][0]["arms"][arm]
        assert result["verified_count"] >= 1
        assert result["spent_wall_s"] >= 0.1
    trace = raw["producer_only_traces"][0]["events"]
    assert any(entry["event"] == "SETTLED_CACHE_HIT" for entry in trace)
    assert any(
        entry["event"] == "SETTLED_SOLVER_ATTEMPT" and entry["warm_start_from_digest"]
        for entry in trace
    )
    invalid = copy.deepcopy(panel)
    invalid["jobs"][0]["cache_source"]["rights"] = "HIDDEN"
    with pytest.raises(adaptive.AdaptiveArmError, match="rights-cleared"):
        adaptive.validate(_reseal(invalid), registration)
    invalid = copy.deepcopy(panel)
    invalid["jobs"][0]["common_cache"][0]["reference"]["value"] = -99
    with pytest.raises(adaptive.AdaptiveArmError, match="cache and current reference"):
        adaptive.validate(_reseal(invalid), registration)
    invalid = copy.deepcopy(panel)
    invalid["jobs"][0]["cache_source"]["condition_panel_digest"] = "sha256:" + "f" * 64
    with pytest.raises(adaptive.AdaptiveArmError, match="exact-condition"):
        adaptive.validate(_reseal(invalid), registration)


def test_finite_f02_direct_enumeration_and_registration_tampering():
    panel, registration = _panel(f02=True)
    raw = adaptive.replay(panel, registration, "half")
    assert (
        raw["results"][0]["arms"]["adaptive_solver"]["solver_attempts"]
        <= budgets.validate(registration).cap("f02", "half").solver_evaluations
    )
    assert raw["results"][0]["arms"]["adaptive_solver"]["status"] == "BUDGET_STOP"
    complete = adaptive.replay(panel, registration, "double")
    assert complete["results"][0]["arms"]["adaptive_solver"]["status"] == "EXHAUSTIVE"
    assert complete["results"][0]["arms"]["adaptive_solver"]["verified_count"] == 9
    bad = copy.deepcopy(panel)
    bad["policy"]["direct"]["method"] = "pattern_multistart"
    with pytest.raises(adaptive.AdaptiveArmError, match="policy digest"):
        adaptive.validate(_reseal(bad), registration)


def test_battery_any_band_hard_breach_and_unresolved_margin():
    panel, registration = _panel(battery=True)
    changed = copy.deepcopy(panel)
    reference = changed["base_panel"]["jobs"][0]["candidates"][1]["reference"]
    reference["status"] = "INFEASIBLE"
    reference["value"] = None
    reference["per_index"]["35"] = {"status": "INFEASIBLE", "value": None}
    changed["jobs"][0]["actions"][1]["margins"]["35"]["limit_a"] = -0.1
    changed["jobs"][0]["actions"][1]["margins"]["40"]["limit_b"] = None
    changed["base_panel"] = equal_budget.seal(
        {
            key: value
            for key, value in changed["base_panel"].items()
            if key != "panel_digest"
        }
    )
    changed = _reseal(changed)
    assert adaptive.validate(changed, registration)
    assert (
        adaptive.compare(
            changed, registration, confidence=0.95, bootstrap_replicates=100, seed=1
        )["status"]
        == "OK"
    )
    wrong = copy.deepcopy(changed)
    wrong["jobs"][0]["actions"][1]["margins"]["35"]["limit_a"] = 0.1
    with pytest.raises(adaptive.AdaptiveArmError, match="margins and settled"):
        adaptive.validate(_reseal(wrong), registration)


def test_typed_action_and_complete_cost_ledger_are_fail_closed():
    panel, registration = _panel()
    wrong = copy.deepcopy(panel)
    wrong["jobs"][0]["actions"][0]["coordinates"]["setting"] = True
    with pytest.raises(adaptive.AdaptiveArmError, match="typed ordinal"):
        adaptive.validate(_reseal(wrong), registration)
    wrong = copy.deepcopy(panel)
    wrong["jobs"][0]["actions"][0]["attempts"][0]["cost"]["core_s"] -= 0.1
    with pytest.raises(adaptive.AdaptiveArmError, match="attempts must equal"):
        adaptive.validate(_reseal(wrong), registration)
    wrong = copy.deepcopy(panel)
    wrong["base_panel"]["budgets"][0]["core_s"] += 1
    wrong["base_panel"] = equal_budget.seal(
        {
            key: value
            for key, value in wrong["base_panel"].items()
            if key != "panel_digest"
        }
    )
    with pytest.raises(adaptive.AdaptiveArmError, match="ladder differs"):
        adaptive.validate(_reseal(wrong), registration)


def test_aggregate_is_disclosure_limited_and_bootstraps_by_bank():
    panel, registration = _panel()
    report = adaptive.compare(
        panel, registration, confidence=0.95, bootstrap_replicates=100, seed=1
    )
    assert report["status"] == "OK"
    assert report["independent_clusters"] == 2
    assert report == adaptive.compare(
        panel, registration, confidence=0.95, bootstrap_replicates=100, seed=1
    )
    output = json.dumps(report)
    assert (
        '"toy-job' not in output
        and '"design_id"' not in output
        and "PROPOSAL" not in output
    )
    assert report["curves"][0]["cluster_bootstrap_ci"] is not None
    altered = copy.deepcopy(panel)
    altered["base_panel"]["jobs"][0]["candidates"][0]["reference"] = {
        "status": "UNRESOLVED",
        "value": None,
    }
    altered["jobs"][0]["actions"][0]["margins"]["limit_a"] = None
    altered["jobs"][0]["actions"][0]["unresolved_cause"] = "FAILED_INFRA"
    altered["base_panel"] = equal_budget.seal(
        {
            key: value
            for key, value in altered["base_panel"].items()
            if key != "panel_digest"
        }
    )
    assert (
        adaptive.compare(
            _reseal(altered),
            registration,
            confidence=0.95,
            bootstrap_replicates=100,
            seed=1,
        )["status"]
        == "UNRESOLVED_PANEL"
    )


def test_cli_defaults_to_aggregates_and_trace_requires_explicit_path(tmp_path, capsys):
    panel, registration = _panel()
    panel_path = tmp_path / "sealed-toy-panel.json"
    registration_path = tmp_path / "registration.json"
    panel_path.write_text(json.dumps(panel), encoding="utf-8")
    registration_path.write_text(json.dumps(registration), encoding="utf-8")
    args = [
        str(panel_path),
        "--budget-registration",
        str(registration_path),
        "--confidence",
        "0.95",
        "--bootstrap-replicates",
        "100",
        "--seed",
        "1",
    ]
    adaptive.main(args)
    stdout = capsys.readouterr().out
    assert json.loads(stdout)["status"] == "OK"
    assert "toy-job" not in stdout and '"observation"' not in stdout
    trace_path = tmp_path / "producer-only.json"
    adaptive.main([*args, "--producer-trace", str(trace_path)])
    capsys.readouterr()
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert "toy-job-0" in json.dumps(trace)
    with pytest.raises(FileExistsError):
        adaptive.main([*args, "--producer-trace", str(trace_path)])
