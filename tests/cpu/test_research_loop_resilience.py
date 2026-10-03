"""The research loop through provider trouble (OWNER-LAUNCHPAD-PROD-01,
LP-PROD-A).

A reply the provider ended early is a turn like any other: one model call,
metered exactly; the calls it finished run, a call it cut off is answered
`call_truncated` without running, and a journalled note asks the model to
continue. A provider failure propagates with the epoch kept open: a failure
that incurred no charge is retried inside the call, a key the miner fixes is
sent again on resume, and a call whose outcome is unknown is never resent
until the campaign is reconciled, after which the same turn goes on under a
fresh identity.

Deterministic Responses mocks test control flow, never agent evidence.
"""

import json
import time

import pytest
from test_cw1_research_ledger import ledger
from test_cw1_research_loop import response
from test_model_provider import rejected
from test_parallel_tool_calls_v2 import (
    LIST,
    SDK,
    START,
    call,
    epoch,
    folder,
    never,
    outputs,
    text,
)

from carbon.development_session.profile import canonical
from carbon.development_session.research_agent import (
    RESERVATION_NANO,
    ProviderCallFailed,
    settle_uncertain_calls,
)
from carbon.development_session.research_agent_policy import (
    AUTONOMOUS,
    PARALLEL_CALLS,
    PARALLEL_CALLS_V2,
)
from carbon.development_session.research_loop import CALL_TRUNCATED

RULES = [None, PARALLEL_CALLS, PARALLEL_CALLS_V2]


def ended(output, reason="max_output_tokens", output_tokens=2048):
    """A reply the provider ended early, as the translators present it."""
    return {
        **response(output),
        "status": "incomplete",
        "incomplete_details": {"reason": reason},
        "usage": {"input_tokens": 10, "output_tokens": output_tokens},
    }


def replies(*items):
    """A transport replying with each item in order: a list is a completed
    turn's output, a dict a whole reply, an exception is raised. Each request
    is kept as it was sent."""
    queue, requests = list(items), []

    def transport(request):
        requests.append(json.loads(canonical(request)))
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return response(item) if type(item) is list else item

    return transport, requests


def notes(request):
    return [
        item["content"]
        for item in request["input"]
        if item.get("role") == "user" and item["content"].startswith("Carbon: ")
    ]


@pytest.mark.parametrize("rule", RULES)
def test_a_reply_cut_off_before_any_call_asks_the_model_to_continue(tmp_path, rule):
    """It used to raise on every resume. Now it is one model call, metered,
    and the next turn carries a note; it is not a choice to stop."""
    meter = ledger(tmp_path)
    transport, requests = replies(ended([text("Thinking at length")]), [text()])
    result = epoch(meter, SDK(), transport, rule=rule)
    assert result["status"] == "STOPPED"
    assert result["reason"] == "agent elected to stop"
    assert len(requests) == 2
    (note,) = notes(requests[1])
    assert "cut off at its limit of 2048 output tokens" in note
    assert "more concisely" in note
    record = json.loads(
        (folder(meter) / "epoch-1-provider-000-truncated.json").read_bytes()
    )
    assert record["reason"] == "max_output_tokens" and record["cut_calls"] == []
    assert record["message"]["content"] == note
    used = meter.status(owner="alice")["used"]
    assert used["provider_attempts"] == 2
    # Exact: the cut turn's own usage, then the second turn's.
    assert used["provider_nanodollars"] == (10 * 250 + 2048 * 2000) + (
        10 * 250 + 20 * 2000
    )
    turn = json.loads((folder(meter) / "epoch-1-provider-000-turn.json").read_bytes())
    assert turn["incomplete"]["reason"] == "max_output_tokens"
    # A resume replays it all: no provider call, the same outcome.
    assert epoch(meter, SDK(), never, rule=rule) == result


def test_a_cut_turn_replays_byte_identically(tmp_path):
    """Interrupted after a cut turn, a resume rebuilds the same history from
    the retained reply and the journals: the next request is byte-identical
    and the cut turn is not sent again."""
    meter = ledger(tmp_path)
    sdk = SDK(meter)
    transport, requests = replies(
        ended([call("a"), call("b")]), rejected(401, "invalid_api_key"), [text()]
    )
    with pytest.raises(ProviderCallFailed):
        epoch(meter, sdk, transport)
    assert epoch(meter, sdk, transport)["status"] == "STOPPED"
    assert len(requests) == 3 and requests[2] == requests[1]
    assert sdk.dispatched == [(LIST, "epoch-1-tool-000")]


def test_finished_calls_run_and_the_cut_one_is_answered(tmp_path):
    meter = ledger(tmp_path)
    sdk = SDK(meter)
    transport, requests = replies(ended([call("a"), call("b")]), [text()])
    epoch(meter, sdk, transport)
    # The finished call ran; the last one, cut off, did not.
    assert sdk.dispatched == [(LIST, "epoch-1-tool-000")]
    answered = dict(outputs(requests[1]))
    assert answered["a"] == {"status": "OK", "fixture": True}
    assert answered["b"]["status"] == "REJECTED_BEFORE_DISPATCH"
    assert answered["b"]["code"] == CALL_TRUNCATED
    assert "cut off at its limit of 2048 output tokens" in answered["b"]["reason"]
    (note,) = notes(requests[1])
    assert "did not run (call_truncated)" in note and "finished ran" in note
    # The note follows the answers, as the turn's last item.
    assert requests[1]["input"][-2]["content"] == note
    record = json.loads(
        (folder(meter) / "epoch-1-provider-000-truncated.json").read_bytes()
    )
    assert record["cut_calls"] == ["b"]
    assert epoch(meter, sdk, never)["status"] == "STOPPED"
    assert len(sdk.dispatched) == 1


@pytest.mark.parametrize("rule", [None, PARALLEL_CALLS])
def test_a_cut_single_call_is_answered_under_the_older_rules(tmp_path, rule):
    meter = ledger(tmp_path)
    sdk = SDK(meter)
    transport, requests = replies(
        ended([call("a", START, {"kind": "practice"})]), [text()]
    )
    epoch(meter, sdk, transport, rule=rule)
    assert sdk.dispatched == []
    assert meter.status(owner="alice")["used"]["research_trials"] == 0
    assert dict(outputs(requests[1]))["a"]["code"] == CALL_TRUNCATED


def test_the_providers_own_item_status_decides_what_was_finished(tmp_path):
    """A call the provider marks unfinished is cut wherever it is; a last call
    it marks completed runs."""
    meter = ledger(tmp_path)
    sdk = SDK(meter)
    first = {**call("a"), "status": "incomplete"}
    last = {**call("b"), "status": "completed"}
    transport, requests = replies(ended([first, last]), [text()])
    epoch(meter, sdk, transport)
    assert sdk.dispatched == [(LIST, "epoch-1-tool-000-01")]
    answered = dict(outputs(requests[1]))
    assert answered["a"]["code"] == CALL_TRUNCATED and answered["b"]["status"] == "OK"


def test_another_early_end_is_named_without_asking_for_brevity(tmp_path):
    meter = ledger(tmp_path)
    transport, requests = replies(
        ended([text("No.")], reason="content_filter"), [text()]
    )
    epoch(meter, SDK(), transport)
    (note,) = notes(requests[1])
    assert "ended before it finished (provider reason: content_filter)" in note
    assert "concisely" not in note


def test_a_cut_reply_spends_no_free_text_reminder(tmp_path):
    meter = ledger(tmp_path)
    transport, requests = replies(ended([text()]), [text()], [text()])
    result = epoch(meter, SDK(), transport, agent_policy=AUTONOMOUS)
    assert result["reason"] == "unstructured agent stop after one clarification"
    assert len(requests) == 3
    assert len(list(folder(meter).glob("*-continuation.json"))) == 1


def test_a_call_with_an_unknown_outcome_waits_for_settlement_then_goes_on(tmp_path):
    meter = ledger(tmp_path)
    sdk = SDK(meter)
    transport, requests = replies([call("a")], TimeoutError("timed out"), [text()])
    with pytest.raises(ProviderCallFailed) as failed:
        epoch(meter, sdk, transport)
    assert failed.value.requires_settlement
    assert not (folder(meter) / "outcome.json").exists()  # the epoch stays open
    # Unsettled, a resume resends nothing.
    with pytest.raises(ValueError, match="no resend"):
        epoch(meter, sdk, never)
    settled = settle_uncertain_calls(meter, owner="alice")
    assert [s["identity"] for s in settled["settled"]] == ["epoch-1-provider-001"]
    result = epoch(meter, sdk, transport)
    assert result["status"] == "STOPPED" and len(requests) == 3
    # The same turn, sent again under a fresh identity: the same request.
    assert requests[2] == requests[1]
    turn = json.loads((folder(meter) / "epoch-1-provider-001-turn.json").read_bytes())
    assert turn["settled"] == ["epoch-1-provider-001"] and turn["attempts"] == 2
    used = meter.status(owner="alice")["used"]
    assert used["provider_attempts"] == 3
    assert used["provider_nanodollars"] == RESERVATION_NANO + 2 * (10 * 250 + 20 * 2000)
    assert sdk.dispatched == [(LIST, "epoch-1-tool-000")]


def test_a_rejected_key_is_sent_again_on_resume_without_settlement(tmp_path):
    meter = ledger(tmp_path)
    transport, requests = replies(
        [call("a")], rejected(401, "invalid_api_key"), [text()]
    )
    with pytest.raises(ProviderCallFailed) as failed:
        epoch(meter, SDK(), transport)
    assert failed.value.resumable and not failed.value.requires_settlement
    # The miner fixed the key: the resume sends the turn again and goes on.
    assert epoch(meter, SDK(), transport)["status"] == "STOPPED"
    assert len(requests) == 3 and requests[2] == requests[1]
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 3


def test_a_busy_provider_is_retried_inside_the_turn(tmp_path, monkeypatch):
    waits = []
    monkeypatch.setattr(time, "sleep", waits.append)
    meter = ledger(tmp_path)
    transport, requests = replies(rejected(429), rejected(503), [text()])
    assert epoch(meter, SDK(), transport)["status"] == "STOPPED"
    assert len(requests) == 3 and len(waits) == 2
    turn = json.loads((folder(meter) / "epoch-1-provider-000-turn.json").read_bytes())
    assert turn["attempts"] == 3 and len(turn["rejections"]) == 2
    assert turn["charge_nanodollars"] == 10 * 250 + 20 * 2000
