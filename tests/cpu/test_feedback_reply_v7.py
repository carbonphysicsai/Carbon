"""The v7 feedback reply (Validator-2 15 Nov, P-1..P-4): Ladder documents with the NOT_SCORED reasons TIMED_OUT / STOPPED_EARLY.

Claims: v7 is opt-in by the kit's request and advertised; every older reply (v1..v6) withholds each document carrying one of
those reasons as null (never a substitute reason) and is otherwise unchanged; a kit whose reason list is pinned to today's
reads such an older reply with no refusal (and would refuse the v7 document whole, which is why it is withheld); a v7 kit
asks for v7 where advertised and reads both reasons.
"""

# ruff: noqa: F811
from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.challenge_validator import direct_intake
from carbon.challenge_validator.ladder_store import LadderStore
from carbon.development_session import direct_submission as client
from carbon.scoring import grade_feedback as gf
from tests.cpu.test_gate_failure_feedback import (  # noqa: F401 - the fixtures and helpers
    EXAM,
    HOTKEY,
    SID,
    _intake,
    ledger,
)

#: The reason list of a kit installed before v7 (pinned: the field's view).
TODAY_REASONS = (
    "LEG_MINIMUM_FAILED",
    "CANDIDATE_INVALID",
    "DECISION_INELIGIBLE",
    "FAILED_INFRA",
    "INDETERMINATE",
)
CHALLENGE = SimpleNamespace(challenge_id="electric-motor-magnetics", version="1.8")
DIGEST = "sha256:" + "a" * 64
REASON_OF = {gf.WALL_STOP_STATUS: "TIMED_OUT", gf.EARLY_STOP_STATUS: "STOPPED_EARLY"}
OLDER = (
    {},
    {"v3": True},
    {"v4": True},
    {"v4": True, "v5": True},
    {"v4": True, "v5": True, "v6": True},
)
V7 = {"v4": True, "v5": True, "v6": True, "v7": True}


def _ladder(ledger, *statuses):
    """A scored best, then each status in turn as the latest."""
    store = LadderStore(ledger)
    common = {
        "exam_version": "exam-1",
        "gates": ["g"],
        "rebuild_noise": None,
        "recipe_digest": DIGEST,
    }
    store.record(
        HOTKEY,
        CHALLENGE,
        EXAM,
        {
            "status": "SCORED_DEVELOPMENT_CANDIDATE",
            "score": 0.6,
            "gates": {"g": "PASS"},
        },
        epoch=1,
        **common,
    )
    for epoch, status in enumerate(statuses, 2):
        store.record(HOTKEY, CHALLENGE, EXAM, {"status": status}, epoch=epoch, **common)


def _intake7(ledger):
    intake = _intake(ledger, {SID: HOTKEY})
    intake.challenge = CHALLENGE
    return intake


def _reply(intake, **kw):
    return direct_intake.DirectRecipeIntake._feedback(
        intake, HOTKEY, submission_id=SID, **kw
    )


@pytest.mark.parametrize("status", [gf.WALL_STOP_STATUS, gf.EARLY_STOP_STATUS])
def test_every_older_reply_withholds_a_stopped_document_and_v7_carries_it(
    ledger, status
):
    _ladder(
        ledger, gf.WALL_STOP_STATUS, status
    )  # an earlier stop, then the latest stop
    intake = _intake7(ledger)
    for kw in OLDER:
        reply = _reply(intake, **kw)
        assert reply.status == 200, kw
        assert reply.body["latest"] is None, kw  # withheld, never a substitute reason
        assert reply.body["best"]["status"] == "IMPROVED", kw  # the best is unchanged
        text = repr(reply.body)
        assert "TIMED_OUT" not in text and "STOPPED_EARLY" not in text, kw
        assert reply.body["schema"] != direct_intake.FEEDBACK_REPLY_SCHEMA_V7, kw
    plain = direct_intake.DirectRecipeIntake._feedback(intake, HOTKEY)  # the v1 read
    assert plain.status == 200 and plain.body["latest"] is None
    v7 = _reply(intake, **V7)
    assert v7.body["schema"] == direct_intake.FEEDBACK_REPLY_SCHEMA_V7
    assert v7.body["latest"]["status"] == "NOT_SCORED"
    assert v7.body["latest"]["reason"] == REASON_OF[status]
    # the submission part of v7 is v6's, unchanged
    assert v7.body["submission"] == _reply(intake, **OLDER[-1]).body["submission"]


def test_a_reply_without_a_stop_is_the_same_in_every_version(ledger):
    _ladder(ledger, "FAILED_INFRA")
    intake = _intake7(ledger)
    latest = _reply(intake, **V7).body["latest"]
    assert latest["reason"] == "FAILED_INFRA"
    for kw in OLDER:
        assert _reply(intake, **kw).body["latest"] == latest, kw


def test_v7_is_opt_in_recognised_and_advertised():
    assert direct_intake.feedback_reply({"reply": "v7", "submission_id": SID}) == "v7"
    from pathlib import Path

    text = Path(direct_intake.__file__).read_text(encoding="utf-8")
    assert '"exam_feedback_v7"' in text
    assert direct_intake.V7_ONLY_REASONS == ("TIMED_OUT", "STOPPED_EARLY")
    assert set(direct_intake.V7_ONLY_REASONS) == set(gf.REASONS) - set(TODAY_REASONS)


# --- the kit -------------------------------------------------------------------------------------------------------


def _kit(monkeypatch, reply, versions):
    """Read ``reply`` (the receiver's body) through `read_exam_feedback`, against a receiver advertising ``versions``."""
    sent = []
    recipe = object.__new__(client.ConstructionRecipe)
    monkeypatch.setattr(
        client.ConstructionRecipe,
        "to_dict",
        lambda self: {
            "challenge": {"id": "electric-motor-magnetics", "version": "1.8"}
        },
    )
    monkeypatch.setattr(client, "_body", lambda facts, **kw: {"fields": kw["fields"]})
    monkeypatch.setattr(
        client,
        "BittensorMessageSigner",
        lambda signer: SimpleNamespace(sign=lambda body, **kw: {}),
    )
    every = {
        "v2": client.FEEDBACK_V2_FACTS,
        "v3": client.FEEDBACK_V3_FACTS,
        "v4": client.FEEDBACK_V4_FACTS,
        "v5": client.FEEDBACK_V5_FACTS,
        "v6": client.FEEDBACK_V6_FACTS,
        "v7": getattr(client, "FEEDBACK_V7_FACTS", None),
    }
    facts = {"exam_feedback": client.FEEDBACK_FACTS}
    facts.update({"exam_feedback_" + v: every[v] for v in versions})

    def send(url, body, headers):
        sent.append(body["fields"])
        return 200, reply

    got = client.read_exam_feedback(
        "http://127.0.0.1:1",
        "external-signer",
        recipe=recipe,
        contract_digest="sha256:" + "c" * 64,
        receiver="validator",
        context=None,
        read=lambda url: facts,
        send=send,
        submission_id=SID,
    )
    return got, sent[-1]


def test_a_kit_pinned_to_todays_reasons_reads_an_older_reply_with_no_refusal(
    ledger, monkeypatch
):
    _ladder(ledger, gf.WALL_STOP_STATUS, gf.EARLY_STOP_STATUS)
    older = _reply(_intake7(ledger), **OLDER[-1]).body
    stopped = _reply(_intake7(ledger), **V7).body
    monkeypatch.setattr(gf, "REASONS", TODAY_REASONS)  # a kit in the field
    six = ("v2", "v3", "v4", "v5", "v6")
    got, sent = _kit(monkeypatch, older, six)
    assert sent == {"reply": "v6", "submission_id": SID}
    assert got["latest"] is None and got["best"]["status"] == "IMPROVED"
    # served as v6, the stopped document would be refused whole: why every older reply withholds it
    with pytest.raises(client.DirectIntakeRefusal):
        _kit(
            monkeypatch,
            {**stopped, "schema": direct_intake.FEEDBACK_REPLY_SCHEMA_V6},
            six,
        )


@pytest.mark.parametrize("status", [gf.WALL_STOP_STATUS, gf.EARLY_STOP_STATUS])
def test_a_v7_kit_asks_for_v7_where_advertised_and_reads_the_reason(
    ledger, monkeypatch, status
):
    _ladder(ledger, status)
    body = _reply(_intake7(ledger), **V7).body
    got, sent = _kit(monkeypatch, body, ("v2", "v3", "v4", "v5", "v6", "v7"))
    assert sent == {"reply": "v7", "submission_id": SID}
    assert got["latest"]["reason"] == REASON_OF[status]
    assert got["submission"] == body["submission"]


def test_a_v7_kit_against_a_receiver_without_v7_asks_v6_unchanged(ledger, monkeypatch):
    _ladder(ledger, "FAILED_INFRA")
    body = _reply(_intake7(ledger), **OLDER[-1]).body
    got, sent = _kit(monkeypatch, body, ("v2", "v3", "v4", "v5", "v6"))
    assert sent == {"reply": "v6", "submission_id": SID}
    assert got["latest"]["reason"] == "FAILED_INFRA"
