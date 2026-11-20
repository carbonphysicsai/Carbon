"""Miner client refusal text (miner-ux item 1): the client carries the receiver's own sentence for the waiting and
allowance-group codes, `version_closed` and `door_updating`, and names the 32 KiB budget in build refusals.

The client copies the receiver's sentences as literals (the client imports no validator code); these tests hold each
copy to the receiver's own constant, so the page cannot drift from the door."""

from __future__ import annotations

import pytest

from carbon.battery import intake as battery_intake
from carbon.challenge_validator import coldkey_waiting, exam_cap
from carbon.development_session import direct_submission as client
from scripts.dev.miner_launchpad import supervisor

KEPT = " Your frozen candidate is kept."


def test_the_waiting_codes_carry_the_receivers_own_sentence():
    assert supervisor.NEXT_ACTIONS["coldkey_submission_waiting"] == (
        coldkey_waiting.MESSAGE + KEPT
    )
    assert supervisor.NEXT_ACTIONS["hotkey_submission_waiting"] == (
        coldkey_waiting.HOTKEY_MESSAGE + KEPT
    )
    assert coldkey_waiting.CODE == "coldkey_submission_waiting"
    assert coldkey_waiting.HOTKEY_CODE == "hotkey_submission_waiting"


def test_the_unmapped_group_carries_the_receivers_own_sentence():
    receiver = exam_cap.GROUPED_LIMIT_TEXT["allowance_group_unmapped"]
    assert supervisor.NEXT_ACTIONS["allowance_group_unmapped"] == receiver + KEPT


def test_the_unresolved_group_sentence_is_true_of_both_receiver_sentences():
    # The receiver says it at admission and at grade in two sentences; the client's one holds the shared facts.
    text = supervisor.NEXT_ACTIONS["allowance_group_unresolved"]
    for receiver in (
        coldkey_waiting.UNRESOLVED_MESSAGE,
        exam_cap.GROUPED_LIMIT_TEXT["allowance_group_unresolved"],
    ):
        assert "match this hotkey to its coldkey in its latest chain snapshot" in receiver
        assert "match this hotkey to its coldkey in its latest chain snapshot" in text
    assert "Try again later" in text and "graded-exam slot" in text


def test_the_updating_door_sentence_is_the_doors_own_words():
    assert battery_intake.UPDATING_MESSAGE in supervisor.NEXT_ACTIONS["door_updating"]


def test_every_new_code_has_its_own_sentence_that_says_to_try_again():
    for code in (
        "hotkey_submission_waiting",
        "coldkey_submission_waiting",
        "allowance_group_unmapped",
        "allowance_group_unresolved",
        "version_closed",
        "door_updating",
        "direct_task_cancelled",
    ):
        text = supervisor.next_action(code)
        assert text != supervisor.FALLBACK_ACTION
        assert "again" in text.lower()


@pytest.mark.parametrize(
    "code",
    [
        "fitted_info_over_budget",
        "bundle_graph_caps_refused",
        "cap_exceeded",
        "bundle_graph_oversized",
    ],
)
def test_a_graph_budget_refusal_names_the_32_kib_budget_in_bytes_not_tokens(code):
    text = supervisor.next_action(code)
    assert "32 KiB" in text
    assert "bytes" in text and "not tokens" in text
    assert "zlib" in text


def test_the_waiting_and_group_codes_keep_the_receivers_retry_message():
    for code in (
        "hotkey_submission_waiting",
        "coldkey_submission_waiting",
        "allowance_group_unmapped",
        "allowance_group_unresolved",
    ):
        answer = {"refused": code, "retry": {"message": "the receiver's sentence"}}
        assert client._refusal_retry(answer, code) == {
            "message": "the receiver's sentence"
        }
    # Only the closed fields, only the closed types, only for these codes.
    answer = {"retry": {"message": "x", "path": "/root", "next_block": "7"}}
    assert client._refusal_retry(answer, "coldkey_submission_waiting") == {
        "message": "x"
    }
    assert client._refusal_retry(answer, "construction_intake_unavailable") == {}


def test_a_503_updating_answer_is_a_typed_refusal_with_the_doors_sentence():
    answer = {
        "status": "updating",
        "message": battery_intake.UPDATING_MESSAGE,
        "retry_after_s": 60,
    }
    with pytest.raises(client.DirectIntakeRefusal) as caught:
        client._raise_if_pre_admission_refusal(503, answer)
    assert caught.value.code == "door_updating"
    assert not isinstance(caught.value, client.DirectIntakeRateLimit)
    assert caught.value.retry == {
        "message": battery_intake.UPDATING_MESSAGE,
        "retry_after_s": 60,
    }


def test_a_503_without_the_updating_status_is_not_door_updating():
    client._raise_if_pre_admission_refusal(503, {"status": "ok"})
    client._raise_if_pre_admission_refusal(200, {"status": "updating"})
