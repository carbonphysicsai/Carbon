"""Model-provider selection, typed provider errors and per-attempt accounting.

Every transport here is a FIXTURE: a local function or a fake urllib opener.
No provider is contacted, no key is real, no model is inferred.
"""

import asyncio
import io
import json
import socket
import tempfile
import urllib.error
from email.message import Message
from pathlib import Path

import pytest
from test_cw1_research_ledger import ledger

from carbon.development_session import model_provider as mp
from carbon.development_session.research_agent import (
    RESERVATION_NANO,
    ProviderCallFailed,
    request_model,
)

# A fixture key file; never a real credential.
FIXTURE_KEY_FILE = str(Path(tempfile.mkdtemp()) / "fixture.key")
Path(FIXTURE_KEY_FILE).write_text("fixture-key-not-a-credential")
FIXTURE_CREDENTIAL = {"kind": "file", "reference": FIXTURE_KEY_FILE}

HISTORICAL_PROVIDER_BLOCK = {
    "model": "gpt-5-mini-2025-08-07",
    "input_per_million": 0.25,
    "cached_per_million": 0.025,
    "output_per_million": 2.0,
    "store": False,
    "data": "public synthetic and own permitted research only; standard API abuse monitoring may retain up to 30 days",
}


def request(selection=mp.DEFAULT_SELECTION):
    effort = selection.settings.reasoning_effort
    return {
        "model": selection.model_id,
        "instructions": "fixture",
        "input": [],
        "tools": [],
        "parallel_tool_calls": False,
        "store": False,
        "max_output_tokens": selection.settings.max_output_tokens,
        "reasoning": None if effort is None else {"effort": effort},
    }


def completed(model=mp.MODEL, usage=None):
    return {
        "model": model,
        "status": "completed",
        "output": [],
        "usage": usage or {"input_tokens": 100, "output_tokens": 10},
    }


def rejected(status, code=None, retry_after=None, usage_reported=False):
    return mp.ProviderHTTPError(
        status, code=code, retry_after=retry_after, usage_reported=usage_reported
    )


# -- classification --------------------------------------------------------


@pytest.mark.parametrize(
    "error, outcome, unbilled, retry_safe",
    [
        (rejected(429, "rate_limit_exceeded", "7"), "rate_limited", True, True),
        (rejected(429, None), "rate_limited", True, True),
        (rejected(429, "insufficient_quota"), "quota_exhausted", True, False),
        (rejected(401, "invalid_api_key"), "auth_credential", True, False),
        (rejected(403), "auth_credential", True, False),
        (rejected(400, "context_length_exceeded"), "context_limit", True, False),
        (rejected(400, "invalid_value"), "invalid_request", True, False),
        (rejected(422), "invalid_request", True, False),
        (rejected(500), "transient_server", False, False),
        (rejected(504), "transient_server", False, False),
        # A server that answered it could not take the request, with no usage
        # object: rejected before generation and retried (LP-PROD-A).
        (rejected(502), "server_unavailable", True, True),
        (rejected(503), "server_unavailable", True, True),
        (rejected(529), "server_unavailable", True, True),
        # One that reports usage may have generated: the reservation stays.
        (rejected(503, usage_reported=True), "transient_server", False, False),
        (mp.ProviderUnreachable("nothing sent"), "unreachable", True, True),
        (rejected(418), "unknown", False, False),
        (TimeoutError("read timed out"), "unknown", False, False),
        (ConnectionResetError(), "unknown", False, False),
        (ConnectionRefusedError(), "unknown", False, False),
        (ValueError("bad json"), "unknown", False, False),
    ],
)
def test_provider_failures_are_typed(error, outcome, unbilled, retry_safe):
    failure = mp.classify(error)
    assert failure.outcome.value == outcome
    assert failure.unbilled is unbilled
    assert failure.retry_safe is retry_safe


def test_retry_after_is_bounded_and_codes_are_sanitised():
    assert mp.classify(rejected(429, retry_after="7")).retry_after_seconds == 7
    assert mp.classify(rejected(429, retry_after="99999")).retry_after_seconds is None
    assert (
        mp.classify(
            rejected(429, retry_after="Wed, 21 Oct 2026 07:28:00 GMT")
        ).retry_after_seconds
        is None
    )
    # Provider text never survives as a code.
    assert mp.classify(rejected(400, "Bearer sk-secret text")).provider_code is None


# -- retry only where safe; accounting per attempt --------------------------


def _args(transport, **extra):
    return {
        "owner": "alice",
        "identity": "model-1",
        "request": request(),
        "credential_file": None,
        "transport": transport,
        **extra,
    }


def test_rate_limit_retries_under_new_reservations_and_replays_without_resend(
    tmp_path,
):
    meter = ledger(tmp_path)
    calls, waits = [], []
    replies = [rejected(429, "rate_limit_exceeded", "3"), rejected(429), completed()]

    def fixture(value):
        calls.append(value)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    first = request_model(
        meter, **_args(fixture, sleep=waits.append, jitter=lambda: 1.0)
    )
    assert first["status"] == "completed"
    assert len(calls) == 3
    # Retry-After is honoured; without one, exponential backoff (here at the
    # top of its jitter).
    assert waits == [3, 4]
    used = meter.status(owner="alice")["used"]
    assert used["provider_attempts"] == 3
    # The two rejections charged nothing; the success its metered usage.
    assert used["provider_nanodollars"] == 100 * 250 + 10 * 2000
    with meter.db() as db:
        rows = dict(db.execute("SELECT id,state FROM operations").fetchall())
    assert rows == {
        "model-1": "FAILED_INFRA",
        "model-1-rl1": "FAILED_INFRA",
        "model-1-rl2": "SUCCEEDED",
    }
    # Resume walks the same identities: no transport call and no second wait.
    waits.clear()
    assert request_model(meter, **_args(fixture, sleep=waits.append)) == first
    assert len(calls) == 3 and waits == []
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 3


def test_persistent_rate_limit_stops_after_bounded_retries(tmp_path):
    """LP-PROD-A changed this test: retries are now bounded by
    `MAX_AUTOMATIC_RETRIES` and a total wait, with doubling backoff up to 60 s
    (was two retries, each wait capped at 30 s), and a later call sends the
    request again instead of replaying the exhausted retries forever."""
    meter = ledger(tmp_path)
    calls = []

    def fixture(value):
        calls.append(value)
        raise rejected(429)

    waits = []
    with pytest.raises(ProviderCallFailed, match="bounded retries") as failed:
        request_model(meter, **_args(fixture, sleep=waits.append, jitter=lambda: 1.0))
    assert failed.value.outcome is mp.ProviderOutcome.RATE_LIMITED
    assert failed.value.resumable and not failed.value.requires_settlement
    assert len(calls) == 7
    assert waits == [2, 4, 8, 16, 32, 60]  # doubling, capped at 60
    used = meter.status(owner="alice")["used"]
    assert used["provider_attempts"] == 7 and used["provider_nanodollars"] == 0
    # A later call - a resume - passes the seven recorded refusals without
    # waiting and sends the request again under the next identity.
    replies = [completed()]
    waits.clear()

    def recovered(value):
        calls.append(value)
        return replies.pop(0)

    assert request_model(meter, **_args(recovered, sleep=waits.append))["status"] == (
        "completed"
    )
    assert len(calls) == 8 and waits == []
    with meter.db() as db:
        (state,) = db.execute(
            "SELECT state FROM operations WHERE id='model-1-rl7'"
        ).fetchone()
    assert state == "SUCCEEDED"


def test_a_retry_after_longer_than_the_wait_left_is_honoured_not_cut(tmp_path):
    meter = ledger(tmp_path)
    calls = []

    def fixture(value):
        calls.append(value)
        raise rejected(429, retry_after="1000")

    with pytest.raises(ProviderCallFailed, match="bounded retries"):
        request_model(meter, **_args(fixture, sleep=pytest.fail))
    # Resending before the provider's 1000 s would ignore it: one attempt.
    assert len(calls) == 1


def test_retries_stop_at_the_total_wait(tmp_path):
    meter = ledger(tmp_path)
    calls, waits = [], []

    def fixture(value):
        calls.append(value)
        raise rejected(503, retry_after="100")

    with pytest.raises(ProviderCallFailed, match="bounded retries") as failed:
        request_model(meter, **_args(fixture, sleep=waits.append, jitter=lambda: 0))
    assert failed.value.outcome is mp.ProviderOutcome.SERVER_UNAVAILABLE
    assert waits == [100, 100, 100]  # a fourth wait would pass 300 s in all
    assert len(calls) == 4
    assert meter.status(owner="alice")["used"]["provider_nanodollars"] == 0


@pytest.mark.parametrize(
    "error, outcome",
    [
        (rejected(400, "context_length_exceeded"), mp.ProviderOutcome.CONTEXT_LIMIT),
        (rejected(400), mp.ProviderOutcome.INVALID_REQUEST),
    ],
)
def test_rejections_are_counted_uncharged_and_never_retried(tmp_path, error, outcome):
    """The same request would get the same answer, so a later call replays the
    recorded rejection. LP-PROD-A moved the key and quota rejections, which
    the miner can fix, to the test below."""
    meter = ledger(tmp_path)
    calls = []

    def fixture(value):
        calls.append(value)
        raise error

    for _ in range(2):  # the second is a replay of the recorded rejection
        with pytest.raises(ProviderCallFailed, match="no retry") as failed:
            request_model(meter, **_args(fixture, sleep=pytest.fail))
        assert failed.value.outcome is outcome
        assert not failed.value.resumable
    assert len(calls) == 1
    used = meter.status(owner="alice")["used"]
    assert used["provider_attempts"] == 1
    assert used["provider_nanodollars"] == 0


@pytest.mark.parametrize(
    "error, outcome",
    [
        (rejected(401, "invalid_api_key"), mp.ProviderOutcome.AUTH_CREDENTIAL),
        (rejected(402), mp.ProviderOutcome.QUOTA_EXHAUSTED),
        (rejected(429, "insufficient_quota"), mp.ProviderOutcome.QUOTA_EXHAUSTED),
    ],
)
def test_a_key_or_balance_rejection_is_sent_again_once_the_miner_fixes_it(
    tmp_path, error, outcome
):
    """Not retried at once - the miner has to act - and not replayed forever:
    a later call (a resume) sends the request again under the next identity."""
    meter = ledger(tmp_path)
    replies = [error, error, completed()]
    calls = []

    def fixture(value):
        calls.append(value)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    for attempt in range(2):  # still refused on the first resume
        with pytest.raises(ProviderCallFailed, match="no retry") as failed:
            request_model(meter, **_args(fixture, sleep=pytest.fail))
        assert failed.value.outcome is outcome and failed.value.resumable
        assert len(calls) == attempt + 1
    report = failed.value.report()
    assert report["code"] == "provider_" + outcome.value
    assert report["resumable"] and not report["requires_settlement"]
    assert "resume" in report["next_step"]
    # The miner fixed it: the next resume goes through, under model-1-rl2.
    assert request_model(meter, **_args(fixture, sleep=pytest.fail)) == completed()
    assert len(calls) == 3
    used = meter.status(owner="alice")["used"]
    assert used["provider_attempts"] == 3
    assert used["provider_nanodollars"] == 100 * 250 + 10 * 2000
    # Replayed again, nothing is sent.
    assert request_model(meter, **_args(fixture, sleep=pytest.fail)) == completed()
    assert len(calls) == 3


@pytest.mark.parametrize(
    "error",
    [
        rejected(500),
        rejected(504),
        rejected(503, usage_reported=True),
        TimeoutError("timed out"),
    ],
)
def test_possibly_processed_failures_keep_the_reservation_and_never_resend(
    tmp_path, error
):
    meter = ledger(tmp_path)
    calls = []

    def fixture(value):
        calls.append(value)
        raise error

    with pytest.raises(ProviderCallFailed, match="full reservation") as failed:
        request_model(meter, **_args(fixture, sleep=pytest.fail))
    assert failed.value.outcome in (
        mp.ProviderOutcome.TRANSIENT_SERVER,
        mp.ProviderOutcome.UNKNOWN,
    )
    assert failed.value.requires_settlement and not failed.value.resumable
    assert "Reconcile" in failed.value.report()["next_step"]
    with pytest.raises(ValueError, match="no resend"):
        request_model(meter, **_args(fixture, sleep=pytest.fail))
    assert len(calls) == 1
    used = meter.status(owner="alice")["used"]
    assert used["provider_nanodollars"] == RESERVATION_NANO


def test_unknown_price_reserves_no_money_and_records_tokens(tmp_path):
    meter = ledger(tmp_path)
    selection = mp.select(
        provider_id="openai-responses",
        model_id="gpt-4.1",
        credential=FIXTURE_CREDENTIAL,
        settings={"reasoning_effort": None},
    )
    assert selection.reservation_nano is None
    response = request_model(
        meter,
        **_args(
            lambda value: completed("gpt-4.1-2025-04-14"),
            request=request(selection),
            provider=selection,
        ),
    )
    assert response["model"] == "gpt-4.1-2025-04-14"
    used = meter.status(owner="alice")["used"]
    assert used["provider_attempts"] == 1
    assert used["provider_nanodollars"] == 0  # none reserved, none metered
    with meter.db() as db:
        (result,) = db.execute("SELECT result FROM operations").fetchone()
    result = json.loads(result)
    assert result["usage"]["nanodollars"] is None
    assert result["provider_model"] == "gpt-4.1-2025-04-14"
    # The pinned model must still come back exactly.
    with pytest.raises(ValueError, match="different provider model"):
        request_model(
            ledger(tmp_path / "pinned"),
            **_args(lambda value: completed("gpt-5-mini-2025-08-07-other")),
        )


def test_declared_price_reserves_the_maximum_before_dispatch(tmp_path):
    selection = mp.select(
        provider_id="openai-compatible-chat",
        model_id="fixture-model",
        endpoint="https://llm.example.invalid/v1/chat/completions",
        credential=FIXTURE_CREDENTIAL,
        declared_pricing={
            "input_nano": 100,
            "cached_input_nano": 10,
            "output_nano": 400,
            "observed": "2026-09-26",
            "note": "fixture price",
        },
    )
    assert selection.reservation_nano == 65536 * 100 + 2048 * 400
    meter = ledger(tmp_path)
    seen = []

    def fixture(value):
        seen.append(meter.status(owner="alice")["used"]["provider_nanodollars"])
        return completed("fixture-model")

    request_model(
        meter, **_args(fixture, request=request(selection), provider=selection)
    )
    assert seen == [selection.reservation_nano]  # reserved before dispatch
    assert (
        meter.status(owner="alice")["used"]["provider_nanodollars"]
        == 100 * 100 + 10 * 400
    )


# -- selection --------------------------------------------------------------


def test_pinned_selection_keeps_every_existing_manifest_verifying():
    assert mp.DEFAULT_SELECTION.manifest_record() == HISTORICAL_PROVIDER_BLOCK
    assert mp.DEFAULT_SELECTION.reservation_nano == RESERVATION_NANO
    resolved = mp.selection_from_record(HISTORICAL_PROVIDER_BLOCK)
    assert resolved.is_historical_default
    with pytest.raises(mp.ModelSelectionRefused, match="differs"):
        mp.selection_from_record({**HISTORICAL_PROVIDER_BLOCK, "model": "gpt-5"})


def test_a_new_selection_round_trips_through_its_record_without_the_key():
    selection = mp.select(
        provider_id="openai-compatible-responses",
        model_id="fixture/model@1",
        endpoint="https://llm.example.invalid/v1/responses",
        credential={"kind": "file", "reference": "/private/key-file"},
        settings={"max_output_tokens": 4096, "reasoning_effort": "medium"},
    )
    record = selection.manifest_record()
    assert record["schema"] == mp.SELECTION_SCHEMA
    assert record["pricing"] is None and record["spend_bound"] == mp.UNKNOWN_SPEND
    assert "/private/key-file" not in json.dumps(record)
    with pytest.raises(mp.ModelSelectionRefused, match="supplied again"):
        mp.selection_from_record(record)
    again = mp.selection_from_record(record, credential_file="/private/key-file")
    assert again.record() == record


@pytest.mark.parametrize(
    "spec, message",
    [
        ({"provider_id": "anthropic-imaginary"}, "unknown provider adapter"),
        ({"model_id": ""}, "model id"),
        ({"endpoint": "https://elsewhere.invalid/v1"}, "fixed"),
        ({"settings": {"temperature": 1}}, "unknown model setting"),
        ({"settings": {"max_output_tokens": 10**9}}, "max_output_tokens"),
        ({"credential": {"kind": "inline", "reference": "sk-x"}}, "key file path"),
        (
            {
                "declared_pricing": {
                    "input_nano": 1,
                    "cached_input_nano": 1,
                    "output_nano": 1,
                    "observed": "2026-09-26",
                    "note": "cheaper",
                }
            },
            "listed",
        ),
    ],
)
def test_invalid_selections_are_refused(spec, message):
    base = {
        "provider_id": "openai-responses",
        "model_id": mp.MODEL,
        "credential": FIXTURE_CREDENTIAL,
    }
    with pytest.raises(mp.ModelSelectionRefused, match=message):
        mp.select(**{**base, **spec})


def test_compatible_adapters_need_an_https_endpoint():
    for endpoint in (None, "http://plain.invalid/v1", "https://x.invalid/v1?k=1"):
        with pytest.raises(mp.ModelSelectionRefused, match="https endpoint"):
            mp.select(
                provider_id="openai-compatible-chat",
                model_id="m",
                endpoint=endpoint,
                credential=FIXTURE_CREDENTIAL,
            )


def test_a_selection_cannot_be_built_around_validation():
    with pytest.raises(mp.ModelSelectionRefused, match="select"):
        mp.ModelSelection(
            mp.ADAPTERS["openai-responses"],
            mp.MODEL,
            "https://api.openai.com/v1/responses",
            mp.DEFAULT_SETTINGS,
            mp.GPT5_MINI_PRICING,
            mp.CredentialReference("file", FIXTURE_KEY_FILE),
        )
    import dataclasses

    with pytest.raises(mp.ModelSelectionRefused, match="select"):
        dataclasses.replace(mp.DEFAULT_SELECTION, model_id="gpt-unvalidated")
    with pytest.raises(mp.ModelSelectionRefused, match="validated"):
        mp.SelectionTransport(object())


def test_a_money_limit_needs_a_price():
    unpriced = mp.select(
        provider_id="openai-responses",
        model_id="gpt-4.1",
        credential=FIXTURE_CREDENTIAL,
    )
    with pytest.raises(mp.ModelSelectionRefused, match="spend limit"):
        mp.check_budget(unpriced, {"provider_nanodollars": 10**9})
    mp.check_budget(unpriced, {"provider_attempts": 5})
    mp.check_budget(unpriced, None)
    mp.check_budget(mp.DEFAULT_SELECTION, {"provider_nanodollars": 10**9})


# -- summary ----------------------------------------------------------------


def test_summary_lists_every_adapter_and_offers_none_without_a_credential():
    rows = {row["provider_id"]: row for row in mp.provider_summary()}
    assert set(rows) == {
        "openai-responses",
        "engy-anthropic",
        "engy-chat",
        "chutes",
        "anthropic",
        "openai-compatible-responses",
        "openai-compatible-chat",
    }
    assert all(not row["available"] for row in rows.values())
    assert {row["reason"] for row in rows.values()} == {"credential_not_configured"}
    listed = rows["openai-responses"]["models"]
    assert [m["model_id"] for m in listed] == [mp.MODEL]
    assert listed[0]["pricing"]["observed"] == "2026-09-17"
    # No price is invented for a service Carbon has none for.
    assert rows["anthropic"]["models"] == []
    assert rows["openai-compatible-chat"]["endpoint_required"] is True
    assert rows["engy-anthropic"]["charge_settled_from"] == "x_engy.charged_micro"


def test_summary_availability_reads_metadata_never_the_key(tmp_path, monkeypatch):
    key = tmp_path / "key"
    key.write_text("fixture-not-a-key\n")
    oversized = tmp_path / "big"
    oversized.write_text("x" * 2000)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("the credential was read")

    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    rows = {
        row["provider_id"]: row
        for row in mp.provider_summary(
            {"engy-anthropic": str(key), "anthropic": str(oversized)}
        )
    }
    assert rows["engy-anthropic"]["available"] is True
    assert rows["openai-responses"]["available"] is False
    assert rows["anthropic"]["reason"] == "credential_file_unusable"
    assert "fixture-not-a-key" not in json.dumps(rows)
    # Specimen: the same patch does catch a function that reads the key.
    with pytest.raises(AssertionError, match="was read"):
        mp.read_credential(mp.CredentialReference("file", str(key)))


def test_an_environment_variable_is_not_a_credential():
    with pytest.raises(mp.ModelSelectionRefused, match="key file path"):
        mp.select(
            provider_id="engy-anthropic",
            credential={"kind": "env", "reference": "ENGY_KEY"},
        )


# -- transports (fixture openers) --------------------------------------------


class Opener:
    def __init__(self, reply):
        self.reply, self.sent = reply, []

    def open(self, outgoing, timeout):
        self.sent.append((outgoing, timeout))
        if isinstance(self.reply, Exception):
            raise self.reply
        return io.BytesIO(json.dumps(self.reply).encode())


def test_chat_adapter_translates_history_and_reply():
    selection = mp.select(
        provider_id="openai-compatible-chat",
        model_id="fixture-model",
        endpoint="https://llm.example.invalid/v1/chat/completions",
        credential=FIXTURE_CREDENTIAL,
    )
    opener = Opener(
        {
            "model": "fixture-model",
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c2",
                                "type": "function",
                                "function": {"name": "t", "arguments": "{}"},
                            }
                        ],
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 5,
                "prompt_tokens_details": {"cached_tokens": 10},
            },
        }
    )
    transport = mp.SelectionTransport(selection, opener=opener)
    value = {
        **request(selection),
        "input": [
            {"role": "user", "content": "observe"},
            {"type": "reasoning", "summary": []},
            {
                "type": "function_call",
                "call_id": "c1",
                "name": "t",
                "arguments": "{}",
            },
            {"type": "function_call_output", "call_id": "c1", "output": "{}"},
        ],
        "tools": [{"type": "function", "name": "t", "strict": True, "parameters": {}}],
    }
    reply = transport(value)
    ((outgoing, timeout),) = opener.sent
    body = json.loads(outgoing.data)
    assert outgoing.full_url == selection.endpoint and timeout == 120
    assert [m["role"] for m in body["messages"]] == [
        "system",
        "user",
        "assistant",
        "tool",
    ]
    assert body["tools"][0] == {
        "type": "function",
        "function": {"name": "t", "strict": True, "parameters": {}},
    }
    assert "reasoning" not in body and "store" not in body
    assert body["max_tokens"] == 2048
    assert reply["status"] == "completed"
    assert reply["output"] == [
        {"type": "function_call", "call_id": "c2", "name": "t", "arguments": "{}"}
    ]
    assert reply["usage"] == {
        "input_tokens": 50,
        "output_tokens": 5,
        "input_tokens_details": {"cached_tokens": 10},
    }


def test_a_request_states_its_parallel_rule_as_a_boolean(tmp_path):
    """False under the historical and v1 rules, True under v2 (LP-PROD-A);
    anything else is refused before a reservation."""
    meter = ledger(tmp_path)
    sent = []

    def fixture(value):
        sent.append(value)
        return completed()

    allowed = {**request(), "parallel_tool_calls": True}
    request_model(meter, **{**_args(fixture), "request": allowed})
    assert sent[0]["parallel_tool_calls"] is True
    for value in ("true", 1, None):
        with pytest.raises(ValueError, match="bounded request required"):
            request_model(
                meter,
                **{
                    **_args(fixture),
                    "identity": "model-2",
                    "request": {**request(), "parallel_tool_calls": value},
                },
            )
    assert len(sent) == 1
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 1


def test_chat_adapter_sends_one_turns_calls_as_one_assistant_message():
    """A v2 turn (LP-PROD-A) carries several calls, and any text before them;
    Chat Completions needs them on one assistant message ahead of the tool
    replies. The request allows parallel calls, as the rule froze it."""
    value = {
        **request(),
        "parallel_tool_calls": True,
        "input": [
            {"role": "user", "content": "observe"},
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Two reads."}],
            },
            {"type": "function_call", "call_id": "c1", "name": "t", "arguments": "{}"},
            {"type": "function_call", "call_id": "c2", "name": "t", "arguments": "{}"},
            {"type": "function_call_output", "call_id": "c1", "output": "{}"},
            {"type": "function_call_output", "call_id": "c2", "output": "{}"},
            {"role": "user", "content": "status"},
            {"type": "function_call", "call_id": "c3", "name": "t", "arguments": "{}"},
        ],
    }
    body = mp.chat_request(value)
    assert [m["role"] for m in body["messages"]] == [
        "system",
        "user",
        "assistant",
        "tool",
        "tool",
        "user",
        "assistant",
    ]
    turn = body["messages"][2]
    assert turn["content"] == "Two reads."
    assert [c["id"] for c in turn["tool_calls"]] == ["c1", "c2"]
    assert [c["id"] for c in body["messages"][6]["tool_calls"]] == ["c3"]
    assert body["parallel_tool_calls"] is True


@pytest.mark.parametrize(
    "arguments",
    [
        None,
        "",
        "  ",
        # LP-PROD-A, part 2: arguments that are not one JSON object - cut off
        # by the output limit, malformed, another JSON value, NaN - are sent
        # as {} too, so a chat endpoint that parses its history cannot refuse
        # the request on the model's own mistake.
        '{"code": "print(1)\\nfor i in',
        "{not json",
        "[1, 2]",
        '{"a": NaN}',
        12,
    ],
)
def test_chat_adapter_sends_an_empty_call_as_an_empty_object(arguments):
    """The loop reads an empty call as {} (`research_loop.tool_arguments`)
    and answers a malformed one with a typed result; the chat history sends
    each as {}, so an endpoint never sees a tool call whose arguments are not
    one JSON object."""
    value = {
        **request(),
        "input": [
            {"role": "user", "content": "observe"},
            {
                "type": "function_call",
                "call_id": "c1",
                "name": "t",
                "arguments": arguments,
            },
            {"type": "function_call_output", "call_id": "c1", "output": "{}"},
        ],
    }
    (call,) = mp.chat_request(value)["messages"][2]["tool_calls"]
    assert call["function"]["arguments"] == "{}"
    # One JSON object is carried back exactly as the model sent it.
    value["input"][1]["arguments"] = '{"a":1,  "b": [2]}'
    (call,) = mp.chat_request(value)["messages"][2]["tool_calls"]
    assert call["function"]["arguments"] == '{"a":1,  "b": [2]}'


def test_responses_adapter_omits_a_null_reasoning_setting():
    selection = mp.select(
        provider_id="openai-responses",
        model_id="gpt-4.1",
        credential=FIXTURE_CREDENTIAL,
        settings={"reasoning_effort": None},
    )
    opener = Opener(completed("gpt-4.1"))
    mp.SelectionTransport(selection, opener=opener)(request(selection))
    body = json.loads(opener.sent[0][0].data)
    assert "reasoning" not in body and body["model"] == "gpt-4.1"


def test_an_http_rejection_keeps_status_code_and_retry_after_only():
    headers = Message()
    headers["Retry-After"] = "5"
    secret = b'{"error": {"code": "rate_limit_exceeded", "message": "key sk-FIXTURE"}}'
    opener = Opener(
        urllib.error.HTTPError(
            "https://x.invalid", 429, "Too Many", headers, io.BytesIO(secret)
        )
    )
    transport = mp.SelectionTransport(
        mp.select(
            provider_id="openai-responses",
            model_id=mp.MODEL,
            credential=FIXTURE_CREDENTIAL,
        ),
        opener=opener,
    )
    with pytest.raises(mp.ProviderHTTPError) as raised:
        transport(request())
    error = raised.value
    assert (error.status, error.code, error.retry_after) == (
        429,
        "rate_limit_exceeded",
        "5",
    )
    assert "sk-FIXTURE" not in str(error) and error.__cause__ is None
    assert mp.classify(error).outcome is mp.ProviderOutcome.RATE_LIMITED


def _transport(opener):
    return mp.SelectionTransport(
        mp.select(
            provider_id="openai-responses",
            model_id=mp.MODEL,
            credential=FIXTURE_CREDENTIAL,
        ),
        opener=opener,
    )


@pytest.mark.parametrize(
    "body, reported, outcome",
    [
        (b'{"error": {"code": "server_error"}}', False, "server_unavailable"),
        (b"<html>Bad gateway</html>", False, "server_unavailable"),
        (
            b'{"error": {"code": "server_error"}, "usage": {"output_tokens": 9}}',
            True,
            "transient_server",
        ),
        # A provider's own charge report (Engy) with no usage: may have been
        # billed, so it is not booked at zero (LP-PROD-A review).
        (
            b'{"error": {"code": "server_error"}, "x_engy": {"charged_micro": 5}}',
            True,
            "transient_server",
        ),
    ],
)
def test_an_unavailable_server_is_read_from_its_status_and_body(
    body, reported, outcome
):
    opener = Opener(
        urllib.error.HTTPError("https://x.invalid", 503, "Busy", None, io.BytesIO(body))
    )
    with pytest.raises(mp.ProviderHTTPError) as raised:
        _transport(opener)(request())
    assert raised.value.usage_reported is reported
    assert mp.classify(raised.value).outcome.value == outcome


@pytest.mark.parametrize(
    "reason", [ConnectionRefusedError(111, "refused"), socket.gaierror(-2, "unknown")]
)
def test_a_connection_refused_before_sending_is_typed_unreachable(reason):
    """Raised from the connect, before any request byte: nothing was sent.
    No network or provider text survives."""
    opener = Opener(urllib.error.URLError(reason))
    with pytest.raises(mp.ProviderUnreachable) as raised:
        _transport(opener)(request())
    assert isinstance(raised.value, OSError) and raised.value.__cause__ is None
    failure = mp.classify(raised.value)
    assert failure.outcome is mp.ProviderOutcome.UNREACHABLE
    assert failure.unbilled and failure.retry_safe
    assert "refused" not in str(raised.value) and "unknown" not in str(raised.value)


def test_any_other_connection_failure_stays_unknown():
    """A reset or a timeout can come after the request was sent."""
    opener = Opener(urllib.error.URLError(ConnectionResetError()))
    with pytest.raises(urllib.error.URLError) as raised:
        _transport(opener)(request())
    assert mp.classify(raised.value).outcome is mp.ProviderOutcome.UNKNOWN


def _chat(finish_reason):
    return {
        "model": "m",
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": "partial"},
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 7},
    }


@pytest.mark.parametrize(
    "finish_reason, reason",
    [
        ("length", "max_output_tokens"),
        ("content_filter", "content_filter"),
        (None, "unknown"),
        ("Odd Reason!", "unknown"),
    ],
)
def test_an_unfinished_chat_reply_says_how_it_ended(finish_reason, reason):
    reply = mp.chat_response(_chat(finish_reason))
    assert reply["status"] == "incomplete"
    assert reply["incomplete_details"] == {"reason": reason}


def test_a_finished_chat_reply_carries_no_incomplete_details():
    for finish_reason in ("stop", "tool_calls"):
        reply = mp.chat_response(_chat(finish_reason))
        assert reply["status"] == "completed" and "incomplete_details" not in reply


def test_run_epoch_uses_the_campaign_selection(tmp_path):
    from carbon.development_session.research_loop import run_epoch

    selection = mp.select(
        provider_id="openai-responses",
        model_id="gpt-4.1",
        credential=FIXTURE_CREDENTIAL,
        settings={"reasoning_effort": None, "max_output_tokens": 1024},
    )
    sent = []

    def fixture(value):
        sent.append(value)
        return {
            **completed("gpt-4.1"),
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "stop"}],
                }
            ],
        }

    meter = ledger(tmp_path)
    outcome = asyncio.run(
        run_epoch(
            meter,
            owner="alice",
            epoch=1,
            sdk=None,
            credential_file=None,
            initial_observation={"fixture": True},
            transport=fixture,
            provider=selection,
        )
    )
    assert outcome["status"] == "STOPPED"
    assert sent[0]["model"] == "gpt-4.1" and sent[0]["reasoning"] is None
    assert sent[0]["max_output_tokens"] == 1024
    plan = json.loads((tmp_path / "epoch-1" / "plan.json").read_bytes())
    assert plan["model"] == "gpt-4.1"
    assert plan["model_selection"] == selection.record()
