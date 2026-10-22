"""S17: a new plan's provider calls stream, so a long reply is never cut.

M1 rehearsal 2026-10-21: a Chutes reasoning reply with a 65,536-token cap ran
past the 600 s call deadline while still being written, and the call ended
as an unknown outcome. Under `TRANSPORT_STREAM_V1`, frozen by new plans only:
- an adapter that streams (Chutes, any OpenAI-compatible chat service) sends
  `stream: true` with `stream_options.include_usage`, and `timeout_seconds`
  is the longest wait between chunks: a reply that keeps sending is never
  cut, and only the miner's own elapsed limit bounds it;
- the reply is assembled from its chunks, tool-call deltas included, into
  the very response the non-streaming path returns, and the final usage
  chunk meters it exactly; with no usage chunk the call is booked at its
  full reservation, for that recorded reason, and nothing is guessed;
- a stream cut before its end, idle past the timeout or carrying a malformed
  chunk is `transport_outcome_unknown`: kept at its reservation, never
  resent, settled by Reconcile;
- a plan frozen before replays non-streaming byte for byte, and an adapter
  that does not stream keeps the whole-reply deadline;
- the campaign view shows the observed speed only after a completed call,
  and warns only a non-streaming plan whose full reply would outlast its
  timeout at that observed speed.

Every provider here is a FIXTURE: a scripted opener or a local HTTPS server
on 127.0.0.1 with a throwaway certificate. No provider is contacted and no
key is real.
"""

from __future__ import annotations

import datetime
import io
import ipaddress
import json
import socket
import ssl
import threading
import time
from email.message import Message
from types import SimpleNamespace

import pytest
from test_cw1_research_ledger import ledger

from carbon.development_session import model_provider as mp
from carbon.development_session import research_campaign as campaigns
from carbon.development_session.profile import canonical
from carbon.development_session.research_agent import (
    UNCERTAIN_CALL,
    ProviderCallFailed,
    ProviderCallUnresolved,
    _call_directory,
    request_model,
)
from scripts.dev.miner_launchpad import campaign_view, capabilities, projection

#: A streamed call's wait for each chunk here (`idle_seconds`, tests only):
#: far below the selection's own validated minimum timeout of 10 s.
IDLE = 0.3
PRICE = {
    "input_nano": 100,
    "cached_input_nano": 10,
    "output_nano": 400,
    "observed": "2026-10-21",
    "note": "test fixture price",
}


@pytest.fixture
def key_file(tmp_path):
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    path = folder / "provider.key"
    path.write_text("fixture-not-a-key")
    return path


def chosen(
    key_file,
    *,
    provider_id="openai-compatible-chat",
    transport=mp.TRANSPORT_STREAM_V1,
    endpoint="https://llm.example.invalid/v1/chat/completions",
    **settings,
):
    adapter = mp.ADAPTERS[provider_id]
    return mp.select(
        provider_id=provider_id,
        model_id=None if adapter.allowed_models else "fixture-model",
        endpoint=None if adapter.endpoint else endpoint,
        credential={"kind": "file", "reference": str(key_file)},
        settings={"reasoning_effort": None, "max_output_tokens": 2048, **settings},
        declared_pricing=None if adapter.priced_models else PRICE,
        transport=transport,
    )


def request(selection, history=()):
    return {
        "model": selection.model_id,
        "instructions": "fixture",
        "input": [{"role": "user", "content": "observe"}, *history],
        "tools": [],
        "parallel_tool_calls": False,
        "store": False,
        "max_output_tokens": selection.settings.max_output_tokens,
        "reasoning": None,
    }


def chunk(delta=None, finish=None, **extra):
    choices = (
        []
        if delta is None and finish is None
        else [{"index": 0, "delta": delta or {}, "finish_reason": finish}]
    )
    return {
        "id": "chatcmpl-fixture",
        "object": "chat.completion.chunk",
        "model": "fixture-model",
        "choices": choices,
        "usage": None,
        **extra,
    }


USAGE = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}


def sse(*events):
    """Server-sent event lines: each event a chunk object, raw bytes, or a
    `("sleep", seconds)` pause before the next."""
    for event in events:
        if type(event) is tuple or type(event) is bytes:
            yield event
        elif event == "[DONE]":
            yield b"data: [DONE]\n\n"
        else:
            yield b"data: " + json.dumps(event).encode() + b"\n\n"


def reply(text="ok", usage=USAGE, done=True):
    events = [
        chunk({"role": "assistant", "content": ""}),
        *[chunk({"content": piece}) for piece in text],
        chunk(finish="stop"),
    ]
    if usage is not None:
        events.append(chunk(usage=usage))
    if done:
        events.append("[DONE]")
    return events


class Stream(io.RawIOBase):
    """A scripted streamed body: `readline` returns each SSE line in turn,
    sleeping where the script pauses."""

    def __init__(self, events, content_type="text/event-stream"):
        self.lines = []
        for event in sse(*events):
            if type(event) is tuple:
                self.lines.append(event)
            else:
                self.lines.extend(event.splitlines(keepends=True))
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def readline(self, limit=-1):
        while self.lines:
            line = self.lines.pop(0)
            if type(line) is tuple:
                time.sleep(line[1])
                continue
            return line
        return b""

    def read(self, limit=-1):
        return b"".join(line for line in self.lines if type(line) is bytes)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Opener:
    def __init__(self, *bodies):
        self.bodies, self.sent = list(bodies), []

    def open(self, outgoing, timeout):
        self.sent.append(json.loads(outgoing.data))
        body = self.bodies.pop(0)
        return body if not isinstance(body, list) else Stream(body)


def call(meter, selection, transport, identity="model-1"):
    return request_model(
        meter,
        owner="alice",
        identity=identity,
        request=request(selection),
        credential_file=None,
        provider=selection,
        transport=transport,
        sleep=pytest.fail,
        accept_incomplete=True,
    )


def uncertain(meter, identity="model-1"):
    path = _call_directory(meter, "alice", identity) / "uncertain.json"
    record = json.loads(path.read_bytes())
    assert record["schema"] == UNCERTAIN_CALL
    return record


def held(meter, selection):
    (op,) = meter.status(owner="alice")["operations"]
    assert op["state"] == "RESERVED" and op["actual"] is None
    assert op["reservation"]["provider_nanodollars"] == selection.reservation_nano
    return op


# -- the rule ----------------------------------------------------------------


def test_the_rule_is_recorded_and_streams_only_where_the_adapter_does(key_file):
    assert mp.TRANSPORT_STREAM_V1 == "carbon.model-selection.transport.stream.v1"
    assert mp.TRANSPORTS == (None, mp.TRANSPORT_STREAM_V1)
    streaming = sorted(a.adapter_id for a in mp.ADAPTERS.values() if a.streaming)
    assert streaming == ["chutes", "openai-compatible-chat"]
    selection = chosen(key_file)
    assert selection.streams
    assert selection.record()["transport"] == mp.TRANSPORT_STREAM_V1
    assert mp.record_streams(selection.record())
    again = mp.selection_from_record(selection.record(), credential_file=key_file)
    assert again.record() == selection.record() and again.streams
    # Built without it, the record is exactly the historical one.
    whole = chosen(key_file, transport=None)
    assert "transport" not in whole.record() and not whole.streams
    assert {k: v for k, v in selection.record().items() if k != "transport"} == (
        whole.record()
    )
    assert mp.DEFAULT_SELECTION.transport is None
    with pytest.raises(mp.ModelSelectionRefused, match="unknown transport rule"):
        chosen(key_file, transport="carbon.model-selection.transport.stream.v0")
    with pytest.raises(mp.ModelSelectionRefused):
        mp.selection_from_record(
            {**selection.record(), "transport": "elsewhere"}, credential_file=key_file
        )
    # Recorded for any adapter, it streams only where the adapter streams.
    for provider_id in ("engy-chat", "openai-responses", "anthropic", "engy-anthropic"):
        other = chosen(key_file, provider_id=provider_id)
        assert other.record()["transport"] == mp.TRANSPORT_STREAM_V1
        assert not other.streams and not mp.record_streams(other.record())


def test_only_a_new_product_plan_freezes_it():
    product = SimpleNamespace(
        product=SimpleNamespace(budget={}),
        model_selection={"provider_id": "chutes", "model_id": "fixture/model"},
        api_key_file="/nonexistent/fixture.key",
    )
    granted = SimpleNamespace(**{**vars(product), "product": None})
    assert campaigns.new_plan_transport(product) == mp.TRANSPORT_STREAM_V1
    assert campaigns.new_plan_transport(granted) is None
    plan = campaigns.supplied_selection(
        product, transport=campaigns.new_plan_transport(product)
    )
    assert plan.streams and plan.record()["transport"] == mp.TRANSPORT_STREAM_V1
    # A resume naming the same choice resolves the frozen plan under either
    # rule, and a plan frozen before keeps its whole calls.
    assert campaigns.resolve_selection(product, plan.record()).streams
    before = campaigns.supplied_selection(product)
    assert not campaigns.resolve_selection(product, before.record()).streams


def test_an_old_plan_replays_non_streaming_byte_for_byte(key_file):
    selection = chosen(key_file, transport=None)
    whole = {
        "id": "chatcmpl-fixture",
        "model": "fixture-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "ok"},
                "finish_reason": "stop",
            }
        ],
        "usage": USAGE,
    }
    sent = []

    class Whole:
        def open(self, outgoing, timeout):
            sent.append(outgoing.data)
            assert timeout == selection.settings.timeout_seconds
            return io.BytesIO(json.dumps(whole).encode())

    response = mp.SelectionTransport(selection, opener=Whole())(request(selection))
    assert sent == [canonical(mp.chat_request(request(selection)))]
    assert b"stream" not in sent[0]
    assert response == mp.chat_response(whole)
    assert "provider_stream" not in response


def test_a_non_streaming_adapter_keeps_the_whole_reply_deadline(key_file):
    selection = chosen(key_file, provider_id="engy-chat")
    assert selection.record()["transport"] == mp.TRANSPORT_STREAM_V1

    class Slow:
        def open(self, outgoing, timeout):
            assert b"stream" not in outgoing.data
            time.sleep(1.5)
            return io.BytesIO(b"{}")

    transport = mp.SelectionTransport(selection, opener=Slow(), deadline_seconds=0.3)
    began = time.monotonic()
    with pytest.raises(mp.ProviderDeadlineExceeded):
        transport(request(selection))
    assert time.monotonic() - began < 1.2


# -- streaming ---------------------------------------------------------------


def test_the_streamed_request_asks_for_the_usage_chunk(key_file):
    selection = chosen(key_file)
    opener = Opener(reply())
    mp.SelectionTransport(selection, opener=opener, idle_seconds=IDLE)(
        request(selection)
    )
    (body,) = opener.sent
    expected = mp.chat_request(request(selection))
    assert body == json.loads(
        canonical(
            {**expected, "stream": True, "stream_options": {"include_usage": True}}
        )
    )


def test_a_stream_that_keeps_sending_past_the_timeout_is_never_cut(key_file, tmp_path):
    selection = chosen(key_file)
    text = "streamed-past-the-timeout"
    events = reply(text)
    paced = []
    for event in events:
        paced.extend([event, ("sleep", IDLE / 3)])
    transport = mp.SelectionTransport(
        selection, opener=Opener(paced), idle_seconds=IDLE, deadline_seconds=IDLE
    )
    meter = ledger(tmp_path)
    began = time.monotonic()
    response = call(meter, selection, transport)
    assert time.monotonic() - began > 5 * IDLE
    assert response["status"] == "completed"
    assert response["output"] == [
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text}],
        }
    ]
    assert response["provider_stream"] == {
        "rule": mp.TRANSPORT_STREAM_V1,
        "streamed": True,
        "usage_reported": True,
    }
    (op,) = meter.status(owner="alice")["operations"]
    assert op["state"] == "SUCCEEDED"
    assert type(op["result"]["reply_ms"]) is int and op["result"]["reply_ms"] > 0


def test_usage_from_the_final_chunk_meters_exactly(key_file, tmp_path):
    selection = chosen(key_file)
    usage = {
        "prompt_tokens": 120,
        "completion_tokens": 33,
        "prompt_tokens_details": {"cached_tokens": 20},
        "completion_tokens_details": {"reasoning_tokens": 7},
    }
    events = reply("ok", usage=None, done=False)
    # A provider that reports running usage: the last one is the count.
    events[1] = chunk({"content": "o"}, usage={"prompt_tokens": 120})
    events += [chunk(usage=usage), "[DONE]"]
    transport = mp.SelectionTransport(
        selection, opener=Opener(events), idle_seconds=IDLE
    )
    meter = ledger(tmp_path)
    response = call(meter, selection, transport)
    assert response["usage"] == {
        "input_tokens": 120,
        "output_tokens": 33,
        "input_tokens_details": {"cached_tokens": 20},
        "output_tokens_details": {"reasoning_tokens": 7},
    }
    (op,) = meter.status(owner="alice")["operations"]
    assert op["actual"]["provider_nanodollars"] == 100 * 100 + 20 * 10 + 33 * 400


def test_with_no_usage_chunk_the_call_is_booked_at_its_reservation(key_file, tmp_path):
    selection = chosen(key_file)
    transport = mp.SelectionTransport(
        selection, opener=Opener(reply(usage=None)), idle_seconds=IDLE
    )
    meter = ledger(tmp_path)
    with pytest.raises(ProviderCallUnresolved) as unresolved:
        call(meter, selection, transport)
    assert unresolved.value.reason == "stream_usage_not_reported"
    assert unresolved.value.report()["code"] == "provider_stream_usage_not_reported"
    assert uncertain(meter)["reason"] == "stream_usage_not_reported"
    held(meter, selection)
    # Never resent; Reconcile books the reservation (fcntl-bound below).
    with pytest.raises(ValueError, match="no resend"):
        call(meter, selection, transport)


def test_settling_a_stream_with_no_usage_books_the_reservation(key_file, tmp_path):
    pytest.importorskip("fcntl")
    from carbon.development_session.research_agent import (
        settle_uncertain_call,
        uncertain_calls,
    )

    selection = chosen(key_file)
    transport = mp.SelectionTransport(
        selection, opener=Opener(reply(usage=None)), idle_seconds=IDLE
    )
    meter = ledger(tmp_path)
    with pytest.raises(ProviderCallUnresolved):
        call(meter, selection, transport)
    (pending,) = uncertain_calls(meter, owner="alice")
    assert pending["reason"] == "stream_usage_not_reported"
    assert pending["refusal"] is None
    settlement = settle_uncertain_call(meter, owner="alice", identity="model-1")
    assert settlement["reason"] == "stream_usage_not_reported"
    assert settlement["booked"]["provider_nanodollars"] == selection.reservation_nano
    assert settlement["retry_dispatched"] is False


def test_tool_call_deltas_assemble_into_the_same_calls(key_file, tmp_path):
    selection = chosen(key_file)
    first = {"index": 0, "id": "call_a", "type": "function"}
    second = {"index": 1, "id": "call_b", "type": "function"}
    events = [
        chunk({"role": "assistant", "content": "Let me look."}),
        chunk(
            {"tool_calls": [{**first, "function": {"name": "read", "arguments": ""}}]}
        ),
        chunk({"tool_calls": [{"index": 0, "function": {"arguments": '{"pa'}}]}),
        chunk(
            {"tool_calls": [{**second, "function": {"name": "run", "arguments": "{"}}]}
        ),
        # The id repeated is the same call; fragments arrive interleaved.
        chunk(
            {
                "tool_calls": [
                    {"index": 0, "id": "call_a", "function": {"arguments": 'th": "a"}'}}
                ]
            }
        ),
        chunk({"tool_calls": [{"index": 1, "function": {"arguments": '"n": 2}'}}]}),
        chunk(finish="tool_calls"),
        chunk(usage=USAGE),
        "[DONE]",
    ]
    transport = mp.SelectionTransport(
        selection, opener=Opener(events), idle_seconds=IDLE
    )
    response = call(ledger(tmp_path), selection, transport)
    whole = {
        "model": "fixture-model",
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": "Let me look.",
                    "tool_calls": [
                        {
                            "id": "call_a",
                            "type": "function",
                            "function": {"name": "read", "arguments": '{"path": "a"}'},
                        },
                        {
                            "id": "call_b",
                            "type": "function",
                            "function": {"name": "run", "arguments": '{"n": 2}'},
                        },
                    ],
                },
            }
        ],
        "usage": USAGE,
    }
    expected = mp.chat_response(whole)
    assert {k: v for k, v in response.items() if k != "provider_stream"} == expected
    assert [item["call_id"] for item in response["output"][1:]] == ["call_a", "call_b"]


def test_a_reply_cut_at_its_output_cap_is_incomplete_as_ever(key_file, tmp_path):
    selection = chosen(key_file)
    events = [chunk({"content": "par"}), chunk(finish="length"), chunk(usage=USAGE)]
    events.append("[DONE]")
    transport = mp.SelectionTransport(
        selection, opener=Opener(events), idle_seconds=IDLE
    )
    meter = ledger(tmp_path)
    response = call(meter, selection, transport)
    assert response["status"] == "incomplete"
    (op,) = meter.status(owner="alice")["operations"]
    assert op["result"]["incomplete"] == {
        "reason": "max_output_tokens",
        "output_tokens": 10,
        "max_output_tokens": 2048,
    }


def test_an_idle_gap_over_the_timeout_is_unknown_and_booked(key_file, tmp_path):
    selection = chosen(key_file)
    events = reply("abc")
    events.insert(2, ("sleep", 4 * IDLE))
    transport = mp.SelectionTransport(
        selection, opener=Opener(events), idle_seconds=IDLE
    )
    meter = ledger(tmp_path)
    began = time.monotonic()
    with pytest.raises(ProviderCallFailed, match="uncertain") as failed:
        call(meter, selection, transport)
    assert time.monotonic() - began < 3 * IDLE
    assert failed.value.outcome is mp.ProviderOutcome.UNKNOWN
    assert failed.value.requires_settlement and not failed.value.resumable
    assert uncertain(meter)["reason"] == "transport_outcome_unknown"
    held(meter, selection)
    with pytest.raises(ValueError, match="reconciliation required, no resend"):
        call(meter, selection, transport)


def test_the_miners_elapsed_limit_still_ends_a_streamed_call(key_file):
    selection = chosen(key_file)
    events = reply("x" * 40)
    paced = []
    for event in events:
        paced.extend([event, ("sleep", 0.05)])
    transport = mp.SelectionTransport(
        selection, opener=Opener(paced), idle_seconds=IDLE
    )
    began = time.monotonic()
    with pytest.raises(mp.ProviderStreamCut, match="elapsed limit"):
        transport(request(selection), remaining_seconds=0.4)
    assert time.monotonic() - began < 1.0
    assert mp.classify(mp.ProviderStreamCut("x")).outcome is mp.ProviderOutcome.UNKNOWN


def test_the_ledger_passes_what_is_left_of_the_elapsed_limit(key_file, tmp_path):
    selection = chosen(key_file)
    seen = []

    class Recording(mp.SelectionTransport):
        def __call__(self, request, *, remaining_seconds=None):
            seen.append(remaining_seconds)
            return super().__call__(request, remaining_seconds=remaining_seconds)

    clock = iter(range(1000, 2000, 7))
    meter = ledger(tmp_path, clock=lambda: next(clock), elapsed_seconds=3600)
    transport = Recording(selection, opener=Opener(reply(), reply()), idle_seconds=IDLE)
    # The first call is bounded too: its reservation starts the campaign.
    call(meter, selection, transport)
    call(meter, selection, transport, identity="model-2")
    with meter.db() as db:
        started = db.execute("SELECT started FROM campaign WHERE id=1").fetchone()[0]
    assert type(started) in (int, float)
    assert len(seen) == 2 and all(type(left) in (int, float) for left in seen)
    assert 0 < seen[1] < seen[0] < 3600
    # A campaign with no elapsed limit has no bound but the idle timeout.
    unbounded, seen[:] = ledger(tmp_path / "free", elapsed_seconds=None), []
    transport = Recording(selection, opener=Opener(reply()), idle_seconds=IDLE)
    call(unbounded, selection, transport)
    assert seen == [None]
    # A call read whole is handed nothing.
    whole = chosen(key_file, transport=None)
    seen[:] = []
    body = {
        "model": "fixture-model",
        "choices": [
            {"index": 0, "message": {"content": "ok"}, "finish_reason": "stop"}
        ],
        "usage": USAGE,
    }
    call(
        ledger(tmp_path / "whole"),
        whole,
        Recording(whole, opener=Opener(io.BytesIO(json.dumps(body).encode()))),
    )
    assert seen == [None]


MALFORMED = {
    "not_json": [b"data: {not json\n\n"],
    "not_an_object": [b"data: [1, 2]\n\n"],
    "choices_not_a_list": [chunk(choices={"index": 0})],
    "content_not_text": [chunk({"content": 7})],
    "second_choice": [
        {**chunk({"content": "a"}), "choices": [{"index": 1, "delta": {}}]}
    ],
    "tool_index_missing": [chunk({"tool_calls": [{"function": {"arguments": "{}"}}]})],
    "tool_id_changes": [
        chunk({"tool_calls": [{"index": 0, "id": "a", "function": {"name": "f"}}]}),
        chunk({"tool_calls": [{"index": 0, "id": "b"}]}),
    ],
    "error_mid_stream": [chunk({"content": "a"}), {"error": {"code": "overloaded"}}],
    "usage_not_an_object": [chunk({"content": "a"}, usage=[1])],
    "not_utf8": [b"data: \xff\xfe\n\n"],
}


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_a_malformed_chunk_is_uncertain_never_a_crash(key_file, tmp_path, name):
    selection = chosen(key_file)
    events = [chunk({"role": "assistant"}), *MALFORMED[name], *reply("z")[1:]]
    transport = mp.SelectionTransport(
        selection, opener=Opener(events), idle_seconds=IDLE
    )
    meter = ledger(tmp_path)
    with pytest.raises(ProviderCallFailed) as failed:
        call(meter, selection, transport)
    assert failed.value.outcome is mp.ProviderOutcome.UNKNOWN
    assert uncertain(meter)["reason"] == "transport_outcome_unknown"
    held(meter, selection)


@pytest.mark.parametrize(
    "events",
    [
        # The connection closed before the finish reason or the usage chunk.
        [chunk({"content": "a"})],
        [chunk({"content": "a"}), chunk(finish="stop")],
        # The sentinel with no finish reason: not a whole reply.
        [chunk({"content": "a"}), "[DONE]"],
        # An event the connection closed inside is never read.
        [chunk({"content": "a"}), chunk(finish="stop"), b'data: {"usage": '],
    ],
)
def test_a_stream_cut_before_its_final_chunk_is_uncertain(key_file, tmp_path, events):
    selection = chosen(key_file)
    transport = mp.SelectionTransport(
        selection, opener=Opener(events), idle_seconds=IDLE
    )
    meter = ledger(tmp_path)
    with pytest.raises(ProviderCallFailed):
        call(meter, selection, transport)
    assert uncertain(meter)["reason"] == "transport_outcome_unknown"
    held(meter, selection)


def test_a_closed_stream_after_its_usage_chunk_is_whole(key_file, tmp_path):
    selection = chosen(key_file)
    transport = mp.SelectionTransport(
        selection, opener=Opener(reply(done=False)), idle_seconds=IDLE
    )
    assert call(ledger(tmp_path), selection, transport)["status"] == "completed"


def test_the_assembled_reply_stays_within_the_response_bound(key_file, tmp_path):
    selection = chosen(key_file)
    limit = selection.settings.max_response_bytes
    piece = "x" * (limit // 3)
    events = [chunk({"content": piece}) for _ in range(4)] + reply("")[1:]
    transport = mp.SelectionTransport(
        selection, opener=Opener(events), idle_seconds=IDLE
    )
    meter = ledger(tmp_path)
    with pytest.raises(ProviderCallFailed):
        call(meter, selection, transport)
    assert uncertain(meter)["reason"] == "transport_outcome_unknown"
    # One line longer than the bound is cut too, unread past it.
    stream = mp._ChatStream(limit)
    with pytest.raises(mp.ProviderStreamCut, match="exceeds the response bound"):
        stream._grow("y" * (limit + 1))
    line = Stream([b"data: " + b"y" * (limit + 10) + b"\n\n"])
    with pytest.raises(mp.ProviderStreamCut, match="line exceeds"):
        mp._read_stream(line, limit, {})


def test_comments_are_no_progress_and_a_whole_json_answer_is_read_whole(key_file):
    selection = chosen(key_file)
    # Keep-alive comments every so often are not chunks: the call goes idle.
    alive = [chunk({"content": "a"})]
    for _ in range(12):
        alive += [b": keep-alive\n\n", ("sleep", IDLE / 3)]
    transport = mp.SelectionTransport(
        selection, opener=Opener(alive + reply("")[1:]), idle_seconds=IDLE
    )
    with pytest.raises(mp.ProviderStreamCut, match="no stream chunk"):
        transport(request(selection))
    # A provider that answers the whole reply as JSON is read whole.
    whole = {
        "model": "fixture-model",
        "choices": [
            {"index": 0, "message": {"content": "ok"}, "finish_reason": "stop"}
        ],
        "usage": USAGE,
    }
    body = io.BytesIO(json.dumps(whole).encode())
    body.headers = {"Content-Type": "application/json; charset=utf-8"}
    response = mp.SelectionTransport(selection, opener=Opener(body), idle_seconds=IDLE)(
        request(selection)
    )
    assert response["provider_stream"]["streamed"] is False
    assert {k: v for k, v in response.items() if k != "provider_stream"} == (
        mp.chat_response(whole)
    )


def test_a_rejection_is_still_typed_when_streaming(key_file):
    import urllib.error

    selection = chosen(key_file)

    class Refusing:
        def open(self, outgoing, timeout):
            raise urllib.error.HTTPError(
                "https://fixture.invalid",
                429,
                "fixture",
                Message(),
                io.BytesIO(b'{"error": {"code": "rate_limit"}}'),
            )

    with pytest.raises(mp.ProviderHTTPError) as raised:
        mp.SelectionTransport(selection, opener=Refusing(), idle_seconds=IDLE)(
            request(selection)
        )
    assert raised.value.status == 429


# -- over a real socket ------------------------------------------------------


@pytest.fixture(scope="module")
def certificate(tmp_path_factory):
    """A throwaway self-signed certificate for 127.0.0.1 (test only)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    folder = tmp_path_factory.mktemp("tls")
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "carbon-fixture")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(hours=1))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = folder / "cert.pem", folder / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


class SSEServer:
    """A local HTTPS server streaming one scripted SSE reply, chunked, per
    connection."""

    def __init__(self, events, certificate):
        self.events, self.stop = events, threading.Event()
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(*map(str, certificate))
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.port, self.held = self.listener.getsockname()[1], []
        threading.Thread(target=self._accept, daemon=True).start()

    @property
    def endpoint(self):
        return f"https://127.0.0.1:{self.port}/v1/chat/completions"

    def _accept(self):
        while not self.stop.is_set():
            try:
                raw, _ = self.listener.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(raw,), daemon=True).start()

    def _serve(self, raw):
        try:
            conn = self.context.wrap_socket(raw, server_side=True)
            self.held.append(conn)
            data = b""
            while b"\r\n\r\n" not in data:
                data += conn.recv(65536)
            head, _, body = data.partition(b"\r\n\r\n")
            length = int(
                next(
                    line.split(b":")[1]
                    for line in head.split(b"\r\n")
                    if line.lower().startswith(b"content-length")
                )
            )
            while len(body) < length:
                body += conn.recv(65536)
            conn.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                b"Transfer-Encoding: chunked\r\n\r\n"
            )
            for event in sse(*self.events):
                if type(event) is tuple:
                    if self.stop.wait(event[1]):
                        return
                    continue
                conn.sendall(b"%x\r\n" % len(event) + event + b"\r\n")
            conn.sendall(b"0\r\n\r\n")
        except (OSError, ssl.SSLError):
            pass

    def close(self):
        self.stop.set()
        self.listener.close()
        for sock in self.held:
            try:
                sock.close()
            except OSError:
                pass


@pytest.fixture
def server(certificate, monkeypatch):
    for name in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv("no_proxy", "*")
    monkeypatch.setenv("SSL_CERT_FILE", str(certificate[0]))
    started = []

    def start(events):
        fake = SSEServer(events, certificate)
        started.append(fake)
        return fake

    yield start
    for fake in started:
        fake.close()


def test_over_a_socket_a_long_stream_completes_and_a_stalled_one_is_cut(
    server, key_file
):
    idle = 1.0
    events = reply("socket")
    paced = []
    for event in events:
        paced.extend([event, ("sleep", idle / 3)])
    fake = server(paced)
    selection = chosen(key_file, endpoint=fake.endpoint)
    began = time.monotonic()
    response = mp.SelectionTransport(selection, idle_seconds=idle)(request(selection))
    # Ten events a third of the timeout apart: past three timeouts, never cut.
    assert time.monotonic() - began > 3 * idle
    assert response["output"][0]["content"][0]["text"] == "socket"
    assert response["usage"]["output_tokens"] == 10

    stalled = server([chunk({"content": "a"}), ("sleep", 30)])
    selection = chosen(key_file, endpoint=stalled.endpoint)
    began = time.monotonic()
    with pytest.raises(mp.ProviderStreamCut, match="no stream chunk"):
        mp.SelectionTransport(selection, idle_seconds=idle)(request(selection))
    assert time.monotonic() - began < idle + 2.0


# -- the observed speed ------------------------------------------------------


def operation(reply_ms, output_tokens):
    return {
        "id": "model-x",
        "state": "SUCCEEDED",
        "result": {"usage": {"output_tokens": output_tokens}, "reply_ms": reply_ms},
    }


def plan(key_file, **kwargs):
    return chosen(key_file, **kwargs).record()


def test_the_rate_warning_appears_only_from_observed_data(key_file):
    whole = plan(key_file, transport=None, max_output_tokens=65536, timeout_seconds=600)
    # Before any completed call: no speed, so no warning.
    speed = projection.model_speed([], whole)
    assert speed["output_tokens_per_second"] is None and speed["warning"] is False
    assert speed["calls_observed"] == 0 and speed["full_reply_seconds"] is None
    # A call with no usage or no timing gives no speed either.
    assert (
        projection.model_speed(
            [{"result": {"usage": None, "reply_ms": 9000}}, {"result": {"usage": {}}}],
            whole,
        )["output_tokens_per_second"]
        is None
    )
    # 50 tokens/s observed: 65,536 tokens take ~1,311 s, past 600 s.
    slow = projection.model_speed([operation(20_000, 1000)], whole)
    assert slow["output_tokens_per_second"] == 50.0
    assert slow["full_reply_seconds"] == 1311 and slow["warning"] is True
    # Fast enough: no warning.
    fast = projection.model_speed([operation(1000, 200), operation(1000, 200)], whole)
    assert fast["output_tokens_per_second"] == 200.0 and fast["calls_observed"] == 2
    assert fast["warning"] is False
    # A streaming plan is never warned: its replies are not cut while tokens
    # arrive.
    streamed = plan(key_file, max_output_tokens=65536, timeout_seconds=600)
    speed = projection.model_speed([operation(20_000, 1000)], streamed)
    assert speed["streams"] is True and speed["warning"] is False
    # The campaign view carries the same, closed.
    view = campaign_view.model_speed({"model_speed": slow})
    assert view == {**slow, "streams": False}
    assert campaign_view.model_speed({}) is None
    assert (
        campaign_view.model_speed(
            {"model_speed": {**slow, "output_tokens_per_second": None}}
        )["warning"]
        is False
    )


def test_the_wizard_names_the_trade_and_invents_no_speed():
    timeout = capabilities._call_timeout()
    assert timeout["transport_rule"] == mp.TRANSPORT_STREAM_V1
    assert timeout["streaming_providers"] == ["chutes", "openai-compatible-chat"]
    assert timeout["streaming_note"].startswith(
        "Streams: long replies are not cut while tokens arrive."
    )
    assert "Carbon records no model speed" in timeout["speed_note"]
    assert "tokens/s" not in timeout["speed_note"]
