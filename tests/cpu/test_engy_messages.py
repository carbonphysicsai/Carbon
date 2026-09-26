"""Anthropic Messages transport, Engy accounting/provenance, caching and the
credential boundary.

Every transport here is a FIXTURE: a fake urllib opener or a local function.
No network call is made, no real key is read (the real Engy key file is
refused outright below), and no model is inferred.
"""

import asyncio
import io
import json
import os
import traceback
import urllib.error
from email.message import Message
from pathlib import Path

import pytest
from test_cw1_research_ledger import ledger

from carbon.development_session import model_provider as mp
from carbon.development_session.profile import canonical
from carbon.development_session.research_admission import (
    GRANT_PROVIDERS,
    PROFILE,
    SCHEMA,
    Admission,
)
from carbon.development_session.research_agent import (
    ProviderCallFailed,
    caching_status,
    provider_turns,
    request_model,
)
from carbon.development_session.research_ledger import (
    DEVELOPMENT_CEILINGS,
    DEVELOPMENT_ELAPSED_SECONDS,
)

REAL_KEY = "/home/carbon/.local/share/carbon-credentials/" + "engy.key"
SPECIMEN = "sk-PLANTED-SPECIMEN-4c1f9e2a7b"


@pytest.fixture(autouse=True)
def never_the_real_key(monkeypatch):
    """No test in this module may read the owner's real key file."""
    original = Path.read_text

    def guarded(self, *args, **kwargs):
        if str(self) == REAL_KEY:
            raise AssertionError("the real credential file was read")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)


@pytest.fixture
def key_file(tmp_path):
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    path = folder / "provider.key"
    path.write_text(SPECIMEN)
    path.chmod(0o600)
    return path


def engy(key_file, model_id=None, provider_id="engy-anthropic"):
    return mp.select(
        provider_id=provider_id,
        model_id=model_id,
        credential={"kind": "file", "reference": str(key_file)},
        settings={"reasoning_effort": None},
    )


def request(selection, history=None, tools=None):
    return {
        "model": selection.model_id,
        "instructions": "fixture system prompt",
        "input": history or [{"role": "user", "content": "observe"}],
        "tools": tools or [],
        "parallel_tool_calls": False,
        "store": False,
        "max_output_tokens": selection.settings.max_output_tokens,
        "reasoning": None,
    }


TOOL = {
    "type": "function",
    "name": "carbon_tool",
    "description": "fixture tool",
    "strict": True,
    "parameters": {"type": "object", "properties": {}},
}


def messages_reply(content, *, stop="end_turn", usage=None, x_engy=None, model=None):
    reply = {
        "id": "msg_fixture",
        "type": "message",
        "role": "assistant",
        "model": model or mp.ENGY_DEFAULT_MODEL,
        "content": content,
        "stop_reason": stop,
        "usage": usage
        or {
            "input_tokens": 100,
            "output_tokens": 10,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
    }
    if x_engy is not None:
        reply["x_engy"] = x_engy
    return reply


ENGY_REPORT = {
    "charged_micro": 1,
    "request_id": "req-fixture-1",
    "miner": "5FixtureMinerHotkey",
    "worker": "worker-fixture-7",
}


class Opener:
    """A fake urllib opener: records each outgoing request, replays replies."""

    def __init__(self, *replies):
        self.replies, self.sent = list(replies), []

    def open(self, outgoing, timeout):
        self.sent.append(outgoing)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(json.dumps(reply).encode())


def http_error(status, body, retry_after=None):
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError(
        "https://fixture.invalid",
        status,
        "fixture",
        headers,
        io.BytesIO(json.dumps(body).encode()),
    )


# -- admission ---------------------------------------------------------------


def grant(tmp_path, provider):
    tmp_path.chmod(0o700)
    path = tmp_path / ("grant-" + provider + ".json")
    document = {
        "schema": SCHEMA,
        "status": "APPROVED",
        "authority": "ENGINEERING_FIXTURE_ONLY",
        "grant_id": "fixture-grant",
        "campaign_id": "fixture-campaign",
        "root": str(tmp_path / "campaign"),
        "principal": "alice",
        "miner_identity": "fixture-miner",
        "profile": PROFILE,
        "runtime": {"implementation": "fixture", "images": ["fixture"]},
        "provider": provider,
        "account_ref": "fixture-no-credential",
        "campaign_count": 1,
        "ceilings": dict(DEVELOPMENT_CEILINGS),
        "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
        "expires_unix": 50000,
        "cleanup": "all-campaign-owned-work; unresolved-reservations-retained",
        "retry_allowance": 0,
    }
    path.write_bytes(canonical(document))
    path.chmod(0o600)
    return Admission.load(path)


def verify(admission, tmp_path):
    return admission.verify(
        root=tmp_path / "campaign",
        principal="alice",
        runtime={"implementation": "fixture", "images": ["fixture"]},
        now=1000,
    )


def test_admission_names_each_provider_specifically():
    assert GRANT_PROVIDERS == (
        "openai-responses",
        "engy-anthropic",
        "engy-chat",
        "anthropic",
    )
    assert set(GRANT_PROVIDERS) <= set(mp.ADAPTERS)


@pytest.mark.parametrize("provider", GRANT_PROVIDERS)
def test_a_grant_for_an_admitted_provider_verifies(tmp_path, provider):
    assert verify(grant(tmp_path, provider), tmp_path)["provider"] == provider


@pytest.mark.parametrize(
    "provider",
    # A registered adapter that is not admitted, and two that do not exist.
    ["openai-compatible-chat", "engy", "anything"],
)
def test_a_grant_for_an_unlisted_provider_is_refused(tmp_path, provider):
    with pytest.raises(ValueError, match="binding"):
        verify(grant(tmp_path, provider), tmp_path)


# -- Engy ladder -------------------------------------------------------------


def test_engy_ladder_defaults_to_the_bottom_rung(key_file):
    selection = engy(key_file)
    assert selection.model_id == "deepseek-v4-flash-0731"
    assert selection.endpoint == "https://api.engy.ai/v1/messages"
    assert mp.ENGY_LADDER == (
        "deepseek-v4-flash-0731",
        "qwen3.8-27b",
        "glm-5.3-flash",
        "glm-5.2",
        "kimi-k3",
    )
    kimi = mp.ENGY_MODELS["kimi-k3"]
    assert (kimi.input_nano, kimi.output_nano, kimi.cached_input_nano) == (
        1950,
        9750,
        195,
    )
    assert kimi.source == "declared_list"
    assert kimi.reference == "Engy published list, observed 2026-09-26"
    assert engy(key_file, provider_id="engy-chat").endpoint == (
        "https://api.engy.ai/v1/chat/completions"
    )


@pytest.mark.parametrize("model", ["deepseek-v4.1-flash", "gpt-5-mini-2025-08-07"])
def test_engy_refuses_models_off_the_ladder(key_file, model):
    with pytest.raises(mp.ModelSelectionRefused, match="not allowed"):
        engy(key_file, model)


def test_the_live_model_list_helper_sends_no_key():
    opener = Opener(
        {
            "data": [
                {"id": "deepseek-v4-flash-0731"},
                {"id": "deepseek-v4.1-flash"},
                {"id": "kimi-k3"},
            ]
        }
    )
    listed = mp.fetch_models(opener=opener)
    (outgoing,) = opener.sent
    assert outgoing.full_url == "https://api.engy.ai/v1/models"
    assert outgoing.get_method() == "GET"
    assert not any(
        k.lower() in ("authorization", "x-api-key") for k in outgoing.headers
    )
    assert listed["allowed_and_listed"] == ["deepseek-v4-flash-0731", "kimi-k3"]
    assert "glm-5.2" in listed["allowed_but_not_listed"]


# -- Messages translation ----------------------------------------------------


HISTORY = [
    {"role": "user", "content": "observe"},
    {
        "type": "reasoning",
        "messages_blocks": [{"type": "thinking", "thinking": "t", "signature": "s"}],
    },
    {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": "plan"}],
    },
    {
        "type": "function_call",
        "call_id": "toolu_1",
        "name": "carbon_tool",
        "arguments": '{"a":1}',
    },
    {"type": "function_call_output", "call_id": "toolu_1", "output": '{"ok":true}'},
    {"role": "user", "content": "reminder"},
]


def test_history_maps_onto_messages_turns_and_tool_blocks(key_file):
    selection = engy(key_file)
    body = mp.messages_request(request(selection, HISTORY, [TOOL]), selection.adapter)
    assert body["system"] == [{"type": "text", "text": "fixture system prompt"}]
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]
    assistant, results = body["messages"][1]["content"], body["messages"][2]["content"]
    assert [b["type"] for b in assistant] == ["thinking", "text", "tool_use"]
    assert assistant[2] == {
        "type": "tool_use",
        "id": "toolu_1",
        "name": "carbon_tool",
        "input": {"a": 1},
    }
    assert results == [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": '{"ok":true}'},
        {"type": "text", "text": "reminder"},
    ]
    assert body["tools"] == [
        {
            "name": "carbon_tool",
            "description": "fixture tool",
            "input_schema": {"type": "object", "properties": {}},
        }
    ]
    assert body["tool_choice"] == {"type": "auto", "disable_parallel_tool_use": True}
    assert body["max_tokens"] == 2048
    assert "cache_control" not in json.dumps(body)  # Engy: no breakpoints sent


def test_anthropic_marks_the_stable_prefix_for_caching(key_file):
    selection = mp.select(
        provider_id="anthropic",
        model_id="fixture-claude-model",
        credential={"kind": "file", "reference": str(key_file)},
    )
    assert selection.endpoint == "https://api.anthropic.com/v1/messages"
    body = mp.messages_request(request(selection, HISTORY, [TOOL]), selection.adapter)
    mark = {"type": "ephemeral"}
    assert body["system"][0]["cache_control"] == mark
    assert body["tools"][-1]["cache_control"] == mark
    assert body["messages"][-1]["content"][-1]["cache_control"] == mark


def test_messages_reply_maps_to_loop_items_usage_and_report():
    reply = mp.messages_response(
        messages_reply(
            [
                {"type": "thinking", "thinking": "why", "signature": "sig"},
                {"type": "text", "text": "Testing "},
                {"type": "text", "text": "the hypothesis."},
                {
                    "type": "tool_use",
                    "id": "toolu_2",
                    "name": "carbon_tool",
                    "input": {"z": 1, "a": 2},
                },
            ],
            stop="tool_use",
            usage={
                "input_tokens": 40,
                "output_tokens": 12,
                "cache_read_input_tokens": 900,
                "cache_creation_input_tokens": 60,
            },
            x_engy=ENGY_REPORT,
        )
    )
    assert reply["status"] == "completed"
    assert reply["output"] == [
        {
            "type": "reasoning",
            "messages_blocks": [
                {"type": "thinking", "thinking": "why", "signature": "sig"}
            ],
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "Testing the hypothesis."}],
        },
        {
            "type": "function_call",
            "call_id": "toolu_2",
            "name": "carbon_tool",
            "arguments": '{"a":2,"z":1}',
        },
    ]
    assert reply["usage"] == {
        "input_tokens": 1000,
        "output_tokens": 12,
        "input_tokens_details": {"cached_tokens": 900, "cache_creation_tokens": 60},
    }
    assert reply["x_engy"] == ENGY_REPORT


@pytest.mark.parametrize("stop", ["max_tokens", "pause_turn", "refusal"])
def test_an_unfinished_messages_turn_is_incomplete(stop):
    assert mp.messages_response(messages_reply([], stop=stop))["status"] == "incomplete"


def test_an_unmapped_block_is_refused_not_dropped():
    with pytest.raises(ValueError, match="unmapped"):
        mp.messages_response(messages_reply([{"type": "server_tool_use"}]))


def test_an_untranslatable_request_is_never_sent(tmp_path, key_file):
    selection = engy(key_file)
    opener = Opener()
    history = [
        {"role": "user", "content": "observe"},
        {"type": "function_call", "call_id": "c", "name": "t", "arguments": "not json"},
    ]
    with pytest.raises(ProviderCallFailed, match="no retry") as failed:
        request_model(
            ledger(tmp_path),
            owner="alice",
            identity="model-1",
            request=request(selection, history),
            credential_file=None,
            provider=selection,
            transport=mp.SelectionTransport(selection, opener=opener),
            sleep=pytest.fail,
        )
    assert failed.value.outcome is mp.ProviderOutcome.INVALID_REQUEST
    assert opener.sent == []


# -- Messages errors ---------------------------------------------------------


@pytest.mark.parametrize(
    "status, kind, outcome",
    [
        (429, "rate_limit_error", "rate_limited"),
        (529, "overloaded_error", "rate_limited"),
        (503, "overloaded_error", "rate_limited"),
        (500, "api_error", "transient_server"),
        (401, "authentication_error", "auth_credential"),
        (402, "billing_error", "quota_exhausted"),
        (400, "invalid_request_error", "invalid_request"),
    ],
)
def test_messages_errors_are_typed(key_file, status, kind, outcome):
    selection = engy(key_file)
    opener = Opener(
        http_error(
            status,
            {"type": "error", "error": {"type": kind, "message": "echo " + SPECIMEN}},
        )
    )
    with pytest.raises(mp.ProviderHTTPError) as raised:
        mp.SelectionTransport(selection, opener=opener)(request(selection))
    assert mp.classify(raised.value, selection.errors).outcome.value == outcome
    assert SPECIMEN not in str(raised.value)


def test_an_overloaded_provider_is_retried_under_a_new_reservation(tmp_path, key_file):
    selection = engy(key_file)
    opener = Opener(
        http_error(529, {"type": "error", "error": {"type": "overloaded_error"}}, "2"),
        messages_reply([{"type": "text", "text": "ok"}], x_engy=ENGY_REPORT),
    )
    meter, waits = ledger(tmp_path), []
    request_model(
        meter,
        owner="alice",
        identity="model-1",
        request=request(selection),
        credential_file=None,
        provider=selection,
        transport=mp.SelectionTransport(selection, opener=opener),
        sleep=waits.append,
    )
    assert waits == [2] and len(opener.sent) == 2
    used = meter.status(owner="alice")["used"]
    assert used["provider_attempts"] == 2
    assert used["provider_nanodollars"] == 1000  # the provider's 1 micro-dollar


# -- accounting and provenance -----------------------------------------------


def call(tmp_path, selection, reply):
    meter = ledger(tmp_path)
    request_model(
        meter,
        owner="alice",
        identity="epoch-1-provider-000",
        request=request(selection),
        credential_file=None,
        provider=selection,
        transport=lambda _: reply,
        sleep=pytest.fail,
    )
    return meter


def test_the_providers_charge_settles_the_call_not_the_headline(tmp_path, key_file):
    selection = engy(key_file, "kimi-k3", provider_id="engy-chat")
    reply = mp.chat_response(
        {
            "model": "kimi-k3",
            "choices": [{"finish_reason": "stop", "message": {"content": "ok"}}],
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 227,
                "prompt_tokens_details": {"cached_tokens": 800},
                "completion_tokens_details": {"reasoning_tokens": 129},
            },
            "x_engy": {**ENGY_REPORT, "charged_micro": 2582},
        }
    )
    meter = call(tmp_path, selection, reply)
    assert meter.status(owner="alice")["used"]["provider_nanodollars"] == 2582000
    (turn,) = provider_turns(meter.status(owner="alice")["operations"])
    headline = 200 * 1950 + 800 * 195 + 227 * 9750
    assert turn["estimated_nanodollars"] == headline != turn["charge_nanodollars"]
    assert turn["charge_nanodollars"] == 2582000
    assert turn["charge_basis"] == ["provider-reported x_engy.charged_micro"]
    assert turn["provider_reported_micro"] == 2582
    assert (turn["reasoning_tokens"], turn["cached_input_tokens"]) == (129, 800)
    assert turn["provenance"] == [
        {
            "request_id": "req-fixture-1",
            "miner": "5FixtureMinerHotkey",
            "worker": "worker-fixture-7",
        }
    ]
    # The per-call journal is campaign evidence, not only accounting.
    (journal,) = list(tmp_path.glob("model-*/call.json"))
    evidence = json.loads(journal.read_bytes())
    assert evidence["provider_report"]["worker"] == "worker-fixture-7"
    assert evidence["charge"]["estimated_nanodollars"] == headline


def test_a_missing_charge_report_keeps_the_whole_reservation(tmp_path, key_file):
    selection = engy(key_file)
    meter = call(tmp_path, selection, mp.messages_response(messages_reply([])))
    used = meter.status(owner="alice")["used"]["provider_nanodollars"]
    assert used == selection.reservation_nano
    (turn,) = provider_turns(meter.status(owner="alice")["operations"])
    assert turn["charge_basis"] == [
        "provider charge not reported; full reservation retained"
    ]
    assert turn["provenance"] == [{"request_id": None, "miner": None, "worker": None}]


def test_a_charge_above_the_reservation_is_retained_for_reconciliation(
    tmp_path, key_file
):
    selection = engy(key_file)
    huge = {**ENGY_REPORT, "charged_micro": selection.reservation_nano}
    with pytest.raises(ValueError, match="exceeds the reservation"):
        call(tmp_path, selection, mp.messages_response(messages_reply([], x_engy=huge)))


# -- caching -----------------------------------------------------------------


def turn_op(index, cached, state="SUCCEEDED"):
    return {
        "id": f"epoch-1-provider-{index:03d}",
        "state": state,
        "actual": {"provider_nanodollars": 0},
        "result": {
            "request_digest": "sha256:x",
            "usage": {"input_tokens": 1000, "cached_input_tokens": cached},
        },
    }


@pytest.mark.parametrize(
    "cached, status",
    [
        ([0, 0, 0], "CACHING_NOT_WORKING"),
        ([0, 0, 900], "CACHING_OBSERVED"),
        ([0, 900, 900], "CACHING_OBSERVED"),
        ([0, 0], "INSUFFICIENT_TURNS"),
        ([0, None, None], "CACHE_NOT_REPORTED"),
    ],
)
def test_caching_is_asserted_from_recorded_counts(cached, status):
    turns = provider_turns([turn_op(i, c) for i, c in enumerate(cached)])
    assert caching_status(turns)["status"] == status


def test_the_loop_prefix_is_byte_stable_across_iterations(tmp_path, key_file):
    """Two real loop iterations through the Messages transport: the tools and
    system prompt are byte-identical, and the second call's history starts
    with the first call's history byte for byte."""
    from carbon.development_session.research_agent_policy import AUTONOMOUS
    from carbon.development_session.research_loop import run_epoch

    selection = engy(key_file)
    usage = {
        "input_tokens": 100,
        "output_tokens": 5,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    opener = Opener(
        messages_reply(
            [{"type": "text", "text": "thinking aloud"}],
            usage=usage,
            x_engy=ENGY_REPORT,
        ),
        messages_reply(
            [{"type": "text", "text": "done"}], usage=usage, x_engy=ENGY_REPORT
        ),
    )
    ticks = iter(range(1000, 100000, 37))  # a clock that moves between calls
    meter = ledger(tmp_path, clock=lambda: next(ticks))
    outcome = asyncio.run(
        run_epoch(
            meter,
            owner="alice",
            epoch=1,
            sdk=None,
            credential_file=None,
            initial_observation={"z": 1, "a": {"y": 2, "b": 3}},
            agent_policy=AUTONOMOUS,
            provider=selection,
            transport=mp.SelectionTransport(selection, opener=opener),
        )
    )
    first, second = (json.loads(sent.data) for sent in opener.sent)
    assert canonical(first["tools"]) == canonical(second["tools"])
    assert canonical(first["system"]) == canonical(second["system"])
    assert [t["name"] for t in first["tools"]] == [t["name"] for t in second["tools"]]
    grown = second["messages"]
    assert canonical(grown[: len(first["messages"])]) == canonical(first["messages"])
    assert len(grown) > len(first["messages"])
    # Sorted, separator-free canonical bytes are what is sent.
    assert opener.sent[0].data == canonical(first)
    # Cost per turn and caching are in the campaign record.
    assert [t["charge_nanodollars"] for t in outcome["provider_turns"]] == [1000, 1000]
    assert outcome["caching"]["status"] == "INSUFFICIENT_TURNS"
    turn = json.loads(
        (tmp_path / "epoch-1" / "epoch-1-provider-000-turn.json").read_bytes()
    )
    assert turn["provenance"][0]["request_id"] == "req-fixture-1"


# -- credential boundary -----------------------------------------------------


def everything_written(root):
    return b"".join(p.read_bytes() for p in Path(root).rglob("*") if p.is_file())


def test_the_key_appears_only_in_its_file_and_its_request_header(
    tmp_path, key_file, capfd
):
    selection = engy(key_file)
    root = tmp_path / "ledger"
    meter = ledger(root)
    opener = Opener(
        http_error(
            401, {"error": {"type": "authentication_error", "message": SPECIMEN}}
        ),
        OSError("connection reset while sending " + SPECIMEN),
        messages_reply([{"type": "text", "text": "ok"}], x_engy=ENGY_REPORT),
    )
    failures = []
    for identity in ("model-1", "model-2", "model-3"):
        try:
            response = request_model(
                meter,
                owner="alice",
                identity=identity,
                request=request(selection),
                credential_file=None,
                provider=selection,
                transport=mp.SelectionTransport(selection, opener=opener),
                sleep=pytest.fail,
            )
        except Exception as error:  # noqa: BLE001 - the error is the output
            failures.append(error)
    assert len(failures) == 2
    outputs = [
        *(str(e) + repr(e) + "".join(traceback.format_exception(e)) for e in failures),
        json.dumps(response),
        json.dumps(provider_turns(meter.status(owner="alice")["operations"])),
        json.dumps(meter.status(owner="alice")),
        json.dumps(selection.record()),
        json.dumps(mp.provider_summary({"engy-anthropic": str(key_file)})),
        repr(selection),
        everything_written(root).decode("utf-8", "replace"),
        "".join(capfd.readouterr()),
        *os.environ.values(),
    ]
    assert not [text for text in outputs if SPECIMEN in text]
    # Specimens: the same scan finds the key where it really is - its file and
    # the one header of each request that carried it.
    assert SPECIMEN in key_file.read_text()
    headers = [dict(sent.header_items()) for sent in opener.sent]
    assert all(h["X-api-key"] == SPECIMEN for h in headers)
    assert not any("Authorization" in h for h in headers)
    assert headers[0]["Anthropic-version"] == mp.ANTHROPIC_VERSION
