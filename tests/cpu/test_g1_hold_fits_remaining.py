"""G1 (Validator, 2026-10-23): a model call's hold fits the money the miner's
own cap still admits (`research_agent.REQUEST_HOLD_FIT_V1`).

Synthetic transport accounting only; these are not agent inference."""

import pytest
from test_cw1_research_ledger import ledger

from carbon.development_session.agent import MAX_OUTPUT_TOKENS, MODEL
from carbon.development_session.model_provider import DEFAULT_SELECTION
from carbon.development_session.profile import canonical
from carbon.development_session.research_agent import (
    CONTEXT_RESERVE_TOKENS,
    FIT_MIN_OUTPUT_TOKENS,
    REQUEST_HOLD_FIT_V1,
    RESERVATION_NANO,
    ProviderCallUnresolved,
    request_model,
)
from carbon.development_session.research_ledger import (
    DEVELOPMENT_CEILINGS,
    LedgerRefusal,
)

PRICING = DEFAULT_SELECTION.pricing


def request():
    return {
        "model": MODEL,
        "instructions": "plan",
        "input": [{"role": "user", "content": "x" * 200}],
        "tools": [],
        "parallel_tool_calls": False,
        "store": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "reasoning": {"effort": "low"},
    }


def capped(tmp_path, nanodollars):
    return ledger(
        tmp_path, ceilings={**DEVELOPMENT_CEILINGS, "provider_nanodollars": nanodollars}
    )


def reply(sent, output_tokens=200, input_tokens=100, status="completed"):
    sent.append(None)
    return {
        "model": MODEL,
        "status": status,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "output": [],
        **(
            {}
            if status == "completed"
            else {"incomplete_details": {"reason": "max_output_tokens"}}
        ),
    }


def held(budget):
    return [
        op["reservation"].get("provider_nanodollars")
        for op in budget.status(owner="alice")["operations"]
    ]


def call(budget, identity, transport, **extra):
    return request_model(
        budget,
        owner="alice",
        identity=identity,
        request=request(),
        credential_file=None,
        transport=transport,
        hold=REQUEST_HOLD_FIT_V1,
        **extra,
    )


def bound_input_nano():
    tokens = len(canonical(request())) + CONTEXT_RESERVE_TOKENS
    return tokens * PRICING.input_nano


def test_with_room_the_hold_and_request_are_v1s(tmp_path):
    budget = capped(tmp_path, 100 * RESERVATION_NANO)
    sent = []
    call(budget, "m-1", lambda r: (sent.append(r), reply([]))[1])
    assert held(budget) == [RESERVATION_NANO]
    assert sent[0]["max_output_tokens"] == MAX_OUTPUT_TOKENS


def test_a_hold_that_does_not_fit_is_clamped_to_the_money_left(tmp_path):
    room = bound_input_nano() + 2000 * PRICING.output_nano
    assert room < RESERVATION_NANO
    budget = capped(tmp_path, room)
    sent = []
    call(budget, "m-1", lambda r: (sent.append(r), reply([]))[1])
    clamped = sent[0]["max_output_tokens"]
    assert FIT_MIN_OUTPUT_TOKENS <= clamped < MAX_OUTPUT_TOKENS
    # The provider is asked for no more output than the hold pays for, and the
    # hold never exceeds what the cap admitted.
    assert held(budget) == [bound_input_nano() + clamped * PRICING.output_nano]
    assert held(budget)[0] <= room


def test_a_call_that_cannot_fit_the_minimum_reply_stops_before_reserving(tmp_path):
    room = bound_input_nano() + (FIT_MIN_OUTPUT_TOKENS - 1) * PRICING.output_nano
    budget = capped(tmp_path, room)
    sent = []
    with pytest.raises(LedgerRefusal, match="miner budget: provider_nanodollars"):
        call(budget, "m-1", lambda r: (sent.append(r), reply([]))[1])
    assert sent == [] and budget.status(owner="alice")["operations"] == []


def test_a_small_cap_buys_most_of_its_calls(tmp_path):
    # A cap that the whole V1 reservation would exhaust at the first call
    # (G1: $0.25 stopped after 2 calls) keeps calling until less than one
    # minimal call is left.
    per_call = 100 * PRICING.input_nano + 200 * PRICING.output_nano
    cap = RESERVATION_NANO // 2
    budget = capped(tmp_path, cap)
    made = 0
    while True:
        try:
            call(budget, f"m-{made}", lambda r: reply([]))
        except LedgerRefusal:
            break
        made += 1
        assert made < 10_000
    used = budget.status(owner="alice")["used"]["provider_nanodollars"]
    assert used == made * per_call
    left = cap - used
    assert left < bound_input_nano() + FIT_MIN_OUTPUT_TOKENS * PRICING.output_nano
    assert made > 2


def test_billed_input_over_the_bound_is_typed_and_recorded_never_silent(tmp_path):
    room = bound_input_nano() + 2000 * PRICING.output_nano
    budget = capped(tmp_path, room)
    huge = room // PRICING.input_nano + 1
    with pytest.raises(ProviderCallUnresolved) as raised:
        call(budget, "m-1", lambda r: reply([], input_tokens=huge))
    assert raised.value.reason in (
        "charge_exceeds_reservation",
        "usage_exceeds_reservation",
    )
    (op,) = budget.status(owner="alice")["operations"]
    assert op["state"] != "SUCCEEDED"


def test_a_length_truncated_clamped_reply_is_metered_once(tmp_path):
    room = bound_input_nano() + 2000 * PRICING.output_nano
    budget = capped(tmp_path, room)
    sent = []

    def cut(r):
        sent.append(r)
        return reply([], output_tokens=r["max_output_tokens"], status="incomplete")

    response = call(budget, "m-1", cut, accept_incomplete=True)
    assert response["status"] == "incomplete"
    charge = (
        100 * PRICING.input_nano + sent[0]["max_output_tokens"] * PRICING.output_nano
    )
    assert budget.status(owner="alice")["used"]["provider_nanodollars"] == charge
    # Replayed, it neither resends nor charges again.
    again = call(budget, "m-1", cut, accept_incomplete=True)
    assert again == response and len(sent) == 1
    assert budget.status(owner="alice")["used"]["provider_nanodollars"] == charge


def test_a_recorded_call_replays_its_own_clamped_request(tmp_path):
    room = bound_input_nano() + 2000 * PRICING.output_nano
    budget = capped(tmp_path, room)
    sent = []
    first = call(budget, "m-1", lambda r: (sent.append(r), reply([]))[1])
    # The room has changed since; the replay must not re-clamp (that would
    # be a replay conflict), and must not send again.
    assert call(budget, "m-1", lambda r: (sent.append(r), reply([]))[1]) == first
    assert len(sent) == 1
