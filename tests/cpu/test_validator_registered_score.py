"""VALIDATOR-26: the validator scores by a registered score-tuning candidate.

OWNER-BATTERY-SCORE-RULE-01 adopted the score; OWNER-BATTERY-V3-FINALS-01
fixed its use:
- screening and nomination use the candidate's score (higher is better) and
  gate, with v2's important-region guard kept;
- finals keep v2's paired accuracy comparison and add the candidate's gate
  on the finalist batch.

The term (registry, registry_sha256, candidate) comes from the deployment's
configuration and the rule's digest binds it. The score is `score_tuning`'s
own. A missing score, design questions or reference is infrastructure
(FAILED_INFRA), never the miner's; the candidate's own failure on the
questions makes it ineligible. No container, chain, network or spend.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.battery import deployment, exam
from carbon.battery.daemon import BatteryValidator, rule_digest
from carbon.battery.value import registered_score as rs
from carbon.battery.value import score_tuning as st
from carbon.battery.worker import WorkerFailure

REGISTRY = "docs/development/evidence/battery-score-tuning/registry-v5.json"
CANDIDATE = "G-FEAS/A-Q>@0.05"
DECISION = "OWNER-BATTERY-SCORE-CANDIDATE-01"


@pytest.fixture(scope="module")
def term():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    _candidates, identity = st.load_registry(root / REGISTRY)
    return {
        "registry": REGISTRY,
        "registry_sha256": identity["sha256"],
        "candidate": CANDIDATE,
        "decision": DECISION,
    }


# -- the rule and its term -----------------------------------------------------------------------
def test_v3_bank_sched_is_v2_bank_sched_scored_by_a_registered_candidate():
    v3, v2 = exam.RULES["v3-bank-sched"], exam.RULES["v2-bank-sched"]
    assert v3["score"] == exam.REGISTERED_SCORE
    assert dict(v3, score=None, authority=None) == dict(v2, score=None, authority=None)
    assert exam.disclosure(v3) == exam.disclosure(v2)  # still sealed


def test_the_deployment_supplies_the_term_and_the_digest_binds_it(term):
    rule = deployment.rule_for({"rule": "v3-bank-sched", "score": term})
    assert rule["score"] == term
    other = deployment.rule_for(
        {"rule": "v3-bank-sched", "score": {**term, "candidate": "A-Q"}}
    )
    assert rule_digest(rule) != rule_digest(other)


@pytest.mark.parametrize(
    "config, code",
    [
        ({"rule": "v3-bank-sched"}, "evaluation_config_score"),
        (
            {"rule": "v3-bank-sched", "score": {"candidate": "x"}},
            "evaluation_config_score",
        ),
        (
            {"rule": "v2-bank-sched", "score": {"candidate": "x"}},
            "evaluation_config_score_not_in_rule",
        ),
        (
            {
                "rule": "v3-bank-sched",
                "score": {
                    "registry": REGISTRY,
                    "registry_sha256": "0" * 64,
                    "candidate": CANDIDATE,
                    "decision": "the owner said so",
                },
            },
            "evaluation_config_score",
        ),
    ],
)
def test_a_missing_or_stray_term_is_refused(config, code):
    with pytest.raises(deployment.EvaluationUnavailable, match=code):
        deployment.rule_for(config)


# -- the registered candidate --------------------------------------------------------------------
def test_the_candidate_loads_from_its_committed_registry(term, monkeypatch):
    found = rs.RegisteredScore(term, ".")
    assert found.candidate.id == CANDIDATE
    assert found.candidate.gate["comparison"] == "exceeds"


@pytest.mark.parametrize(
    "change, code",
    [
        ({"registry_sha256": "0" * 64}, "registered_score_registry_changed"),
        ({"candidate": "no-such-candidate"}, "registered_score_candidate_unknown"),
        ({"registry": "docs/elsewhere.json"}, "registered_score_term_malformed"),
        (
            {"decision": "OWNER-NO-SUCH-RECORD-99"},
            "registered_score_decision_unrecorded",
        ),
        ({"decision": "not-an-owner-record"}, "registered_score_term_malformed"),
    ],
)
def test_a_changed_registry_or_unknown_candidate_is_refused(term, change, code):
    with pytest.raises(rs.RegisteredScoreRefused, match=code):
        rs.RegisteredScore({**term, **change}, ".")


# -- the owner's #1101 security conditions -------------------------------------------------------
def test_the_owner_record_must_name_the_candidate_and_the_registry_digest(
    term, tmp_path
):
    """(1) A candidate is owner-only: its record must name both."""
    assert rs.check_decision(term, ".").name.endswith(DECISION + ".md")
    decisions = tmp_path / ".agent" / "decisions"
    decisions.mkdir(parents=True)
    record = decisions / "2026-10-11-OWNER-X-01.md"
    other = {**term, "decision": "OWNER-X-01"}
    record.write_text(f"## 2026-10-11 — OWNER-X-01: candidate {CANDIDATE}\n")
    with pytest.raises(rs.RegisteredScoreRefused, match="decision_mismatch"):
        rs.check_decision(other, tmp_path)  # names no digest
    record.write_text(
        f"## 2026-10-11 — OWNER-X-01: {CANDIDATE}\n{term['registry_sha256']}\n"
    )
    assert rs.check_decision(other, tmp_path) == record
    # A record that only mentions the id in its body is not the record.
    record.write_text(f"## 2026-10-11 — OWNER-Y-01\nOWNER-X-01 {CANDIDATE}\n")
    with pytest.raises(rs.RegisteredScoreRefused, match="decision_unrecorded"):
        rs.check_decision(other, tmp_path)


def test_every_window_commitment_names_the_term(term):
    """(2) The producer commits the active term with each window."""
    from carbon.challenge_validator.battery import BatteryBatchSource

    source = object.__new__(BatteryBatchSource)
    v3 = deployment.rule_for({"rule": "v3-bank-sched", "score": term})
    source.adapter = SimpleNamespace(target=SimpleNamespace(rule=v3))
    assert source.score_term() == term
    source.adapter.target.rule = exam.RULES["v2-bank-sched"]
    assert source.score_term() is None


def _importer(rule):
    return SimpleNamespace(
        identities=lambda: {"contract_digest": "c", "rule_digest": rule_digest(rule)},
        target=SimpleNamespace(rule=rule),
    )


def test_a_window_naming_another_term_is_refused(term):
    """(2) A validator imports only windows naming its own term."""
    from carbon.challenge_validator.answer_key import AnswerKeyRefused
    from carbon.challenge_validator.battery import BatteryAdapter

    mine = deployment.rule_for({"rule": "v3-bank-sched", "score": term})
    other = {**term, "candidate": "A-Q"}
    for named in (other, None):
        commitment = {"contract_digest": "c", "rule_digest": rule_digest(mine)}
        if named is not None:
            commitment["score"] = named
        with pytest.raises(AnswerKeyRefused, match="answer_key_score_mismatch"):
            BatteryAdapter.import_answer_key(_importer(mine), commitment, {})
    v2 = exam.RULES["v2-bank-sched"]
    with pytest.raises(AnswerKeyRefused, match="answer_key_score_mismatch"):
        BatteryAdapter.import_answer_key(
            _importer(v2),
            {"contract_digest": "c", "rule_digest": rule_digest(v2), "score": term},
            {},
        )


def test_a_candidate_change_is_prospective_a_new_deployment_state(term, tmp_path):
    """(3) A changed term is a changed rule: the bound state refuses it, so
    a new candidate starts a new deployment state and nothing is rescored."""
    from carbon.battery.pool_store import PoolStore, StateError

    rule = deployment.rule_for({"rule": "v3-bank-sched", "score": term})
    changed = deployment.rule_for(
        {"rule": "v3-bank-sched", "score": {**term, "candidate": "A-Q"}}
    )
    store = PoolStore(tmp_path / "state.sqlite3", rule=rule)
    store.bind({"rule": rule, "rule_digest": rule_digest(rule)})
    with pytest.raises(StateError, match="identities_changed"):
        store.bind({"rule": changed, "rule_digest": rule_digest(changed)})
    with pytest.raises(StateError, match="identities_not_carryable"):
        store.rebind(
            {"rule": changed, "rule_digest": rule_digest(changed)}, decision="x"
        )


def test_the_score_is_score_tunings_own(term, monkeypatch):
    found = rs.RegisteredScore(term, ".")
    row = {
        "eligible": True,
        "legs": {"a": 0.8, "q": 0.5},
        "gates": {"feasibility": 0.05},
        "E": 0.25,
    }
    monkeypatch.setattr(st, "member_legs", lambda *a, **k: row)
    measured = found.measure({}, [], None, 1.0)
    assert measured["score"] == st.score_member(found.candidate, row)
    assert (
        measured["gate"] == st.gate_verdict(found.candidate, row) == "PASS"
    )  # 0.05 passes
    monkeypatch.setattr(
        st, "member_legs", lambda *a, **k: {**row, "gates": {"feasibility": 0.051}}
    )
    assert found.gate({}, [], None) == "FAIL"


def test_q_pools_the_windows_and_types_the_failures():
    ok = {"status": "OK", "mean_regret": 1.0, "per_question": [{}] * 8}
    half = {"status": "OK", "mean_regret": 3.0, "per_question": [{}] * 8}
    assert rs.pooled_regret({"a": ok, "b": half}) == (2.0, None)
    assert rs.pooled_regret({"a": ok, "b": {"status": "INELIGIBLE"}}) == (
        None,
        "q_candidate_failed",
    )
    assert rs.pooled_regret({"a": ok, "b": {"status": "VOID"}}) == (
        None,
        "q_unavailable",
    )


# -- nomination ----------------------------------------------------------------------------------
def _record(score, *, eligible=True, important=0.1):
    return {
        "eligible": eligible,
        "pool_version": 1,
        "important_score": important,
        "registered": {"score": score},
    }


def test_nomination_is_by_the_registered_score_higher_is_better():
    margin = 0.05
    assert exam.nominate_registered(_record(0.8), _record(0.7), margin) == (
        True,
        "nominated",
    )
    assert not exam.nominate_registered(_record(0.72), _record(0.7), margin)[
        0
    ]  # inside margin
    assert not exam.nominate_registered(
        _record(0.9, eligible=False), _record(0.7), margin
    )[0]
    assert exam.nominate_registered(_record(0.8), None, margin) == (
        True,
        "no incumbent",
    )
    assert not exam.nominate_registered(_record(None), None, margin)[0]


def test_the_important_region_guard_is_kept():
    ok, why = exam.nominate_registered(
        _record(0.9, important=0.2), _record(0.7, important=0.1), 0.05
    )
    assert not ok and "important-region" in why


# -- the daemon: infrastructure is never the miner's -----------------------------------------------
class _Scorer:
    def __init__(self, batches):
        self.design = SimpleNamespace(
            inputs=lambda designs: {"q1": {}},
            measure=lambda designs, preds: {"batches": batches},
        )

    pooled = staticmethod(rs.pooled_regret)

    def measure(self, preds, ids, store, regret):
        return {"score": 0.5, "gate": "PASS", "eligible": True, "regret": regret}


def _daemon(scorer, designs):
    return SimpleNamespace(
        registered_score=scorer,
        store=SimpleNamespace(design=lambda f: designs.get(f)),
        _quiz_predictions=lambda *a, **k: {"q1": {}},
        DESIGN_PREDICTIONS="design/",
    )


POOL = {"version": 3, "active": ["f1", "f2"]}
OK = {"status": "OK", "mean_regret": 1.0, "per_question": [{}]}


def test_the_score_needs_the_scorer_and_every_windows_questions():
    with pytest.raises(WorkerFailure) as missing:
        BatteryValidator._registered(_daemon(None, {}), "m", {}, [], None, POOL, "")
    assert missing.value.code == "registered_score_not_installed"
    assert missing.value.candidate is False
    daemon = _daemon(_Scorer({"f1": OK}), {"f1": {"questions": {}}})
    with pytest.raises(WorkerFailure) as nodesign:
        BatteryValidator._registered(daemon, "m", {}, [], None, POOL, "")
    assert nodesign.value.code == "registered_score_design_missing"
    assert nodesign.value.candidate is False


def test_a_reference_failure_is_infrastructure_and_a_candidate_failure_is_ineligible():
    designs = {"f1": {}, "f2": {}}
    void = _daemon(_Scorer({"f1": OK, "f2": {"status": "VOID"}}), designs)
    with pytest.raises(WorkerFailure) as failed:
        BatteryValidator._registered(void, "m", {}, [], None, POOL, "")
    assert failed.value.code == "registered_score_q_unavailable"
    assert failed.value.candidate is False
    ineligible = _daemon(_Scorer({"f1": OK, "f2": {"status": "INELIGIBLE"}}), designs)
    found = BatteryValidator._registered(ineligible, "m", {}, [], None, POOL, "")
    assert found["eligible"] is False and found["cause"] == "q_candidate_failed"
    scored = BatteryValidator._registered(
        _daemon(_Scorer({"f1": OK, "f2": OK}), designs), "m", {}, [], None, POOL, ""
    )
    assert scored["eligible"] is True and scored["regret"] == 1.0


def test_the_intake_admits_only_without_the_score():
    rule = {"score": {"candidate": CANDIDATE}}
    assert not deployment.scores_here(SimpleNamespace(rule=rule, registered_score=None))
    assert deployment.scores_here(SimpleNamespace(rule=rule, registered_score=object()))
    assert deployment.scores_here(SimpleNamespace(rule={}, registered_score=None))


def test_the_supervisor_runs_the_scored_entry_point(tmp_path):
    from scripts.dev.battery_validator_service.supervisor import _daemon_module

    path = tmp_path / "d.json"
    path.write_text(json.dumps({"rule": "v3-bank-sched", "score": {}}))
    assert _daemon_module(path) == "carbon.battery.value.scored_operate"
    path.write_text(json.dumps({"rule": "v2-bank-sched"}))
    assert _daemon_module(path) == "carbon.battery.operate"
