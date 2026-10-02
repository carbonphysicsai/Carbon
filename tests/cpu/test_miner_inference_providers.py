"""C-MLP-03 slice 2: Chutes and Engy inference, and the generic adapters.

Chutes gets an adapter of its own whose prices come from its public model list
when a selection is made (provider-published, with the list and the time).
Engy's Chat Completions route is setup's default. The generic OpenAI-shaped
adapters become launchable with the miner's endpoint and, optionally, their
declared price, and that choice travels from setup through the runner profile
to the campaign. No provider is contacted: the openers here are fixtures.
"""

import datetime
import io
import json
import urllib.error
from pathlib import Path

import pytest

from carbon.development_session import model_provider as mp
from scripts.dev.miner_launchpad import runner
from scripts.dev.miner_launchpad.environment_setup import (
    AUTONOMOUS,
    LOCAL_CPU,
    EnvironmentSetup,
    LiveChecks,
    SetupRefused,
    check_quote,
)

KEY = "sk-fixture-never-echoed-0123456789"
HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
NOW = datetime.datetime(2026, 10, 2, 9, 30, tzinfo=datetime.timezone.utc)
CHUTES_MODEL = "Qwen/Qwen3.8-27B-TEE"
#: The shape Chutes' public list has (read 2026-10-02), trimmed.
CHUTES_LIST = {
    "object": "list",
    "data": [
        {
            "id": CHUTES_MODEL,
            "pricing": {"prompt": 0.24, "completion": 2.2, "input_cache_read": 0.024},
        },
        {"id": "unpriced/model"},
    ],
}
CHAT_REPLY = {
    "choices": [{"message": {"role": "assistant", "content": "ready"}}],
    "usage": {"prompt_tokens": 9, "completion_tokens": 1, "total_tokens": 10},
}
DECLARED = {
    "input_nano": 100,
    "cached_input_nano": 10,
    "output_nano": 400,
    "observed": "2026-10-02",
    "note": "my provider's published price",
}
GENERIC = "https://inference.example.org/v1/chat/completions"


class Opener:
    def __init__(self, answers):
        self.answers, self.sent, self.bodies = answers, [], []

    def open(self, request, timeout=None):
        self.sent.append((request.full_url, dict(request.header_items())))
        self.bodies.append(json.loads(request.data) if request.data else None)
        status, body = self.answers[request.full_url]
        if status != 200:
            raise urllib.error.HTTPError(
                request.full_url, status, "refused", {}, io.BytesIO(b"{}")
            )
        return io.BytesIO(json.dumps(body).encode())


def chutes_lister():
    return Opener({mp.CHUTES_MODELS_URL: (200, CHUTES_LIST)})


def credential(tmp_path):
    home = tmp_path / "keys"
    home.mkdir(mode=0o700, exist_ok=True)
    path = home / "k"
    path.write_text(KEY)
    path.chmod(0o600)
    return {"kind": "file", "reference": str(path)}


# --- the provider layer -------------------------------------------------------------


def test_chutes_prices_are_read_from_its_public_list_with_source_and_time():
    record = mp.published_pricing(
        "chutes", CHUTES_MODEL, opener=chutes_lister(), now=NOW
    )
    assert record == {
        "unit": "nanodollars per token",
        "input": 240,
        "cached_input": 24,
        "output_including_reasoning": 2200,
        "source": "provider_published",
        "reference": "https://llm.chutes.ai/v1/models",
        "observed": "2026-10-02T09:30:00Z",
        "note": record["note"],
    }
    with pytest.raises(ValueError, match="no published price"):
        mp.published_pricing("chutes", "unpriced/model", opener=chutes_lister())
    with pytest.raises(ValueError, match="not in the published list"):
        mp.published_pricing("chutes", "absent/model", opener=chutes_lister())
    with pytest.raises(ValueError, match="no live prices"):
        mp.published_pricing("engy-chat", "deepseek-v4-flash-0731")


def test_a_published_price_selects_reserves_and_round_trips(tmp_path):
    record = mp.published_pricing(
        "chutes", CHUTES_MODEL, opener=chutes_lister(), now=NOW
    )
    selection = mp.select(
        provider_id="chutes",
        model_id=CHUTES_MODEL,
        credential=credential(tmp_path),
        published_pricing=record,
    )
    assert selection.endpoint == "https://llm.chutes.ai/v1/chat/completions"
    assert selection.reservation_nano == (65536 * 240 + 2048 * 2200)
    assert selection.record()["pricing"] == record
    again = mp.selection_from_record(
        selection.record(), credential_file=credential(tmp_path)["reference"]
    )
    assert again.record() == selection.record()
    assert mp.selection_spec(selection) == {
        "provider_id": "chutes",
        "model_id": CHUTES_MODEL,
        "published_pricing": record,
    }
    # Any model id: no price published is an unknown spend, never a guess.
    unpriced = mp.select(
        provider_id="chutes", model_id="any/model", credential=credential(tmp_path)
    )
    assert unpriced.pricing is None and unpriced.reservation_nano is None


@pytest.mark.parametrize(
    "provider,change",
    [
        ("engy-chat", {}),  # Engy's prices are listed, not published live.
        ("chutes", {"reference": "https://elsewhere.example/v1/models"}),
        ("chutes", {"source": "miner_declared"}),
        ("chutes", {"observed": "2026-10-02"}),
        ("chutes", {"input": -1}),
    ],
)
def test_a_published_price_is_only_the_providers_own(tmp_path, provider, change):
    record = {
        **mp.published_pricing("chutes", CHUTES_MODEL, opener=chutes_lister(), now=NOW),
        **change,
    }
    with pytest.raises(mp.ModelSelectionRefused):
        mp.select(
            provider_id=provider,
            model_id=(
                CHUTES_MODEL if provider == "chutes" else "deepseek-v4-flash-0731"
            ),
            credential=credential(tmp_path),
            published_pricing=record,
        )


def test_a_generic_adapters_endpoint_and_declared_price_travel(tmp_path):
    selection = mp.select(
        provider_id="openai-compatible-chat",
        model_id="my-model",
        credential=credential(tmp_path),
        endpoint=GENERIC,
        declared_pricing=DECLARED,
    )
    spec = mp.selection_spec(selection, settings={"timeout_seconds": 60})
    assert spec == {
        "provider_id": "openai-compatible-chat",
        "model_id": "my-model",
        "settings": {"timeout_seconds": 60},
        "endpoint": GENERIC,
        "declared_pricing": DECLARED,
    }
    rebuilt = mp.select(credential=credential(tmp_path), **spec)
    assert rebuilt.endpoint == GENERIC
    assert rebuilt.pricing.source == "miner_declared"


# --- setup ---------------------------------------------------------------------------


class Checks:
    def __init__(self):
        self.calls = []

    def published_pricing(self, provider_id, model_id):
        self.calls.append(("published_pricing", provider_id, model_id))
        return mp.published_pricing(
            provider_id, model_id, opener=chutes_lister(), now=NOW
        )

    def inference(self, provider_id, model_id, credential_file, spec=None):
        self.calls.append(("inference", provider_id, model_id, spec))
        return {
            "models_source": "fixture",
            "models_listed": 1,
            "completion": "answered",
        }

    def compute(self, image, analysis):
        return {
            "implementation": {
                "revision": "a" * 40,
                "tree": "b" * 40,
                "source_tree_digest": "sha256:" + "c" * 64,
            },
            "images": ["sha256:" + "d" * 64, "sha256:" + "e" * 64],
        }

    @staticmethod
    def hermes_files():
        return ["/fixture/hermes/profiles/carbon/config.yaml"]

    def agent(self, hotkey, socket_path=None):
        return {"signing": "fixture"}

    @staticmethod
    def operator_config(path):
        return None


class Onboarding:
    def confirm(self, address):
        return {"registered": True, "confirmed": True}

    def requirements(self):
        return {}


def setup_with(tmp_path, inference):
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    home = tmp_path / "miner"
    home.mkdir(mode=0o700)
    for name in ("worker.json", "analysis.json", "operator.json"):
        (home / name).write_text("{}")
    checks = Checks()
    setup = EnvironmentSetup(root, onboarding=Onboarding(), checks=checks)
    setup.begin({"address": HOTKEY})
    quote = setup.quote({k: v for k, v in inference.items() if k != "key"})
    setup.inference({**inference, "consent": {"max_cost_nano": quote["max_cost_nano"]}})
    setup.compute(
        {
            "choice": LOCAL_CPU,
            "image_manifest": str(home / "worker.json"),
            "analysis_image_manifest": str(home / "analysis.json"),
        }
    )
    setup.agent({"choice": AUTONOMOUS, "operator_config": str(home / "operator.json")})
    setup.review({"confirm": True})
    return setup, checks, quote


def test_chutes_in_setup_quotes_the_published_price_and_the_launch_carries_it(
    tmp_path,
):
    setup, checks, quote = setup_with(
        tmp_path, {"provider_id": "chutes", "model_id": CHUTES_MODEL, "key": KEY}
    )
    # The quote is the check's maximum at Chutes' own published price.
    assert quote["max_cost_nano"] == 16384 * 240 + 256 * 2200
    assert "provider published" in quote["statement"]
    assert ("published_pricing", "chutes", CHUTES_MODEL) in checks.calls
    cfg = runner.validated_profile(json.loads(setup.profile_path.read_bytes()))
    chosen = cfg["model_selection"]
    assert chosen["provider_id"] == "chutes"
    assert chosen["published_pricing"]["reference"] == mp.CHUTES_MODELS_URL
    choice = runner.RunnerAdapter._launch_choice(
        cfg, {"agent": "autonomous"}, {"id": "battery", "version": "1"}
    )
    assert choice.selection.pricing.source == "provider_published"

    class Args:
        pass

    args = Args()
    choice.apply(args)
    assert args.model_selection["published_pricing"] == chosen["published_pricing"]
    assert KEY not in json.dumps(cfg)


def test_a_generic_endpoint_in_setup_is_launchable_with_its_declared_price(
    tmp_path,
):
    setup, _, quote = setup_with(
        tmp_path,
        {
            "provider_id": "openai-compatible-chat",
            "model_id": "my-model",
            "endpoint": GENERIC,
            "declared_pricing": DECLARED,
            "key": KEY,
        },
    )
    assert quote["max_cost_nano"] == 16384 * 100 + 256 * 400
    cfg = runner.validated_profile(json.loads(setup.profile_path.read_bytes()))
    assert cfg["model_selection"]["endpoint"] == GENERIC
    rows = {r["provider_id"]: r for r in runner.RunnerAdapter._model_providers(cfg)}
    assert rows["openai-compatible-chat"]["availability"] == "available"
    assert rows["openai-compatible-responses"]["reason"] == (
        "model_provider_endpoint_not_configured"
    )
    choice = runner.RunnerAdapter._launch_choice(
        cfg, {"agent": "autonomous"}, {"id": "battery", "version": "1"}
    )
    assert choice.selection.endpoint == GENERIC

    class Args:
        pass

    args = Args()
    choice.apply(args)
    assert args.model_selection["endpoint"] == GENERIC
    assert args.model_selection["declared_pricing"] == DECLARED
    # A launch cannot name another generic endpoint the profile never set.
    with pytest.raises(Exception, match="endpoint_not_configured"):
        runner.RunnerAdapter._launch_choice(
            cfg,
            {"agent": "autonomous", "model_provider": "openai-compatible-responses"},
            None,
        )


def test_a_profile_whose_selection_does_not_validate_is_refused(tmp_path):
    setup, _, _ = setup_with(
        tmp_path, {"provider_id": "chutes", "model_id": CHUTES_MODEL, "key": KEY}
    )
    cfg = json.loads(setup.profile_path.read_bytes())
    tampered = dict(cfg["model_selection"])
    tampered["published_pricing"] = {
        **tampered["published_pricing"],
        "reference": "https://elsewhere.example/v1/models",
    }
    with pytest.raises(ValueError, match="does not validate"):
        runner.validated_profile({**cfg, "model_selection": tampered})
    with pytest.raises(ValueError):
        runner.validated_profile(
            {**cfg, "model_selection": {**cfg["model_selection"], "extra": 1}}
        )


def test_the_live_chutes_check_lists_prices_and_completes_with_the_miners_key(
    tmp_path,
):
    opener = Opener(
        {
            mp.CHUTES_MODELS_URL: (200, CHUTES_LIST),
            "https://llm.chutes.ai/v1/chat/completions": (200, CHAT_REPLY),
        }
    )
    checks = LiveChecks(opener=opener)
    record = checks.published_pricing("chutes", CHUTES_MODEL)
    check = checks.inference(
        "chutes",
        CHUTES_MODEL,
        Path(credential(tmp_path)["reference"]),
        {"published_pricing": record},
    )
    assert check["completion"] == "answered"
    assert check["models_source"] == mp.CHUTES_MODELS_URL
    completion = opener.sent[-1]
    assert completion[0] == "https://llm.chutes.ai/v1/chat/completions"
    assert completion[1]["Authorization"] == "Bearer " + KEY
    # The public list is read without the key.
    assert not any(KEY in v for url, h in opener.sent[:-1] for v in h.values())
    with pytest.raises(SetupRefused) as refused:
        checks.published_pricing("chutes", "unpriced/model")
    assert refused.value.field == "model_id"


def test_the_generic_check_completes_at_the_miners_endpoint(tmp_path):
    opener = Opener({GENERIC: (200, CHAT_REPLY)})
    check = LiveChecks(opener=opener).inference(
        "openai-compatible-chat",
        "my-model",
        Path(credential(tmp_path)["reference"]),
        {"endpoint": GENERIC},
    )
    assert check["models_source"] == "not listed: any model id"
    assert [url for url, _ in opener.sent] == [GENERIC]


def test_a_quote_without_a_price_says_so(tmp_path):
    quote = check_quote(
        "openai-compatible-chat",
        "my-model",
        Path(credential(tmp_path)["reference"]),
        {"endpoint": GENERIC},
    )
    assert quote["max_cost_nano"] is None
    assert mp.UNKNOWN_SPEND in quote["statement"]
