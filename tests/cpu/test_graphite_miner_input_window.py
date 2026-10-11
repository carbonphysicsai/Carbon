"""A new Graphite miner-edition plan opens with the model's published input
window (OWNER-GRAPHITE-MINER-INPUT-WINDOW-01, LA-F8 option a).

The owner, 2026-10-08: "For LA-F8, default the miner edition to the model's
published input window (option a)." So:
- a new Graphite miner-edition plan that sets no max_input_tokens freezes the
  model's published context less its output cap, bounded by `select`'s own
  upper limit, and records how it chose it;
- a max_input_tokens the miner sets binds;
- a model Carbon records no context for keeps the historical 65,536, and the
  plan says so; nothing is guessed;
- every other campaign type, and every plan frozen before, is unchanged;
- the launch options and capability document state the same window and the
  same per-call reservation the campaign will freeze, and the least FULL
  ceiling that pays one research call.

Every selection uses a fixture key path; no provider is contacted.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
from test_battery_graphite_plan import block

from carbon.agent_campaign.graphite import roles
from carbon.agent_campaign.graphite.miner import driver
from carbon.battery import campaign as battery
from carbon.challenge_registry import agent_plan
from carbon.development_session import model_provider as mp
from carbon.development_session import research_campaign as campaigns
from scripts.dev.miner_launchpad import capabilities, runner
from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS

ENGY = {"provider_id": "engy-chat", "model_id": mp.ENGY_DEFAULT_MODEL}
#: 1,048,576 published less the 131,072 output default (Engy's).
ENGY_WINDOW = 1048576 - 131072
BUDGET = {"ceilings": {"provider_attempts": 100, "provider_nanodollars": 10**11}}


def launch(model_selection=None, *, product=True):
    """What a launch hands a campaign's own selection builder."""
    return SimpleNamespace(
        product=object() if product else None,
        model_selection=model_selection,
        api_key_file="/nonexistent/fixture.key",
    )


def new_plan(args, agent="graphite"):
    """The selection `prepare_battery` (and motor's and cold plate's) builds
    for a new plan."""
    return campaigns.supplied_selection(
        args,
        output_default=campaigns.new_plan_output_default(args),
        input_default=campaigns.new_plan_input_default(args, agent),
    )


def test_a_new_graphite_plan_freezes_the_published_window():
    selection = new_plan(launch(ENGY))
    assert selection.settings.max_output_tokens == 131072
    assert selection.settings.max_input_tokens == ENGY_WINDOW == 917504
    assert selection.input_window == {
        "rule": mp.INPUT_DEFAULT_V2,
        "max_input_tokens": ENGY_WINDOW,
        "basis": mp.INPUT_FROM_PUBLISHED,
        "published_context": mp.published_context("engy-chat", mp.ENGY_DEFAULT_MODEL),
        "max_output_tokens": 131072,
        "bound": None,
    }
    # A request and its whole reply fit the context Engy publishes.
    assert (
        selection.settings.max_input_tokens + selection.settings.max_output_tokens
        <= mp.ENGY_CONTEXT_TOKENS[mp.ENGY_DEFAULT_MODEL]
    )
    # The cost: each call reserves the larger window (LA-F8's figures).
    assert selection.reservation_nano == ENGY_WINDOW * 45 + 131072 * 90 == 53084160
    for plans in (battery, agent_plan):
        plan = plans.provider_plan("graphite", BUDGET, selection, graphite=block())
        assert plan["model_selection"]["settings"]["max_input_tokens"] == ENGY_WINDOW
        assert plan["input_window"] == selection.input_window


def test_the_window_is_bounded_by_selects_upper_limit_and_says_so():
    # kimi-k3 publishes 1,113,088; with a 4,096 output cap the room is above
    # the most `select` accepts.
    selection = new_plan(
        launch(
            {
                "provider_id": "engy-chat",
                "model_id": "kimi-k3",
                "settings": {"max_output_tokens": 4096},
            }
        )
    )
    high = mp.INPUT_TOKEN_BOUNDS[1]
    assert selection.settings.max_input_tokens == high == 1048576
    assert selection.input_window["basis"] == mp.INPUT_FROM_PUBLISHED
    assert selection.input_window["bound"] == {
        "upper": high,
        "source": "model_provider.INPUT_TOKEN_BOUNDS",
    }
    plan = agent_plan.provider_plan("graphite", BUDGET, selection, graphite=block())
    assert plan["input_window"]["bound"]["upper"] == high


def test_a_window_the_miner_sets_binds():
    for chosen in (32768, 200000, 1048576):
        selection = new_plan(launch({**ENGY, "settings": {"max_input_tokens": chosen}}))
        assert selection.settings.max_input_tokens == chosen
        assert selection.input_window["basis"] == mp.INPUT_FROM_MINER
        assert selection.input_window["max_input_tokens"] == chosen
    # Out of bounds is refused as before, never replaced by the default.
    with pytest.raises(mp.ModelSelectionRefused):
        new_plan(launch({**ENGY, "settings": {"max_input_tokens": 16383}}))


def test_a_model_with_no_published_context_keeps_the_old_default_and_says_so():
    selection = new_plan(launch())  # the pinned model: no recorded context
    assert mp.published_context(selection.provider_id, selection.model_id) is None
    assert selection.settings.max_input_tokens == 65536
    assert selection.input_window["basis"] == mp.INPUT_CONSERVATIVE
    assert selection.input_window["published_context"] is None
    plan = battery.provider_plan("graphite", BUDGET, selection, graphite=block())
    assert plan["input_window"]["basis"] == mp.INPUT_CONSERVATIVE
    assert plan["input_window"]["max_input_tokens"] == 65536


def test_a_context_that_leaves_no_window_keeps_the_old_default():
    record = mp.input_window("engy-chat", "glm-5.2", 262144 - 1000)
    assert record["basis"] == mp.INPUT_NO_ROOM
    assert record["max_input_tokens"] == 65536


def test_other_campaign_types_are_unchanged():
    assert mp.DEFAULT_SETTINGS.max_input_tokens == 65536
    # An autonomous (or any non-Graphite) product plan, and a Graphite
    # campaign admitted by a development grant, keep the historical window.
    assert campaigns.new_plan_input_default(launch(ENGY), "autonomous") is None
    assert campaigns.new_plan_input_default(launch(ENGY), "none") is None
    assert (
        campaigns.new_plan_input_default(launch(ENGY, product=False), "graphite")
        is None
    )
    autonomous = new_plan(launch(ENGY), agent="autonomous")
    assert autonomous.settings.max_input_tokens == 65536
    assert autonomous.input_window is None
    plan = battery.provider_plan("autonomous", BUDGET, autonomous)
    assert "input_window" not in plan
    # The research loop's generic builder (Burgers and every other campaign
    # through `campaign_selection`) and a bare `select` are unchanged.
    selection = mp.select(credential={"kind": "file", "reference": "unset"}, **ENGY)
    assert selection.settings.max_input_tokens == 65536
    assert selection.input_window is None
    # Internal Graphite keeps GRAPHITE-D34's whole-context table.
    assert roles._whole_context(mp.ENGY_DEFAULT_MODEL)["max_input_tokens"] == 1048576


def test_frozen_campaigns_keep_their_window_on_resume():
    old = mp.select(
        credential={"kind": "file", "reference": "unset"},
        output_default=mp.OUTPUT_DEFAULT_V2,
        **ENGY,
    )
    assert old.settings.max_input_tokens == 65536
    frozen_before = battery.provider_plan("graphite", BUDGET, old, graphite=block())
    assert "input_window" not in frozen_before
    new = new_plan(launch(ENGY))
    frozen_now = battery.provider_plan("graphite", BUDGET, new, graphite=block())
    # Resolved from their own records, with or without the miner's choice
    # supplied again, neither is reinterpreted or refused.
    for args in (launch(), launch(ENGY)):
        resumed = battery.plan_selection(args, frozen_before)
        assert resumed.settings.max_input_tokens == 65536
        assert resumed.record() == old.record()
        resumed = agent_plan.plan_selection(args, frozen_now)
        assert resumed.settings.max_input_tokens == ENGY_WINDOW
        assert resumed.record() == new.record()
    # A different window supplied on resume is still refused.
    with pytest.raises(ValueError, match="differs from the frozen"):
        battery.plan_selection(
            launch({**ENGY, "settings": {"max_input_tokens": 100000}}), frozen_now
        )


def test_the_launch_options_and_capabilities_state_the_new_reservation():
    cfg = {"model_selection": dict(ENGY)}
    block_ = runner.graphite_options(cfg)["input_window"]
    built = new_plan(launch(ENGY))
    assert block_["default_rule"] == mp.INPUT_DEFAULT_V2
    assert block_["default"] == built.settings.max_input_tokens == ENGY_WINDOW
    shown = block_["launch_default"]
    assert shown["model"] == "engy-chat:" + mp.ENGY_DEFAULT_MODEL
    assert shown["chosen"] == built.input_window
    assert shown["per_call_reservation_nanodollars"] == built.reservation_nano
    assert shown["advised"] is False
    assert block_["advised_at_or_below"] == 65536
    assert block_["next_step"] == NEXT_ACTIONS["graphite_input_window_too_small"]
    # The least FULL ceiling is the plan's own refusal rule's boundary.
    least = shown["full_launch_minimum_provider_nanodollars"]
    # A 10% share holds one call at ten calls' ceiling; a hunt's half at 20.
    assert least == {
        "without_hunt": built.reservation_nano * 10,
        "with_hunt": built.reservation_nano * 20,
    }
    assert math.isclose(least["without_hunt"] / 1e9, 0.5308416)
    for hunt, key in ((None, "without_hunt"), ({}, "with_hunt")):
        full = {"mode": "FULL", "research_share": 0.1, "hunt": hunt}

        def short(nano, full=full):
            ceilings = {"provider_attempts": 100, "provider_nanodollars": nano}
            return driver.research_share_shortfall(full, ceilings, built)

        assert short(least[key]) is None
        assert short(least[key] - 1)["dimension"] == "provider_nanodollars"

    # With no model chosen (the pinned default, no recorded context) the
    # window stays 65,536 and the advisory applies.
    pinned = runner.graphite_options({})["input_window"]
    assert pinned["default"] == 65536
    assert pinned["launch_default"]["advised"] is True

    # The capability document lists the same window per offered model.
    options = {
        "agents": [{"value": "graphite", "availability": "available"}],
        "model_providers": [
            {"provider_id": provider_id, "availability": "available"}
            for provider_id in mp.ADAPTERS
        ],
    }
    window = capabilities._model(options, capabilities.NO_PROFILE, {})["input_window"]
    listed = window["graphite_defaults"]["engy-chat"][mp.ENGY_DEFAULT_MODEL]
    assert listed["max_input_tokens"] == ENGY_WINDOW
    assert listed["per_call_reservation_nanodollars"] == built.reservation_nano
    assert window["graphite_default_rule"] == mp.INPUT_DEFAULT_V2
    assert window["graphite_advisory"]["applies_at_or_below"] == 65536


def test_the_advisory_says_when_it_applies():
    advisory = NEXT_ACTIONS["graphite_input_window_too_small"]
    assert "published context less its output cap" in advisory
    assert "65,536 or less" in advisory
    assert "FULL" in advisory
    assert "max_input_tokens" in NEXT_ACTIONS["research_share_too_small"]
