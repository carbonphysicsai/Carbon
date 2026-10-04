"""A new plan's output cap is the model's own maximum (OWNER-LAUNCHPAD-PROD-02).

Answer 1: "why would we limit an agents output tokens? ... It's their
economics, compute, and choice!" So:
- a new product plan reserves every call at the selected model's own maximum
  output, and meters it at what the provider reports;
- a cap the miner sets binds, and the miner's own money ceiling bounds the
  reservation exactly as before;
- a plan frozen earlier keeps the cap it recorded and resolves to the same
  record, under either output default;
- a model whose maximum Carbon has no documentation for keeps the
  conservative historical cap; nothing is guessed;
- callers that do not make a new product plan (the pinned default, Graphite,
  a development grant) are unchanged.

Every transport is a fixture: no provider is contacted and no key is real.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_cw1_research_ledger import ledger
from test_model_provider import HISTORICAL_PROVIDER_BLOCK, completed, request

from carbon.battery.campaign import plan_selection, provider_plan
from carbon.development_session import model_provider as mp
from carbon.development_session import research_campaign
from carbon.development_session.profile import canonical
from carbon.development_session.research_agent import RESERVATION_NANO, request_model
from carbon.development_session.research_ledger import DEVELOPMENT_CEILINGS

KEY = Path(tempfile.mkdtemp()) / "fixture.key"
KEY.write_text("fixture-key-not-a-credential")
CREDENTIAL = {"kind": "file", "reference": str(KEY)}
BUDGET = {"ceilings": {"provider_attempts": 96, "provider_nanodollars": 10**9}}
#: The pinned model's recorded prices (`GPT5_MINI_PRICING`), per token.
INPUT_NANO, OUTPUT_NANO = 250, 2000


def new_launch(tmp_path, model_selection=None, *, product=True):
    """What a launch hands a campaign's own selection builder: no manifest
    yet, the launch's product (or none, a development grant's campaign) and
    the miner's choice, if any."""
    root = tmp_path / "campaign"
    root.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        root=root,
        product=object() if product else None,
        model_selection=model_selection,
        api_key_file=KEY,
    )


def call(meter, selection, transport):
    return request_model(
        meter,
        owner="alice",
        identity="model-1",
        request=request(selection),
        credential_file=None,
        transport=transport,
        provider=selection,
        sleep=pytest.fail,
    )


def test_a_new_plan_reserves_at_the_model_maximum(tmp_path):
    # The pinned model: OpenAI documents 128,000 output tokens for it.
    selection = research_campaign.campaign_selection(new_launch(tmp_path))
    assert selection.model_id == mp.GPT5_MINI
    assert selection.settings.max_output_tokens == 128000
    assert mp.output_maximum("openai-responses", mp.GPT5_MINI)["basis"] == (
        mp.OUTPUT_FROM_MODEL
    )
    maximum = 65536 * INPUT_NANO + 128000 * OUTPUT_NANO
    assert selection.reservation_nano == maximum
    # No longer the pinned default, so the plan records the cap it chose.
    assert not selection.is_historical_default
    plan = provider_plan("autonomous", BUDGET, selection)
    assert plan["model_selection"]["settings"]["max_output_tokens"] == 128000

    # The call is reserved at that maximum before dispatch, sent with it, and
    # metered at the provider's own usage.
    meter = ledger(tmp_path / "ledger")
    seen = []

    def provider(sent):
        seen.append((sent["max_output_tokens"], meter.status(owner="alice")["used"]))
        return completed()

    call(meter, selection, provider)
    ((sent_cap, during),) = seen
    assert sent_cap == 128000
    assert during["provider_nanodollars"] == maximum
    used = meter.status(owner="alice")["used"]
    assert used["provider_nanodollars"] == 100 * INPUT_NANO + 10 * OUTPUT_NANO

    # Engy states no output maximum apart from each model's context, which
    # leaves room for Carbon's highest cap.
    engy = research_campaign.campaign_selection(
        new_launch(tmp_path / "engy", {"provider_id": "engy-chat"})
    )
    assert engy.settings.max_output_tokens == mp.OUTPUT_TOKEN_BOUNDS[1] == 131072
    assert mp.output_maximum("engy-chat", engy.model_id)["basis"] == (
        mp.OUTPUT_FROM_PROVIDER
    )
    assert engy.reservation_nano == 65536 * 45 + 131072 * 90


def test_a_cap_the_miner_sets_binds(tmp_path):
    capped = research_campaign.campaign_selection(
        new_launch(
            tmp_path,
            {
                "provider_id": "openai-responses",
                "model_id": mp.GPT5_MINI,
                "settings": {"max_output_tokens": 4096},
            },
        )
    )
    assert capped.settings.max_output_tokens == 4096
    assert capped.reservation_nano == 65536 * INPUT_NANO + 4096 * OUTPUT_NANO
    plan = provider_plan("autonomous", BUDGET, capped)
    assert plan["model_selection"]["settings"]["max_output_tokens"] == 4096

    # The miner's money ceiling bounds the reservation exactly as before: a
    # ceiling below the model-maximum reservation refuses that call before
    # anything is sent, and admits the same call at the miner's own cap.
    uncapped = research_campaign.campaign_selection(new_launch(tmp_path / "default"))
    ceiling = 100_000_000
    assert capped.reservation_nano <= ceiling < uncapped.reservation_nano
    ceilings = {**DEVELOPMENT_CEILINGS, "provider_nanodollars": ceiling}
    with pytest.raises(ValueError, match="miner budget: provider_nanodollars"):
        call(ledger(tmp_path / "refused", ceilings=ceilings), uncapped, pytest.fail)
    meter = ledger(tmp_path / "admitted", ceilings=ceilings)
    sent = []
    call(meter, capped, lambda value: sent.append(value) or completed())
    assert [s["max_output_tokens"] for s in sent] == [4096]
    used = meter.status(owner="alice")["used"]
    assert used["provider_nanodollars"] == 100 * INPUT_NANO + 10 * OUTPUT_NANO


def test_an_old_plan_is_unchanged(tmp_path):
    # The pinned default and its historical settings are exactly as before.
    assert mp.DEFAULT_SETTINGS.max_output_tokens == 2048
    assert mp.DEFAULT_SELECTION.manifest_record() == HISTORICAL_PROVIDER_BLOCK
    assert mp.DEFAULT_SELECTION.reservation_nano == RESERVATION_NANO
    assert RESERVATION_NANO == 65536 * INPUT_NANO + 2048 * OUTPUT_NANO

    # A battery plan frozen with the pinned default recorded no selection,
    # and still resolves to the 2,048-token pinned default.
    resume = SimpleNamespace(root=tmp_path, api_key_file=KEY)
    pinned = plan_selection(resume, provider_plan("autonomous", BUDGET))
    assert pinned.is_historical_default
    assert pinned.settings.max_output_tokens == 2048

    # A plan frozen with a selection recorded its cap, and replays the same
    # record byte for byte, whatever today's default would choose.
    spec = {"provider_id": "engy-chat", "model_id": mp.ENGY_DEFAULT_MODEL}
    recorded = mp.select(credential=CREDENTIAL, **spec).record()
    assert recorded["settings"]["max_output_tokens"] == 2048
    old_plan = {
        **provider_plan("autonomous", BUDGET),
        "model": mp.ENGY_DEFAULT_MODEL,
        "model_selection": recorded,
    }
    replayed = plan_selection(resume, json.loads(json.dumps(old_plan)))
    assert canonical(replayed.record()) == canonical(recorded)
    assert replayed.reservation_nano == 65536 * 45 + 2048 * 90

    # A frozen manifest decides, even for a product launch's arguments.
    launch = new_launch(tmp_path / "burgers")
    (launch.root / "campaign-manifest.json").write_text(
        json.dumps({"provider": recorded})
    )
    assert research_campaign.campaign_selection(launch).record() == recorded

    # Resuming the earlier plan with the same choice (no cap set) is
    # accepted under either default; a different cap is still refused.
    again = SimpleNamespace(root=tmp_path, api_key_file=KEY, model_selection=spec)
    assert research_campaign.resolve_selection(again, recorded).record() == recorded
    again.model_selection = {**spec, "settings": {"max_output_tokens": 8192}}
    with pytest.raises(ValueError, match="differs from the frozen"):
        research_campaign.resolve_selection(again, recorded)


def test_a_model_with_no_documented_maximum_keeps_the_conservative_cap(tmp_path):
    for provider_id, model_id in (
        ("anthropic", "claude-fixture-model"),
        ("openai-responses", "gpt-4.1"),
    ):
        found = mp.output_maximum(provider_id, model_id)
        assert found == {
            "max_output_tokens": 2048,
            "basis": mp.OUTPUT_CONSERVATIVE,
            "source": None,
        }
        chosen = mp.select(
            provider_id=provider_id,
            model_id=model_id,
            credential=CREDENTIAL,
            output_default=mp.OUTPUT_DEFAULT_V2,
        )
        assert chosen.settings.max_output_tokens == 2048
    # Every recorded maximum names its documentation and date.
    for adapter in mp.ADAPTERS.values():
        documented = list(adapter.output_maxima.values())
        documented += [adapter.output_maximum] if adapter.output_maximum else []
        for maximum in documented:
            assert maximum.reference and maximum.note
            assert maximum.observed == "2026-10-03"
    with pytest.raises(mp.ModelSelectionRefused, match="unknown output default"):
        mp.select(
            provider_id="engy-chat", credential=CREDENTIAL, output_default="largest"
        )


def test_only_a_new_product_plan_takes_the_new_default(tmp_path):
    # `select` without the new default (Graphite's roles, the pinned default,
    # every re-validation of a record) keeps the historical cap.
    for provider_id, model_id in (
        ("openai-responses", mp.GPT5_MINI),
        ("engy-anthropic", None),
        ("engy-chat", None),
    ):
        chosen = mp.select(
            provider_id=provider_id, model_id=model_id, credential=CREDENTIAL
        )
        assert chosen.settings.max_output_tokens == 2048
    # A campaign admitted by a development grant is not a product launch: it
    # keeps the default its grant was sized for.
    granted = research_campaign.campaign_selection(new_launch(tmp_path, product=False))
    assert granted.is_historical_default
    assert granted.settings.max_output_tokens == 2048
