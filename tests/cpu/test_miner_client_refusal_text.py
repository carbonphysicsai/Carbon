"""Miner client refusal text (miner-ux item 1): the client carries the receiver's own sentence for the waiting and
allowance-group codes, `version_closed` and `door_updating`, and names the 32 KiB budget in build refusals.

The client copies the receiver's sentences as literals (the client imports no validator code); these tests hold each
copy to the receiver's own constant, so the page cannot drift from the door."""

from __future__ import annotations

from pathlib import Path

import pytest

from carbon.battery import intake as battery_intake
from carbon.challenge_validator import coldkey_waiting, exam_cap
from carbon.development_session import direct_submission as client
from scripts.dev.miner_launchpad import supervisor

KEPT = " Your frozen candidate is kept."


def test_the_waiting_codes_carry_the_receivers_own_sentence_then_the_clients_tail():
    coldkey = supervisor.NEXT_ACTIONS["coldkey_submission_waiting"]
    hotkey = supervisor.NEXT_ACTIONS["hotkey_submission_waiting"]
    assert coldkey.startswith(coldkey_waiting.MESSAGE)
    assert hotkey.startswith(coldkey_waiting.HOTKEY_MESSAGE)
    assert coldkey_waiting.CODE == "coldkey_submission_waiting"
    assert coldkey_waiting.HOTKEY_CODE == "hotkey_submission_waiting"
    # The tails name the Launchpad's own button and say another hotkey may be the one waiting.
    assert "Withdraw (while queued)" in hotkey and "Withdraw (while queued)" in coldkey
    assert "Another hotkey under your coldkey" in coldkey
    assert coldkey.endswith(KEPT) and hotkey.endswith(KEPT)


def test_the_launchpad_button_the_tails_name_exists():
    page = (Path(supervisor.__file__).parent / "app.js").read_text(encoding="utf-8")
    assert "Withdraw (while queued)" in page


def test_the_group_refusals_use_no_internal_name_and_keep_the_receivers_facts():
    # The receiver's sentences say "funder map" and "chain snapshot"; the miner is told in plain words. The fact the
    # receiver states (no graded-exam slot used) stays, and the receiver still says it.
    for code, receiver in (
        (
            "allowance_group_unmapped",
            exam_cap.GROUPED_LIMIT_TEXT["allowance_group_unmapped"],
        ),
        ("allowance_group_unresolved", coldkey_waiting.UNRESOLVED_MESSAGE),
    ):
        text = supervisor.NEXT_ACTIONS[code]
        assert "funder map" not in text and "chain snapshot" not in text
        assert "No graded-exam slot was used" in text and "Try again later" in text
        assert "last 4 characters of your hotkey" in text
        assert "slot" in receiver or "allowance" in receiver


def test_the_updating_door_sentence_is_the_doors_own_words():
    text = supervisor.NEXT_ACTIONS["door_updating"]
    assert battery_intake.UPDATING_MESSAGE in text
    assert "Your place in line" in text and "few minutes" not in text


def test_every_new_code_has_its_own_sentence():
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
        # A refusal that is ours never tells the miner to send it again; a rule of theirs says when to try again.
        if code not in ("direct_task_cancelled", "version_closed"):
            assert "again" in text.lower() or "retry" in text.lower()


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
    assert "32 KiB size limit" in text
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
