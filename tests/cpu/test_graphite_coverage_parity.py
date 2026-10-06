"""GRAPHITE-COVERAGE-PARITY-01/-02: coverage on every host, and no flattering score.

The claims tested:
- `scoring.cover` asks every scored case; a case left out or given null is an
  empty prediction, which fails the Challenge's schema gate;
- battery's Graphite frozen rule (`BatteryPracticeRule.score`) types each
  missing case a schema-gate failure, so a partial set is ineligible and no
  case is excluded, and its identity names the coverage rule;
- cooling's and motor's frozen rules (`CoolingPracticeRule.score`,
  `MotorPracticeRule.score`) do the same (GRAPHITE-COVERAGE-PARITY-02), and
  so does cooling's Interface v1 validator (tested with its own adapter in
  `test_challenge_validator_cooling.py`);
- battery's validator (`daemon.incomplete`, read by `_infer`) refuses a worker
  result that leaves a case out or gives it null, as the candidate's;
- Graphite's host scores a pod's partial `predictions.json` ineligible;
- a v2 experiment record never headlines an ineligible set's soft score: it
  reads INELIGIBLE with its gate reasons, and the partial score sits apart,
  labelled "partial coverage, k of n cases"; v1 records stay readable as
  written, and the delivery write-up shows an ineligible baseline as such;
- mutations: each host's check, disabled at the name it is read by, turns its
  guard red.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.agent_campaign.attack.adapters import battery as attack_battery
from carbon.agent_campaign.attack.adapters import cooling as attack_cooling
from carbon.agent_campaign.attack.adapters import motor as attack_motor
from carbon.agent_campaign.graphite import delivery, experiment
from carbon.challenge_validator import (
    battery_scoring,
    cooling_scoring,
    motor_scoring,
    scoring,
)

V1 = "carbon.graphite.phase3.proposal-result.v1"


# -- the shared check ---------------------------------------------------------------------------
def test_cover_asks_every_scored_case_and_lists_the_missing_ones():
    asked, missing = scoring.cover({"a": {"x": 1}, "b": None, "z": {}}, ["a", "b", "c"])
    assert asked == {"a": {"x": 1}, "b": {}, "c": {}}
    assert missing == ["b", "c"]
    assert scoring.cover("not a mapping", ["a"]) == ({"a": {}}, ["a"])


# -- battery's Graphite frozen rule -------------------------------------------------------------
@pytest.fixture(scope="module")
def rule():
    return scoring.scoring_for(attack_battery.CHALLENGE_ID).frozen_rule(".")


def _complete(rule):
    return {r["case_id"]: attack_battery._honest(r) for r in rule.practice.records}


def _guard_battery_rule(rule):
    predictions = _complete(rule)
    rows, full = rule.score(predictions)
    assert full["eligible"] and full["n_missing"] == 0
    dropped = sorted(predictions)[:7]
    partial = {k: v for k, v in predictions.items() if k not in dropped}
    partial[dropped[0]] = None  # null counts as missing too
    rows, summary = rule.score(partial)
    assert summary["n_missing"] == 7
    assert summary["n_gate_failed"] == 7 and summary["n_failed_infra"] == 0
    assert not summary["eligible"]
    states = {r["case_id"]: r["state"] for r in rows}
    assert {states[c] for c in dropped} == {"GATE_FAILED"}
    assert summary["gate_failures"] == {"schema_finite": 7}
    assert rule.identity["coverage"] == scoring.COVERAGE_RULE


def test_battery_frozen_rule_charges_a_missing_case(rule):
    _guard_battery_rule(rule)


# -- cooling's and motor's Graphite frozen rules (GRAPHITE-COVERAGE-PARITY-02) -----------------
#: Each Challenge's attack adapter (its exact public PRACTICE predictions)
#: and how many cases the guard leaves out.
PARITY_HOSTS = {"cooling": (attack_cooling, 7), "motor": (attack_motor, 3)}


def _parity_rule(host):
    adapter, _k = PARITY_HOSTS[host]
    return scoring.scoring_for(adapter.CHALLENGE_ID).frozen_rule(".")


def _guard_parity_rule(host):
    """The same claims as battery's guard, on cooling's or motor's rule: a
    case left out or given null is GATE_FAILED (schema_finite), counted in
    `n_missing`, never FAILED_INFRA, and the set is ineligible."""
    adapter, k = PARITY_HOSTS[host]
    rule = _parity_rule(host)
    predictions = adapter._oracle_predictions()
    rows, full = rule.score(predictions)
    assert full["eligible"] and full["n_missing"] == 0
    assert full["n_scored"] == full["n_cases"] == len(predictions)
    dropped = sorted(predictions)[:k]
    partial = {key: v for key, v in predictions.items() if key not in dropped}
    partial[dropped[0]] = None  # null counts as missing too
    rows, summary = rule.score(partial)
    assert summary["n_missing"] == k
    assert summary["n_gate_failed"] == k and summary["n_failed_infra"] == 0
    assert not summary["eligible"]
    states = {r["case_id"]: r["state"] for r in rows}
    assert {states[c] for c in dropped} == {"GATE_FAILED"}
    assert summary["gate_failures"] == {"schema_finite": k}
    assert rule.score("not a mapping")[1]["n_missing"] == len(predictions)
    assert rule.identity["coverage"] == scoring.COVERAGE_RULE


@pytest.mark.parametrize("host", sorted(PARITY_HOSTS))
def test_cooling_and_motor_frozen_rules_charge_a_missing_case(host):
    _guard_parity_rule(host)


# -- battery's validator ------------------------------------------------------------------------
def _guard_daemon():
    from carbon.battery import daemon
    from carbon.battery.worker import WorkerFailure

    asked = ["c1", "c2"]
    assert not daemon.incomplete({"c1": {}, "c2": {}}, asked)
    assert daemon.incomplete({"c1": {}}, asked)
    assert daemon.incomplete({"c1": {}, "c2": {}, "c3": {}}, asked)
    assert daemon.incomplete({"c1": {}, "c2": None}, asked)
    assert daemon.incomplete(None, asked)

    stored = {}
    store = SimpleNamespace(
        predictions=lambda model_id, case_ids: {},
        model_state=lambda model_id: {"state": b"x"},
        store_predictions=lambda model_id, p: stored.update(p),
    )
    backend = SimpleNamespace(
        infer=lambda identity, state, inputs: {c: None for c in inputs}
    )
    target = SimpleNamespace(store=store, backend=backend)
    try:
        daemon.BatteryValidator._infer(target, "m", asked, {"c1": {}, "c2": {}}, "t")
    except WorkerFailure as refused:
        assert refused.code == "prediction_cases_differ"
        assert refused.candidate and stored == {}
    else:
        raise AssertionError("an incomplete worker result was accepted")


def test_battery_validator_refuses_an_incomplete_worker_result():
    _guard_daemon()


# -- Graphite's host ----------------------------------------------------------------------------
def _guard_graphite_host():
    result = attack_battery._graphite("absent", "worst_k")
    assert result["outcome"] == "SCORED" and result["eligible"] is False
    assert result["n_gate_failed"] == len(result["hit"]) == 20
    assert result["n_scored"] == 180 and result["score"] is None


def test_graphite_host_scores_a_partial_pod_file_ineligible():
    _guard_graphite_host()


# -- item 2: the headline of an ineligible record -----------------------------------------------
SUMMARY = {
    "eligible": False,
    "score": 0.0123,
    "important_score": 0.02,
    "components": {"temperature": 0.01},
    "n_scored": 180,
    "n_gate_failed": 20,
    "gate_failures": {"schema_finite": 20},
}


def _guard_view():
    view = experiment.frozen_rule_view(SUMMARY, 200)
    assert view["headline"] == "INELIGIBLE"
    assert view["score"] is None and view["important_score"] is None
    assert view["components"] is None
    partial = view["partial_coverage"]
    assert partial["label"] == "partial coverage, 180 of 200 cases"
    assert (partial["k"], partial["n"], partial["score"]) == (180, 200, 0.0123)
    eligible = experiment.frozen_rule_view(
        {**SUMMARY, "eligible": True, "n_gate_failed": 0, "gate_failures": {}}, 200
    )
    assert eligible["headline"] == "SCORED" and eligible["score"] == 0.0123
    assert "partial_coverage" not in eligible


def test_an_ineligible_record_headlines_ineligible_with_its_gate_reasons():
    _guard_view()
    assert experiment.PROPOSAL_SCHEMA.endswith(".v2")
    assert V1 in experiment.PROPOSAL_SCHEMAS


def test_v1_records_stay_readable_and_are_never_shown_as_scored():
    """A v1 record keeps its stored fields (nothing rewrites it); every
    reader shows an ineligible one as INELIGIBLE, never its soft score."""
    v1 = {key: SUMMARY[key] for key in experiment.FROZEN_RULE_KEYS}
    assert experiment.frozen_headline(v1) == "INELIGIBLE (schema_finite x20)"
    assert experiment.headline_score(v1) is None
    assert v1["score"] == 0.0123  # read, not rewritten
    eligible = {**v1, "eligible": True}
    assert experiment.headline_score(eligible) == 0.0123
    assert experiment.frozen_headline(eligible) == "SCORED 0.0123"
    line = delivery._result_line("baseline", v1)
    assert "0.0123" not in line and "INELIGIBLE" in line
    assert delivery._result_line("baseline", eligible) == (
        "- baseline: eligible True; score 0.0123"
    )


def test_a_run_records_an_ineligible_proposal_without_a_headline_score():
    """End to end on Graphite's host: a pod's non-finite set is a v2 record
    whose score column is empty and whose partial score is labelled."""
    result = attack_battery._graphite("nonfinite_temperature", "worst_k")
    assert result["outcome"] == "SCORED" and result["score"] is None


# -- mutations: each host's check, disabled where it is read, turns its guard red -------------------
def _battery_rule_excludes(m):
    def excluding(predictions, case_ids):
        source = predictions if isinstance(predictions, dict) else {}
        return {case: source.get(case) for case in case_ids}, []

    m.setattr(battery_scoring, "cover", excluding)


def _daemon_checks_keys_only(m):
    from carbon.battery import daemon

    m.setattr(
        daemon, "incomplete", lambda predictions, asked: set(predictions) != set(asked)
    )


def _bare_score_view(m):
    def v1_view(summary, n_cases):
        return {key: summary.get(key) for key in experiment.FROZEN_RULE_KEYS}

    m.setattr(experiment, "frozen_rule_view", v1_view)


def _rule_excludes(module):
    def mutate(m):
        def excluding(predictions, case_ids):
            source = predictions if isinstance(predictions, dict) else {}
            return {case: source.get(case) for case in case_ids}, []

        m.setattr(module, "cover", excluding)

    return mutate


MUTATIONS = {
    "cooling_rule_excludes_a_missing_case": (
        _rule_excludes(cooling_scoring),
        lambda: _guard_parity_rule("cooling"),
    ),
    "motor_rule_excludes_a_missing_case": (
        _rule_excludes(motor_scoring),
        lambda: _guard_parity_rule("motor"),
    ),
    "battery_rule_excludes_a_missing_case": (
        _battery_rule_excludes,
        lambda: _guard_battery_rule(
            scoring.scoring_for(attack_battery.CHALLENGE_ID).frozen_rule(".")
        ),
    ),
    "graphite_host_excludes_a_missing_case": (
        _battery_rule_excludes,
        _guard_graphite_host,
    ),
    "battery_validator_checks_keys_only": (_daemon_checks_keys_only, _guard_daemon),
    "ineligible_record_headlines_its_soft_score": (
        _bare_score_view,
        _guard_view,
    ),
    "graphite_run_records_a_bare_score": (
        _bare_score_view,
        test_a_run_records_an_ineligible_proposal_without_a_headline_score,
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_each_disabled_check_turns_its_guard_red(name, monkeypatch):
    mutate, guard = MUTATIONS[name]
    mutate(monkeypatch)
    with pytest.raises((AssertionError, KeyError, TypeError)):
        guard()
