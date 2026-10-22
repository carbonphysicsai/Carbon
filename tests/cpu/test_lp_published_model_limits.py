"""A live-listed provider's own published model limits are the defaults.

The owner, relayed by the Test Lead 2026-10-21: "I'm trying to not limit
miners at all... just enable them"; no Carbon-chosen number may bind model
settings. So, for a provider whose public model list publishes them (Chutes'
`/v1/models`):
- a new plan's default output cap is the model's `max_output_length`, and its
  context the smaller of `context_length` and `max_model_len`, each recorded
  with the list and the time setup read it, and frozen in the plan;
- a field the list does not publish as a positive whole number is "not
  published", never a crash;
- only `select`'s existing bounds clamp, and the clamp is recorded;
- a provider that publishes nothing keeps the conservative fallback, and the
  capability text says the miner should set it;
- Engy, and every plan frozen before, is unchanged;
- a cap the miner sets binds, and each call is still reserved at the cap
  against the miner's own ceiling.

Every model list is a fixture document; no provider is contacted.
"""

from __future__ import annotations

import datetime
import io
import json
import urllib.error

import pytest

from carbon.development_session import model_provider as mp
from scripts.dev.miner_launchpad import capabilities

NOW = datetime.datetime(2026, 10, 21, 9, 30, tzinfo=datetime.timezone.utc)
KIMI = "moonshotai/Kimi-K2.6"
CREDENTIAL = {"kind": "file", "reference": "/nonexistent/fixture.key"}
#: Chutes' /v1/models shape (fixture values, not a live read): Kimi publishes
#: its output maximum and context; the others are malformed or partial.
CHUTES_LIST = {
    "object": "list",
    "data": [
        {
            "id": KIMI,
            "pricing": {"prompt": 0.6, "completion": 2.5, "input_cache_read": 0.15},
            "max_output_length": 65535,
            "context_length": 262144,
            "max_model_len": 262144,
        },
        {
            "id": "malformed/model",
            "pricing": {"prompt": 0.1, "completion": 0.2},
            "max_output_length": "65535",
            "context_length": -1,
            "max_model_len": True,
        },
        {
            "id": "fractional/model",
            "max_output_length": 16384.0,
            "context_length": 0,
            "max_model_len": None,
        },
        {
            "id": "narrow/model",
            "max_output_length": 200000,
            "context_length": 262144,
            "max_model_len": 131072,
        },
        {"id": "silent/model"},
    ],
}


class Opener:
    def __init__(self, document):
        self.document, self.sent = document, []

    def open(self, request, timeout=None):
        self.sent.append(request.full_url)
        if request.full_url != mp.CHUTES_MODELS_URL:
            raise urllib.error.HTTPError(
                request.full_url, 404, "absent", {}, io.BytesIO(b"{}")
            )
        return io.BytesIO(json.dumps(self.document).encode())


def limits(model_id):
    return mp.published_limits("chutes", model_id, opener=Opener(CHUTES_LIST), now=NOW)


def pricing(model_id):
    return mp.published_pricing("chutes", model_id, opener=Opener(CHUTES_LIST), now=NOW)


def new_plan(model_id, *, settings=None, graphite=False, with_limits=True):
    """A new plan's selection on Chutes, as setup's spec carries it."""
    return mp.select(
        provider_id="chutes",
        model_id=model_id,
        credential=CREDENTIAL,
        settings=settings,
        published_pricing=pricing(model_id),
        **({"published_limits": limits(model_id)} if with_limits else {}),
        output_default=mp.OUTPUT_DEFAULT_V2,
        input_default=mp.INPUT_DEFAULT_V2 if graphite else None,
        timeout_default=mp.TIMEOUT_DEFAULT_V2,
    )


def test_kimi_publishes_its_output_and_context_and_they_are_recorded():
    record = limits(KIMI)
    assert record == {
        "max_output_length": 65535,
        "context_length": 262144,
        "max_model_len": 262144,
        "source": mp.PUBLISHED_LIVE,
        "reference": mp.CHUTES_MODELS_URL,
        "observed": "2026-10-21T09:30:00Z",
        "note": record["note"],
    }
    assert mp.PUBLISHED_LIVE == "provider_published_live"
    found = mp.output_maximum("chutes", KIMI, published_limits=record)
    assert found == {
        "max_output_tokens": 65535,
        "basis": mp.OUTPUT_FROM_PUBLISHED_LIVE,
        "source": {
            "max_output_length": 65535,
            "reference": mp.CHUTES_MODELS_URL,
            "observed": "2026-10-21T09:30:00Z",
            "bound": None,
        },
    }
    context = mp.published_context("chutes", KIMI, record)
    assert context["tokens"] == 262144
    assert context["basis"] == mp.PUBLISHED_LIVE
    assert context["reference"] == mp.CHUTES_MODELS_URL

    # An autonomous plan: Kimi's own output maximum, the historical window.
    autonomous = new_plan(KIMI)
    assert autonomous.settings.max_output_tokens == 65535
    assert autonomous.settings.max_input_tokens == 65536
    assert autonomous.record()["published_limits"] == record
    # A Graphite plan also opens with Kimi's published context less its cap.
    graphite = new_plan(KIMI, graphite=True)
    assert graphite.settings.max_input_tokens == 262144 - 65535 == 196609
    assert graphite.input_window["published_context"] == context
    assert graphite.input_window["basis"] == mp.INPUT_FROM_PUBLISHED


def test_each_call_is_reserved_at_the_published_cap_and_the_miner_may_lower_it():
    # The fixture's published price: 600 and 2,500 nanodollars per token.
    autonomous = new_plan(KIMI)
    assert autonomous.reservation_nano == 65536 * 600 + 65535 * 2500 == 203159100
    graphite = new_plan(KIMI, graphite=True)
    assert graphite.reservation_nano == 196609 * 600 + 65535 * 2500 == 281802900
    lowered = new_plan(KIMI, settings={"max_output_tokens": 4096})
    assert lowered.settings.max_output_tokens == 4096
    assert lowered.reservation_nano == 65536 * 600 + 4096 * 2500


def test_a_field_not_published_as_a_positive_whole_number_is_not_published():
    for model_id in ("malformed/model", "fractional/model", "silent/model"):
        record = limits(model_id)
        assert [record[name] for name in mp.LIMIT_FIELDS] == [None, None, None]
        found = mp.output_maximum("chutes", model_id, published_limits=record)
        assert found["basis"] == mp.OUTPUT_CONSERVATIVE
        assert found["max_output_tokens"] == 2048
        assert mp.published_context("chutes", model_id, record) is None
        chosen = mp.select(
            provider_id="chutes",
            model_id=model_id,
            credential=CREDENTIAL,
            published_limits=record,
            output_default=mp.OUTPUT_DEFAULT_V2,
            input_default=mp.INPUT_DEFAULT_V2,
        )
        assert chosen.settings.max_output_tokens == 2048
        assert chosen.settings.max_input_tokens == 65536
        assert chosen.input_window["basis"] == mp.INPUT_CONSERVATIVE
    # A model the list does not carry is refused, as its price is.
    with pytest.raises(ValueError, match="not in the published list"):
        limits("absent/model")
    # A list that is not a list is refused, never a crash in a campaign.
    with pytest.raises(ValueError, match="malformed"):
        mp.published_limits("chutes", KIMI, opener=Opener({"data": {}}), now=NOW)


@pytest.mark.parametrize(
    "change",
    [
        {"max_output_length": "65535"},
        {"context_length": 0},
        {"max_model_len": 1.5},
        {"source": "miner_declared"},
        {"reference": "https://elsewhere.example/v1/models"},
        {"observed": "2026-10-21"},
        {"extra": 1},
    ],
)
def test_a_frozen_limits_record_is_checked_exactly(change):
    with pytest.raises(mp.ModelSelectionRefused, match="published limits"):
        mp.select(
            provider_id="chutes",
            model_id=KIMI,
            credential=CREDENTIAL,
            published_limits={**limits(KIMI), **change},
        )


def test_the_smaller_context_binds_and_no_carbon_maximum_clamps():
    record = limits("narrow/model")
    context = mp.published_context("chutes", "narrow/model", record)
    # context_length 262,144 and max_model_len 131,072 differ: the server's
    # enforced length is the smaller.
    assert (context["tokens"], context["field"]) == (131072, "max_model_len")
    found = mp.output_maximum("chutes", "narrow/model", published_limits=record)
    # A miner's selection: the published 200,000 as it is (limits row #8).
    assert found["max_output_tokens"] == 200000
    assert found["source"]["max_output_length"] == 200000
    assert found["source"]["bound"] is None


def test_engy_and_a_generic_adapter_are_unchanged():
    engy = mp.output_maximum("engy-chat", mp.ENGY_DEFAULT_MODEL)
    assert engy["basis"] == mp.OUTPUT_FROM_PROVIDER
    assert engy["max_output_tokens"] == 131072
    with pytest.raises(ValueError, match="no live model list"):
        mp.published_limits("engy-chat", mp.ENGY_DEFAULT_MODEL)
    with pytest.raises(mp.ModelSelectionRefused, match="not read live"):
        mp.select(
            provider_id="engy-chat",
            credential=CREDENTIAL,
            published_limits={**limits(KIMI)},
        )
    selection = mp.select(
        provider_id="engy-chat",
        credential=CREDENTIAL,
        output_default=mp.OUTPUT_DEFAULT_V2,
        input_default=mp.INPUT_DEFAULT_V2,
    )
    assert "published_limits" not in selection.record()
    assert selection.settings.max_input_tokens == 1048576 - 131072
    # The generic adapters publish nothing: the conservative cap, and the
    # capability text tells the miner to set it.
    generic = mp.output_maximum("openai-compatible-chat", "my-model")
    assert generic == {
        "max_output_tokens": 2048,
        "basis": mp.OUTPUT_CONSERVATIVE,
        "source": None,
    }
    with pytest.raises(ValueError, match="no live model list"):
        mp.published_limits("openai-compatible-chat", "my-model")
    text = capabilities._output_cap([])["basis"]
    assert "Carbon has no published maximum for that model" in text
    assert "so set your own" in text


def test_a_plan_freezes_the_limits_and_replays_unchanged():
    new = new_plan(KIMI, graphite=True)
    frozen = json.loads(json.dumps(new.record()))
    again = mp.selection_from_record(frozen, credential_file="/nonexistent/k")
    assert again.record() == frozen
    assert again.published_limits == limits(KIMI)
    assert mp.selection_spec(again)["published_limits"] == limits(KIMI)
    # A plan frozen before published limits were read carries none, and
    # replays exactly as it recorded (2,048 tokens, no published context).
    old = new_plan(KIMI, with_limits=False)
    assert old.settings.max_output_tokens == 2048
    old_record = json.loads(json.dumps(old.record()))
    assert "published_limits" not in old_record
    replayed = mp.selection_from_record(old_record, credential_file="/nonexistent/k")
    assert replayed.record() == old_record
    assert replayed.settings.max_output_tokens == 2048


def test_the_capability_document_shows_the_published_basis():
    options = {
        "agents": [{"value": "graphite", "availability": "available"}],
        "model_providers": [
            {"provider_id": provider_id, "availability": "available"}
            for provider_id in mp.ADAPTERS
        ],
    }
    cfg = {
        "model_selection": {
            "provider_id": "chutes",
            "model_id": KIMI,
            "published_pricing": pricing(KIMI),
            "published_limits": limits(KIMI),
        }
    }
    model = capabilities._model(options, capabilities.NO_PROFILE, cfg)
    shown = model["output_cap"]["defaults"]["chutes"][KIMI]
    assert shown == {
        "max_output_tokens": 65535,
        "basis": mp.OUTPUT_FROM_PUBLISHED_LIVE,
        "source": mp.output_maximum("chutes", KIMI, published_limits=limits(KIMI))[
            "source"
        ],
    }
    window = model["input_window"]
    assert window["published_context"]["chutes"][KIMI]["tokens"] == 262144
    graphite = window["graphite_defaults"]["chutes"][KIMI]
    assert graphite["max_input_tokens"] == 196609
    # A tampered profile record is ignored, never trusted.
    cfg["model_selection"]["published_limits"] = {
        **limits(KIMI),
        "max_output_length": "big",
    }
    tampered = capabilities._model(options, capabilities.NO_PROFILE, cfg)
    assert tampered["output_cap"]["defaults"]["chutes"][KIMI]["basis"] == (
        mp.OUTPUT_CONSERVATIVE
    )
