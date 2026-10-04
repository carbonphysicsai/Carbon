"""Provider resilience (OWNER-LAUNCHPAD-PROD-01, LP-PROD-A).

A reply the provider ended early comes back metered to a caller that accepts
one; failures that incurred no charge are retried with bounded backoff, each
attempt still admitted by the ledger; and a call whose outcome is unknown is
never resent blind, but an explicit, journalled settlement books its full
reservation and lets the next call of its turn go out under a fresh identity.

Every transport here is a FIXTURE: no provider is contacted, no key is real.
"""

import io
import json

import pytest
from test_cw1_research_ledger import ledger
from test_model_provider import completed, rejected, request
from test_product_campaign_ledger import OWNER, product

from carbon.development_session import model_provider as mp
from carbon.development_session import research_agent as ra
from carbon.development_session.research_agent import (
    MODEL_CAVEAT,
    PROVIDER_SETTLEMENT,
    RESERVATION_NANO,
    ProviderCallFailed,
    ProviderCallUnresolved,
    SettlementRefused,
    incomplete_reply,
    provider_turns,
    request_model,
    settle_uncertain_call,
    settle_uncertain_calls,
    uncertain_calls,
)
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import CampaignLedger, ReconcileFenced

METERED = 100 * 250 + 10 * 2000


def cut_off(output_tokens=2048, **extra):
    return {
        **completed(usage={"input_tokens": 100, "output_tokens": output_tokens}),
        "status": "incomplete",
        "incomplete_details": {"reason": "max_output_tokens"},
        **extra,
    }


def script(*replies):
    """A transport replying in order; an exception is raised."""
    calls, queue = [], list(replies)

    def transport(value):
        calls.append(value)
        reply = queue.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply

    return transport, calls


def args(transport, **extra):
    return {
        "owner": "alice",
        "identity": "model-1",
        "request": request(),
        "credential_file": None,
        "transport": transport,
        "sleep": pytest.fail,
        **extra,
    }


def operation(meter, identity):
    (op,) = [
        op for op in meter.status(owner="alice")["operations"] if op["id"] == identity
    ]
    return op


def directory(meter, identity, owner="alice"):
    return ra._call_directory(meter, owner, identity)


# -- an incomplete reply ------------------------------------------------------


def test_an_incomplete_reply_comes_back_metered_to_a_caller_that_accepts_it(tmp_path):
    meter = ledger(tmp_path)
    transport, calls = script(cut_off())
    reply = request_model(meter, **args(transport, accept_incomplete=True))
    assert reply["status"] == "incomplete"
    assert incomplete_reply(reply, 2048) == {
        "reason": "max_output_tokens",
        "output_tokens": 2048,
        "max_output_tokens": 2048,
    }
    # One call, booked exactly at its metered usage - not the reservation.
    op = operation(meter, "model-1")
    assert op["state"] == "FAILED_INFRA"  # as an early end was always recorded
    assert op["actual"]["provider_attempts"] == 1
    assert op["actual"]["provider_nanodollars"] == 100 * 250 + 2048 * 2000
    assert op["result"]["incomplete"]["reason"] == "max_output_tokens"
    # A replay returns the retained reply and sends nothing.
    assert request_model(meter, **args(transport, accept_incomplete=True)) == reply
    assert len(calls) == 1
    (turn,) = provider_turns(meter.status(owner="alice")["operations"])
    assert turn["incomplete"]["max_output_tokens"] == 2048


def test_without_acceptance_an_incomplete_reply_still_raises(tmp_path):
    """Every other caller keeps its historical behaviour, replay included."""
    meter = ledger(tmp_path)
    transport, calls = script(cut_off())
    with pytest.raises(ValueError, match="incomplete provider response"):
        request_model(meter, **args(transport))
    with pytest.raises(ValueError, match="reconciliation required, no resend"):
        request_model(meter, **args(transport))
    assert len(calls) == 1


def test_an_incomplete_reply_recorded_before_this_change_now_resumes(tmp_path):
    """The old code recorded the same row - FAILED_INFRA, the response
    retained, no `incomplete` field - and raised; the accepting caller now
    reads it back instead of stopping on it forever."""
    meter = ledger(tmp_path)
    transport, _ = script(cut_off())
    with pytest.raises(ValueError, match="incomplete provider response"):
        request_model(meter, **args(transport))
    with meter.db() as db:
        (result,) = db.execute(
            "SELECT result FROM operations WHERE id='model-1'"
        ).fetchone()
        old = {k: v for k, v in json.loads(result).items() if k != "incomplete"}
        db.execute(
            "UPDATE operations SET result=? WHERE id='model-1'",
            (json.dumps(old),),
        )
    reply = request_model(meter, **args(script()[0], accept_incomplete=True))
    assert reply["status"] == "incomplete"


@pytest.mark.parametrize(
    "stop, reason",
    [
        ("max_tokens", "max_output_tokens"),
        ("pause_turn", "pause_turn"),
        ("refusal", "refusal"),
    ],
)
def test_an_unfinished_messages_turn_says_how_it_ended(stop, reason):
    reply = mp.messages_response(
        {
            "model": "m",
            "content": [{"type": "text", "text": "partial"}],
            "stop_reason": stop,
            "usage": {"input_tokens": 3, "output_tokens": 4},
        }
    )
    assert reply["incomplete_details"] == {"reason": reason}
    assert incomplete_reply(reply, 99)["reason"] == reason
    # A reply retained before `incomplete_details` existed is read from its
    # Messages stop reason.
    del reply["incomplete_details"]
    assert incomplete_reply(reply, 99)["reason"] == reason


def test_a_completed_reply_is_not_incomplete():
    assert incomplete_reply(completed(), 2048) is None


# -- failures that incurred no charge -----------------------------------------


def test_an_unavailable_server_and_an_unreachable_one_are_retried_uncharged(
    tmp_path,
):
    meter = ledger(tmp_path)
    waits = []
    transport, calls = script(
        rejected(502),
        mp.ProviderUnreachable("nothing sent"),
        rejected(529, retry_after="7"),
        completed(),
    )
    reply = request_model(
        meter, **args(transport, sleep=waits.append, jitter=lambda: 0.5)
    )
    assert reply == completed() and len(calls) == 4
    # Backoff with equal jitter: 2*0.75, then 4*0.75, then the Retry-After.
    assert waits == [1.5, 3.0, 7]
    used = meter.status(owner="alice")["used"]
    assert used["provider_attempts"] == 4
    assert used["provider_nanodollars"] == METERED
    rejections = [
        op["result"]["provider_rejection"]["provider_outcome"]
        for op in meter.status(owner="alice")["operations"]
        if "provider_rejection" in op["result"]
    ]
    assert rejections == ["server_unavailable", "unreachable", "server_unavailable"]
    (turn,) = provider_turns(meter.status(owner="alice")["operations"])
    assert turn["attempts"] == 4 and turn["charge_nanodollars"] == METERED


def test_an_unusable_key_file_is_a_credential_failure_not_an_unknown_outcome(
    tmp_path,
):
    """The key is read before anything is sent, so a missing key file is the
    miner's to fix - not a call to reconcile - and a resume after the fix
    sends the request."""
    key = tmp_path / "missing.key"
    selection = mp.select(
        provider_id="openai-compatible-responses",
        model_id="fixture-model",
        endpoint="https://llm.example.invalid/v1/responses",
        credential={"kind": "file", "reference": str(key)},
    )
    sent = []

    class Opener:
        def open(self, outgoing, timeout):
            sent.append(outgoing)
            return io.BytesIO(json.dumps(completed("fixture-model")).encode())

    transport = mp.SelectionTransport(selection, opener=Opener())
    meter = ledger(tmp_path / "campaign")
    call = args(transport, request=request(selection), provider=selection)
    with pytest.raises(ProviderCallFailed, match="no retry") as failed:
        request_model(meter, **call)
    assert failed.value.outcome is mp.ProviderOutcome.AUTH_CREDENTIAL
    assert failed.value.resumable and sent == []
    assert operation(meter, "model-1")["state"] == "FAILED_INFRA"
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 1
    key.write_text("fixture-not-a-key")
    assert request_model(meter, **call)["status"] == "completed"
    assert len(sent) == 1


def test_every_retry_is_admitted_by_the_miner_ceiling(tmp_path):
    """Bounded by the ceilings: the third attempt is over the miner's
    provider-attempt budget, so it is refused before it is reserved."""
    meter = ledger(tmp_path, ceilings={"provider_attempts": 2})
    transport, calls = script(rejected(429), rejected(429), completed())
    with pytest.raises(ValueError, match="miner budget: provider_attempts"):
        request_model(meter, **args(transport, sleep=lambda _: None))
    assert len(calls) == 2
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 2


def test_the_backoff_doubles_with_jitter_and_honours_retry_after():
    assert ra.retry_wait(0, jitter=lambda: 0) == 1
    assert ra.retry_wait(0, jitter=lambda: 1) == 2
    assert ra.retry_wait(3, jitter=lambda: 0) == 8
    assert ra.retry_wait(10, jitter=lambda: 1) == ra.MAX_BACKOFF_SECONDS
    assert ra.retry_wait(0, 45, jitter=lambda: 1) == 45
    with pytest.raises(ValueError, match="jitter"):
        ra.retry_wait(0, jitter=lambda: 2)


# -- a call whose outcome is unknown ------------------------------------------


@pytest.mark.parametrize(
    "reply, reason",
    [
        (TimeoutError("timed out"), "transport_outcome_unknown"),
        (rejected(500), "transport_outcome_unknown"),
        ({**completed(), "usage": None}, "usage_unavailable"),
        (completed("gpt-5-mini-2025-08-07-other"), "model_mismatch"),
    ],
)
def test_settlement_books_the_full_reservation_and_the_turn_goes_on(
    tmp_path, reply, reason
):
    meter = ledger(tmp_path)
    transport, calls = script(reply, completed())
    with pytest.raises(ValueError):
        request_model(meter, **args(transport))
    # Unsettled, nothing is resent.
    with pytest.raises(ValueError, match="no resend"):
        request_model(meter, **args(transport))
    assert len(calls) == 1
    (pending,) = uncertain_calls(meter, owner="alice")
    assert pending["identity"] == "model-1" and pending["reason"] == reason
    assert pending["refusal"] is None
    # Another model's price is unknown: booked, with that said beforehand.
    caveat = MODEL_CAVEAT if reason == "model_mismatch" else None
    assert pending["caveat"] == caveat
    settlement = settle_uncertain_call(meter, owner="alice", identity="model-1")
    assert settlement["schema"] == PROVIDER_SETTLEMENT
    assert settlement["reason"] == reason and settlement["retry_dispatched"] is False
    assert settlement["booked"]["provider_nanodollars"] == RESERVATION_NANO
    assert settlement["caveat"] == caveat
    # Journalled beside the call, and booked: never less than can be charged.
    journal = json.loads((directory(meter, "model-1") / "settlement.json").read_bytes())
    assert journal == settlement
    op = operation(meter, "model-1")
    assert op["state"] == "FAILED_INFRA"
    assert op["actual"] == op["reservation"]
    assert op["result"]["provider_settlement"] == settlement
    # Settled again: the same settlement, nothing booked twice.
    assert settle_uncertain_call(meter, owner="alice", identity="model-1") == settlement
    # The turn goes on under a fresh identity with its own reservation.
    assert request_model(meter, **args(transport)) == completed()
    assert len(calls) == 2
    assert operation(meter, "model-1-rl1")["state"] == "SUCCEEDED"
    used = meter.status(owner="alice")["used"]
    assert used["provider_attempts"] == 2
    assert used["provider_nanodollars"] == RESERVATION_NANO + METERED
    (turn,) = provider_turns(meter.status(owner="alice")["operations"])
    assert turn["settled"] == ["model-1"] and turn["state"] == "SUCCEEDED"
    assert "outcome unknown; full reservation booked by settlement" in (
        turn["charge_basis"]
    )
    # A replay walks past the settlement to the retained reply.
    assert request_model(meter, **args(transport)) == completed()
    assert len(calls) == 2


def test_a_call_with_no_record_of_why_settles_as_unknown(tmp_path):
    """A call left unresolved before this change has no `uncertain.json`."""
    meter = ledger(tmp_path)
    transport, _ = script(TimeoutError("timed out"))
    with pytest.raises(ProviderCallFailed):
        request_model(meter, **args(transport))
    (directory(meter, "model-1") / "uncertain.json").unlink()
    settlement = settle_uncertain_call(meter, owner="alice", identity="model-1")
    assert settlement["reason"] == "outcome_unknown"
    assert settlement["request_retained"] and not settlement["response_retained"]


def test_a_reported_charge_above_the_reservation_is_never_settled_under_it(tmp_path):
    key = tmp_path / "key"
    key.write_text("fixture-not-a-key")
    selection = mp.select(
        provider_id="engy-chat",
        model_id="deepseek-v4-flash-0731",
        credential={"kind": "file", "reference": str(key)},
    )
    meter = ledger(tmp_path / "campaign")
    over = {
        **completed("deepseek-v4-flash-0731"),
        "x_engy": {"charged_micro": selection.reservation_nano // 1000 + 1},
    }
    transport, _ = script(over)
    with pytest.raises(ValueError, match="exceeds the reservation"):
        request_model(
            meter,
            **args(transport, request=request(selection), provider=selection),
        )
    (pending,) = uncertain_calls(meter, owner="alice")
    assert pending["refusal"] == "charge_exceeds_reservation"
    with pytest.raises(SettlementRefused) as refused:
        settle_uncertain_call(meter, owner="alice", identity="model-1")
    assert refused.value.code == "charge_exceeds_reservation"
    assert operation(meter, "model-1")["state"] == "RESERVED"
    # The same, read from the retained reply when no record says why.
    (directory(meter, "model-1") / "uncertain.json").unlink()
    with pytest.raises(SettlementRefused, match="charge_exceeds_reservation"):
        settle_uncertain_call(meter, owner="alice", identity="model-1")


def test_settlement_refuses_what_it_cannot_settle(tmp_path):
    meter = ledger(tmp_path)
    transport, _ = script(completed(), TimeoutError("timed out"))
    request_model(meter, **args(transport))
    for identity, owner, code in (
        ("model-1", "alice", "not_uncertain"),
        ("model-404", "alice", "operation_unavailable"),
        ("model-1", "mallory", "operation_unavailable"),
    ):
        with pytest.raises(SettlementRefused) as refused:
            settle_uncertain_call(meter, owner=owner, identity=identity)
        assert refused.value.code == code
    meter.reserve(
        "trial-1",
        owner="alice",
        phase="research",
        request={"fixture": True},
        resources={"research_trials": 1},
    )
    with pytest.raises(SettlementRefused, match="not_a_provider_call"):
        settle_uncertain_call(meter, owner="alice", identity="trial-1")
    # A retained request that differs from the reserved one is kept as is.
    with pytest.raises(ProviderCallFailed):
        request_model(meter, **args(transport, identity="model-2"))
    (directory(meter, "model-2") / "request.json").chmod(0o600)
    (directory(meter, "model-2") / "request.json").write_bytes(b"{}")
    with pytest.raises(SettlementRefused, match="request_changed"):
        settle_uncertain_call(meter, owner="alice", identity="model-2")
    assert operation(meter, "model-2")["state"] == "RESERVED"
    result = settle_uncertain_calls(meter, owner="alice")
    assert result == {
        "settled": [],
        "refused": [{"identity": "model-2", "code": "request_changed"}],
    }


def reconcile(meter):
    """What the reconcile action does first, under the campaign's owner lock:
    a fresh control generation, the campaign observed RECONCILING."""
    meter.generation = CampaignControl(meter).acquire()
    return meter


def test_a_controlled_campaign_dispatches_again_only_after_settlement(tmp_path):
    """A product campaign refuses every model call while one call's outcome
    is unknown; the reconcile action's settlement is what unblocks it.

    Changed with the settlement fence (LP-PROD-A review): the settlement now
    runs as the reconcile action does, after `CampaignControl.acquire`; the
    run's own holder, still RUNNING, is refused (`control_fenced`)."""
    meter = product(tmp_path)
    transport, calls = script(TimeoutError("timed out"), completed())
    call = {**args(transport), "owner": OWNER}
    with pytest.raises(ProviderCallFailed):
        request_model(meter, **call)
    with pytest.raises(ValueError, match="reconcile before dispatch"):
        request_model(meter, **{**call, "identity": "model-2"})
    assert settle_uncertain_calls(meter, owner=OWNER) == {
        "settled": [],
        "refused": [{"identity": "model-1", "code": "control_fenced"}],
    }
    result = settle_uncertain_calls(reconcile(meter), owner=OWNER)
    assert [s["identity"] for s in result["settled"]] == ["model-1"]
    assert result["refused"] == []
    assert request_model(meter, **call) == completed()
    assert len(calls) == 2
    assert uncertain_calls(meter, owner=OWNER) == []


# -- the settlement fences (LP-PROD-A review) ---------------------------------


def test_a_running_or_stale_holder_never_settles(tmp_path):
    """Only the campaign's reconcile action books a settlement: the run's own
    holder (RUNNING) and a holder whose generation another acquire superseded
    are refused, before anything is journalled and again in the booking's own
    transaction."""
    meter = product(tmp_path)
    transport, _ = script(TimeoutError("timed out"))
    with pytest.raises(ProviderCallFailed):
        request_model(meter, **{**args(transport), "owner": OWNER})
    folder = directory(meter, "model-1", owner=OWNER)
    with pytest.raises(SettlementRefused) as refused:
        settle_uncertain_call(meter, owner=OWNER, identity="model-1")
    assert refused.value.code == "control_fenced"
    reconcile(meter)
    # A second holder acquires after it: the first one's generation is stale.
    second = reconcile(CampaignLedger(meter.root, clock=lambda: 1000))
    with pytest.raises(SettlementRefused, match="control_fenced"):
        settle_uncertain_call(meter, owner=OWNER, identity="model-1")
    with pytest.raises(ReconcileFenced):
        meter.finish(
            "model-1",
            owner=OWNER,
            state="FAILED_INFRA",
            actual=operation_of(meter, OWNER, "model-1")["reservation"],
            result={"fixture": True},
            reconciling=True,
        )
    assert not (folder / "settlement.json").exists()
    assert operation_of(meter, OWNER, "model-1")["state"] == "RESERVED"
    # The current holder settles it.
    settlement = settle_uncertain_call(second, owner=OWNER, identity="model-1")
    assert settlement["identity"] == "model-1"
    assert operation_of(meter, OWNER, "model-1")["state"] == "FAILED_INFRA"


def test_a_call_in_flight_is_never_settled(tmp_path):
    """A call holds the campaign's provider-call lease from before its
    reservation until it is booked, so a settlement - in this process or
    another - never books it and lets a later call send it again."""
    meter = ledger(tmp_path)
    seen = {}

    def transport(value):
        # model-1 is in flight here.
        try:
            settle_uncertain_call(meter, owner="alice", identity="model-1")
        except SettlementRefused as refused:
            seen["code"] = refused.code
        seen["listed"] = uncertain_calls(meter, owner="alice")
        seen["batch"] = settle_uncertain_calls(meter, owner="alice")
        raise TimeoutError("timed out")

    with pytest.raises(ProviderCallFailed):
        request_model(meter, **args(transport))
    assert seen["code"] == "call_in_flight"
    (row,) = seen["listed"]
    assert row["identity"] == "model-1" and row["refusal"] == "call_in_flight"
    assert seen["batch"] == {
        "settled": [],
        "refused": [{"identity": "model-1", "code": "call_in_flight"}],
    }
    assert operation(meter, "model-1")["state"] == "RESERVED"
    # Once the call has ended, the same settlement goes through.
    (row,) = uncertain_calls(meter, owner="alice")
    assert row["refusal"] is None
    settlement = settle_uncertain_call(meter, owner="alice", identity="model-1")
    assert settlement["reason"] == "transport_outcome_unknown"


def operation_of(meter, owner, identity):
    (op,) = [
        op for op in meter.status(owner=owner)["operations"] if op["id"] == identity
    ]
    return op


# -- usage beyond the reserved limits (LP-PROD-A review) ----------------------


def test_usage_costing_more_than_the_reservation_is_never_settled(tmp_path):
    """A reply whose own usage meters above the reservation (50,000 output
    tokens against a 2,048 limit) is not booked at the reservation: settling
    it would under-count spend. Refused, whether or not the call's journal
    survives."""
    meter = ledger(tmp_path)
    over = completed(usage={"input_tokens": 100, "output_tokens": 50000})
    transport, _ = script(over)
    with pytest.raises(ProviderCallUnresolved) as unresolved:
        request_model(meter, **args(transport))
    assert unresolved.value.reason == "usage_exceeds_reservation"
    report = unresolved.value.report()
    assert report["code"] == "provider_usage_exceeds_reservation"
    assert report["requires_settlement"] and not report["resumable"]
    journal = json.loads((directory(meter, "model-1") / "uncertain.json").read_bytes())
    assert journal["reason"] == "usage_exceeds_reservation"
    assert journal["metered_nanodollars"] == 100 * 250 + 50000 * 2000
    assert journal["metered_nanodollars"] > RESERVATION_NANO
    (pending,) = uncertain_calls(meter, owner="alice")
    assert pending["refusal"] == "usage_exceeds_reservation"
    with pytest.raises(SettlementRefused, match="usage_exceeds_reservation"):
        settle_uncertain_call(meter, owner="alice", identity="model-1")
    # Read from the retained reply itself when no record says why.
    (directory(meter, "model-1") / "uncertain.json").unlink()
    with pytest.raises(SettlementRefused, match="usage_exceeds_reservation"):
        settle_uncertain_call(meter, owner="alice", identity="model-1")
    assert operation(meter, "model-1")["state"] == "RESERVED"


def test_usage_beyond_the_limits_that_fits_the_reservation_is_settled(tmp_path):
    """A few output tokens over the limit (a chat provider counting reasoning
    outside its cap) still cost less than the reservation: the journal says
    so, with the charge, and the settlement books the reservation. Without
    that journal nothing shows the charge fits, so it is refused."""
    meter = ledger(tmp_path)
    over = completed(usage={"input_tokens": 100, "output_tokens": 2100})
    transport, _ = script(over, over)
    with pytest.raises(ProviderCallUnresolved, match="exceeds reservation") as raised:
        request_model(meter, **args(transport))
    assert raised.value.reason == "usage_beyond_bounds"
    journal = json.loads((directory(meter, "model-1") / "uncertain.json").read_bytes())
    assert journal["metered_nanodollars"] == 100 * 250 + 2100 * 2000
    settlement = settle_uncertain_call(meter, owner="alice", identity="model-1")
    assert settlement["reason"] == "usage_beyond_bounds"
    assert settlement["booked"]["provider_nanodollars"] == RESERVATION_NANO
    assert RESERVATION_NANO >= journal["metered_nanodollars"]
    with pytest.raises(ProviderCallUnresolved):
        request_model(meter, **args(transport, identity="model-2"))
    (directory(meter, "model-2") / "uncertain.json").unlink()
    with pytest.raises(SettlementRefused, match="usage_exceeds_reservation"):
        settle_uncertain_call(meter, owner="alice", identity="model-2")


def test_a_reply_without_usage_is_typed_and_reported(tmp_path):
    meter = ledger(tmp_path)
    transport, _ = script({**completed(), "usage": None})
    with pytest.raises(ProviderCallUnresolved, match="usage missing") as raised:
        request_model(meter, **args(transport))
    assert raised.value.report() == {
        "schema": ra.FAILURE_REPORT,
        "code": "provider_usage_unavailable",
        "outcome": "unknown",
        "resumable": False,
        "requires_settlement": True,
        "next_step": ra.UNRESOLVED_NEXT_STEPS["usage_unavailable"],
    }


def test_a_settlement_without_a_journal_still_names_another_model(tmp_path):
    """A call left unresolved before `uncertain.json` existed: the caveat is
    read from the retained reply."""
    meter = ledger(tmp_path)
    transport, _ = script(completed("another-model"))
    with pytest.raises(ProviderCallUnresolved, match="different provider model"):
        request_model(meter, **args(transport))
    (directory(meter, "model-1") / "uncertain.json").unlink()
    settlement = settle_uncertain_call(meter, owner="alice", identity="model-1")
    assert settlement["reason"] == "outcome_unknown"
    assert settlement["caveat"] == MODEL_CAVEAT


# -- an untrusted stop reason (LP-PROD-A review) ------------------------------


@pytest.mark.parametrize("reason", [["max_tokens"], {"why": "length"}, 7])
def test_a_stop_reason_that_is_not_a_string_is_unknown(tmp_path, reason):
    """It used to raise TypeError before the call was booked, leaving a
    metered reply unresolved."""
    reply = {
        **cut_off(),
        "incomplete_details": {"reason": reason},
    }
    assert incomplete_reply(reply, 2048)["reason"] == "unknown"
    meter = ledger(tmp_path)
    transport, _ = script(reply)
    request_model(meter, **args(transport, accept_incomplete=True))
    op = operation(meter, "model-1")
    assert op["state"] == "FAILED_INFRA"
    assert op["result"]["incomplete"]["reason"] == "unknown"
    translated = mp.chat_response(
        {
            "model": "m",
            "choices": [{"message": {"content": "x"}, "finish_reason": reason}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4},
        }
    )
    assert translated["incomplete_details"] == {"reason": "unknown"}
