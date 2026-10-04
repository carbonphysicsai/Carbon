"""GRAPHITE-01 phase 1: the escalation rule on the owner's Engy ladder.

One rung, only on a recorded typed research failure; never on success or an
infrastructure failure; never a skipped rung; never above the top.
"""

from __future__ import annotations

import pytest
from graphite_fixtures import provider, reader_script, spec, started

from carbon.agent_campaign.graphite import ladder as gl
from carbon.agent_campaign.graphite.ladder import Ladder, LadderError
from carbon.agent_campaign.graphite.model import ScriptedModel, fail
from carbon.agent_campaign.graphite.roles import (
    CONSTRUCTOR_STALL_ATTEMPTS,
    ROLES,
    FailureKind,
    RoleName,
)
from carbon.development_session.model_provider import ENGY_LADDER

EVIDENCE = "sha256:" + "e" * 64


def _attempt(call):
    """The outcome of one escalation attempt as a value: the result or the
    refusal code. Any other exception fails the calling assertion."""
    try:
        return call()
    except Exception as error:  # noqa: BLE001 - asserted below
        assert type(error) is LadderError, repr(error)
        return error.code


def test_escalation_moves_exactly_one_rung_on_a_recorded_failure(tmp_path):
    ladder = Ladder(tmp_path / "ladder")
    role = RoleName.CONSTRUCTOR
    assert ladder.model(role) == ENGY_LADDER[0]
    failure = ladder.record_failure(role, FailureKind.BUILD_FAILED_TO_COMPILE, EVIDENCE)
    step = ladder.escalate(role, failure)
    assert step["from_model"] == ENGY_LADDER[0]
    assert step["to_model"] == ENGY_LADDER[1]
    assert ladder.model(role) == ENGY_LADDER[1]
    assert ladder.history() == [
        {
            "sequence": 1,
            "role": role.value,
            "failure": failure,
            "kind": FailureKind.BUILD_FAILED_TO_COMPILE.value,
            "evidence": EVIDENCE,
            "from_model": ENGY_LADDER[0],
            "to_model": ENGY_LADDER[1],
        }
    ]
    # Other roles are untouched.
    assert ladder.model(RoleName.READER) == ROLES[RoleName.READER].start_model


def test_no_escalation_without_a_recorded_failure(tmp_path):
    ladder = Ladder(tmp_path / "ladder")
    role = RoleName.READER
    outcome = _attempt(lambda: ladder.escalate(role, "failure-0000000000000000"))
    assert outcome == "no_recorded_failure"
    assert ladder.model(role) == ROLES[role].start_model
    assert ladder.history() == []


def test_a_successful_session_does_not_escalate(tmp_path):
    graphite, run_id = started(tmp_path / "graphite", ScriptedModel(reader_script()))
    assert graphite.run(run_id) == "succeeded"
    assert graphite.ladder.model(RoleName.READER) == ROLES[RoleName.READER].start_model
    assert graphite.ladder.history() == []


def test_an_infrastructure_failure_is_not_a_research_failure(tmp_path):
    graphite, run_id = started(
        tmp_path / "graphite", ScriptedModel([fail(503, "overloaded")])
    )
    assert graphite.run(run_id) == "failed"
    ladder = graphite.ladder
    for kind in ("provider_call_failed", "reconciliation_required", "run_cap_reached"):
        with pytest.raises(LadderError, match="not_a_typed_research_failure"):
            ladder.record_failure(RoleName.READER, kind, EVIDENCE)
    assert ladder.model(RoleName.READER) == ROLES[RoleName.READER].start_model


def test_each_failure_escalates_once_and_only_its_own_role(tmp_path):
    ladder = Ladder(tmp_path / "ladder")
    failure = ladder.record_failure(
        RoleName.READER, FailureKind.CARD_EXTRACTION_ERROR, EVIDENCE
    )
    with pytest.raises(LadderError, match="failure_belongs_to_another_role"):
        ladder.escalate(RoleName.WRITER, failure)
    ladder.escalate(RoleName.READER, failure)
    with pytest.raises(LadderError, match="failure_already_consumed"):
        ladder.escalate(RoleName.READER, failure)
    assert ladder.model(RoleName.READER) == ENGY_LADDER[1]
    with pytest.raises(LadderError, match="failure_kind_not_for_this_role"):
        ladder.record_failure(
            RoleName.READER, FailureKind.WRITEUP_FAILED_CHECKLIST, EVIDENCE
        )
    with pytest.raises(ValueError, match="sha256"):
        ladder.record_failure(RoleName.READER, FailureKind.CARD_EXTRACTION_ERROR, "x")


def test_rungs_are_never_skipped(tmp_path):
    ladder = Ladder(tmp_path / "ladder")
    role = RoleName.CONSTRUCTOR
    seen = [ladder.model(role)]
    for _ in range(len(ENGY_LADDER) - 1):
        failure = ladder.record_failure(
            role,
            FailureKind.BUILD_STALLED_AGAINST_BASELINE,
            EVIDENCE,
            attempts=CONSTRUCTOR_STALL_ATTEMPTS,
        )
        _attempt(lambda f=failure: ladder.escalate(role, f))
        seen.append(ladder.model(role))
    assert seen == list(ENGY_LADDER)


def test_the_top_rung_is_a_ceiling(tmp_path):
    ladder = Ladder(tmp_path / "ladder")
    role = RoleName.PLANNER
    assert ladder.model(role) == "glm-5.2"
    first = ladder.record_failure(role, FailureKind.PLAN_NOT_RUNNABLE, EVIDENCE)
    assert _attempt(lambda: ladder.escalate(role, first))["to_model"] == "kimi-k3"
    second = ladder.record_failure(role, FailureKind.PLAN_NOT_DISTINCT, EVIDENCE)
    assert _attempt(lambda: ladder.escalate(role, second)) == "ladder_top"
    assert ladder.model(role) == ENGY_LADDER[-1]
    assert len(ladder.history()) == 1


def test_a_running_session_keeps_its_model_and_the_next_one_escalates(tmp_path):
    model = ScriptedModel(reader_script() + reader_script())
    graphite = provider(tmp_path / "graphite", model)
    first = graphite.start(spec(graphite), "k1").provider_run_id
    failure = graphite.ladder.record_failure(
        RoleName.READER, FailureKind.CARD_EXTRACTION_ERROR, EVIDENCE
    )
    graphite.ladder.escalate(RoleName.READER, failure)
    assert graphite.run(first) == "succeeded"
    assert {r["model"] for r in model.requests} == {ENGY_LADDER[0]}
    second = graphite.start(spec(graphite), "k2").provider_run_id
    assert graphite.run(second) == "succeeded"
    assert model.requests[-1]["model"] == ENGY_LADDER[1]
    assert graphite.session_record(second)["role"]["rung"] == 1
    assert graphite.session_record(first)["role"]["rung"] == 0


def test_the_ladder_is_the_owner_ladder():
    assert gl.LADDER == ENGY_LADDER
    assert gl.TOP == len(ENGY_LADDER) - 1


def test_the_constructor_stall_limit_is_the_registered_five_attempts(tmp_path):
    """OWNER-GRAPHITE-02: builds count as stalled only over 5 attempts."""
    assert CONSTRUCTOR_STALL_ATTEMPTS == 5
    ladder = Ladder(tmp_path / "ladder")
    role, kind = RoleName.CONSTRUCTOR, FailureKind.BUILD_STALLED_AGAINST_BASELINE
    for attempts in (None, 0, 1, 4, "5", True):
        assert _attempt(
            lambda a=attempts: ladder.record_failure(role, kind, EVIDENCE, attempts=a)
        ) in (
            "stall_below_registered_attempts",
            "attempts_is_a_positive_integer",
        ), attempts
    failure = ladder.record_failure(role, kind, EVIDENCE, attempts=5)
    assert _attempt(lambda: ladder.escalate(role, failure))["to_model"] == (
        ENGY_LADDER[1]
    )
    assert ladder.record_failure(role, kind, EVIDENCE, attempts=9)
