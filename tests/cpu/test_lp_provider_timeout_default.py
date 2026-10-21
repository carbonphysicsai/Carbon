"""A new agent campaign plan waits up to 600 s for each provider call.

M1 rehearsal 2026-10-21: both ProviderCallFailed (transport_outcome_unknown)
interruptions were Carbon's own 120 s provider timeout cutting two ~150 KB
Engy requests that were still being answered; each left an unknown outcome
and forced a Reconcile. So:
- a new Graphite or autonomous plan that sets no timeout_seconds freezes
  `select`'s own upper bound, 600 s (`TIMEOUT_DEFAULT_V2`), in its recorded
  selection, or half its own elapsed limit where that is shorter (never under
  10 s), so the default alone never stops its first call;
- a timeout_seconds the miner sets binds;
- a plan frozen before replays at the 120 s it recorded, and the pinned
  default (`DEFAULT_SETTINGS`) is byte-for-byte unchanged;
- a timeout is no spend: no reservation depends on it;
- the launch page reads its bounds and default from the capability
  document, and the MCP description states the same bounds.

Every selection uses a fixture key path; no provider is contacted.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from test_battery_graphite_plan import block
from test_cw1_research_ledger import ledger
from test_model_provider import HISTORICAL_PROVIDER_BLOCK, completed, request

from carbon.agent_campaign.graphite.miner import edition as editions
from carbon.battery import campaign as battery
from carbon.development_session import model_provider as mp
from carbon.development_session import research_campaign as campaigns
from carbon.development_session.profile import canonical
from carbon.development_session.research_agent import request_model
from carbon.development_session.research_ledger import DEVELOPMENT_CEILINGS
from scripts.dev.miner_launchpad import capabilities, runner
from scripts.dev.miner_launchpad.operations import FIELDS

ENGY = {"provider_id": "engy-chat", "model_id": mp.ENGY_DEFAULT_MODEL}
BUDGET = {"ceilings": {"provider_attempts": 100, "provider_nanodollars": 10**11}}


def launch(model_selection=None, *, product=True, budget=None):
    """What a launch hands a campaign's own selection builder: its product
    (with the miner's budget) or none, and the miner's choice, if any."""
    return SimpleNamespace(
        product=SimpleNamespace(budget=budget or {}) if product else None,
        model_selection=model_selection,
        api_key_file="/nonexistent/fixture.key",
    )


def new_plan(args, agent):
    """The selection `prepare_battery` (and motor's, cold plate's and the
    direct campaign's) builds for a new plan."""
    return campaigns.supplied_selection(
        args,
        output_default=campaigns.new_plan_output_default(args),
        input_default=campaigns.new_plan_input_default(args, agent),
        timeout_default=campaigns.new_plan_timeout_default(args),
        elapsed_seconds=campaigns.new_plan_elapsed_seconds(args),
    )


def test_the_rule_and_its_value_are_selects_own_bound():
    assert mp.TIMEOUT_DEFAULT_V2 == "carbon.model-selection.timeout-default.v2"
    assert mp.TIMEOUT_DEFAULTS == (None, mp.TIMEOUT_DEFAULT_V2)
    assert mp.TIMEOUT_SECONDS_BOUNDS == (10, 600)
    assert mp.TIMEOUT_DEFAULT_V2_SECONDS == mp.TIMEOUT_SECONDS_BOUNDS[1] == 600
    chosen = mp.select(
        credential={"kind": "file", "reference": "unset"},
        timeout_default=mp.TIMEOUT_DEFAULT_V2,
        **ENGY,
    )
    assert chosen.settings.timeout_seconds == 600
    with pytest.raises(mp.ModelSelectionRefused, match="unknown timeout default"):
        mp.select(
            credential={"kind": "file", "reference": "unset"},
            timeout_default="longest",
            **ENGY,
        )
    for bad in (9, 601, 120.0, "600", True):
        with pytest.raises(mp.ModelSelectionRefused, match=r"\[10, 600\]"):
            mp.select(
                credential={"kind": "file", "reference": "unset"},
                settings={"timeout_seconds": bad},
                timeout_default=mp.TIMEOUT_DEFAULT_V2,
                **ENGY,
            )


def test_a_new_graphite_plan_records_600():
    selection = new_plan(launch(ENGY), "graphite")
    assert selection.settings.timeout_seconds == 600
    plan = battery.provider_plan("graphite", BUDGET, selection, graphite=block())
    assert plan["model_selection"]["settings"]["timeout_seconds"] == 600
    # Frozen, it replays at what it recorded.
    frozen = json.loads(json.dumps(plan))
    for args in (launch(), launch(ENGY)):
        resumed = battery.plan_selection(args, frozen)
        assert resumed.settings.timeout_seconds == 600
        assert canonical(resumed.record()) == canonical(selection.record())
    # The depth edition's Planner floor (600) is met by the selection itself.
    derived, record = editions.role_selection(
        editions.DEPTH_EDITION, "planner", selection
    )
    assert derived.settings.timeout_seconds == 600
    assert record["timeout_seconds"] == {
        "selection": 600,
        "at_least": 600,
        "applied": 600,
    }


def test_a_new_autonomous_plan_records_600(tmp_path):
    # Through a domain campaign's builder.
    selection = new_plan(launch(ENGY), "autonomous")
    assert selection.settings.timeout_seconds == 600
    plan = battery.provider_plan("autonomous", BUDGET, selection)
    assert plan["model_selection"]["settings"]["timeout_seconds"] == 600
    # Through the research loop's generic builder, on the pinned model.
    root = tmp_path / "campaign"
    root.mkdir()
    args = SimpleNamespace(
        root=root,
        product=object(),
        model_selection=None,
        api_key_file="/nonexistent/fixture.key",
    )
    pinned = campaigns.campaign_selection(args)
    assert pinned.model_id == mp.GPT5_MINI
    assert pinned.settings.timeout_seconds == 600
    assert pinned.record()["settings"]["timeout_seconds"] == 600


def test_a_timeout_the_miner_sets_wins():
    for agent in ("graphite", "autonomous"):
        chosen = new_plan(launch({**ENGY, "settings": {"timeout_seconds": 300}}), agent)
        assert chosen.settings.timeout_seconds == 300
        # Even one below the historical default.
        low = new_plan(launch({**ENGY, "settings": {"timeout_seconds": 30}}), agent)
        assert low.settings.timeout_seconds == 30
    plan = battery.provider_plan("autonomous", BUDGET, chosen)
    assert plan["model_selection"]["settings"]["timeout_seconds"] == 300


def test_a_plan_frozen_before_the_rule_replays_at_120():
    # A plan frozen before recorded the 120 s its rules chose.
    old = mp.select(
        credential={"kind": "file", "reference": "unset"},
        output_default=mp.OUTPUT_DEFAULT_V2,
        **ENGY,
    )
    assert old.settings.timeout_seconds == 120
    for agent, extra in (("autonomous", {}), ("graphite", {"graphite": block()})):
        frozen = json.loads(
            json.dumps(battery.provider_plan(agent, BUDGET, old, **extra))
        )
        assert frozen["model_selection"]["settings"]["timeout_seconds"] == 120
        # Resumed with or without the same choice supplied again, it is
        # neither reinterpreted nor refused.
        for args in (launch(), launch(ENGY)):
            resumed = battery.plan_selection(args, frozen)
            assert resumed.settings.timeout_seconds == 120
            assert resumed.record() == old.record()
        # A different timeout supplied on resume is still refused.
        with pytest.raises(ValueError, match="differs from the frozen"):
            battery.plan_selection(
                launch({**ENGY, "settings": {"timeout_seconds": 300}}), frozen
            )
    # A plan frozen on the pinned default recorded no selection at all.
    pinned = battery.plan_selection(
        launch(), battery.provider_plan("autonomous", BUDGET)
    )
    assert pinned.is_historical_default
    assert pinned.settings.timeout_seconds == 120


def test_the_pinned_default_and_non_plan_callers_are_unchanged():
    assert mp.DEFAULT_SETTINGS == mp.Settings(
        max_input_tokens=65536,
        max_output_tokens=2048,
        reasoning_effort="low",
        timeout_seconds=120,
    )
    assert mp.DEFAULT_SETTINGS.record() == {
        "max_input_tokens": 65536,
        "max_output_tokens": 2048,
        "reasoning_effort": "low",
        "timeout_seconds": 120,
    }
    assert mp.DEFAULT_SELECTION.manifest_record() == HISTORICAL_PROVIDER_BLOCK
    # A bare `select` (every re-validation of a record) keeps 120.
    bare = mp.select(credential={"kind": "file", "reference": "unset"}, **ENGY)
    assert bare.settings.timeout_seconds == 120
    # A campaign admitted by a development grant is not a product launch.
    granted = new_plan(launch(ENGY, product=False), "autonomous")
    assert granted.settings.timeout_seconds == 120
    assert campaigns.new_plan_timeout_default(launch(product=False)) is None


def test_a_timeout_is_not_a_spend():
    historical = mp.select(
        credential={"kind": "file", "reference": "unset"},
        output_default=mp.OUTPUT_DEFAULT_V2,
        input_default=mp.INPUT_DEFAULT_V2,
        **ENGY,
    )
    longer = new_plan(launch(ENGY), "graphite")
    assert (historical.settings.timeout_seconds, longer.settings.timeout_seconds) == (
        120,
        600,
    )
    # The same reservation, window and output cap.
    assert longer.reservation_nano == historical.reservation_nano
    assert longer.input_window == historical.input_window
    assert longer.settings.max_output_tokens == historical.settings.max_output_tokens
    # The hard per-call deadline is still the timeout plus the margin.
    assert mp.call_deadline_seconds(longer.settings) == 600 + mp.DEADLINE_MARGIN_SECONDS


def test_the_launch_surfaces_read_the_same_bounds_and_default():
    options = {
        "agents": [{"value": "graphite", "availability": "available"}],
        "model_providers": [
            {"provider_id": provider_id, "availability": "available"}
            for provider_id in mp.ADAPTERS
        ],
    }
    model = capabilities._model(options, capabilities.NO_PROFILE, {})
    timeout = model["call_timeout"]
    assert timeout["launch_field"] == "model_settings.timeout_seconds"
    assert timeout["bounds"] == list(mp.TIMEOUT_SECONDS_BOUNDS)
    assert timeout["default"] == mp.TIMEOUT_DEFAULT_V2_SECONDS
    assert timeout["default_rule"] == mp.TIMEOUT_DEFAULT_V2
    # The default shown is what a launch that sets none gets.
    assert (
        timeout["default"]
        == new_plan(launch(ENGY), "graphite").settings.timeout_seconds
    )
    # The runner's Graphite default selection chooses the same.
    assert runner.graphite_default_selection({}).settings.timeout_seconds == 600
    # The MCP launch description states the same bounds and default.
    text = FIELDS["model_settings"][1]
    assert "timeout_seconds one from 10 to 600" in text
    assert "timeout_seconds, which is 600 seconds" in text


@pytest.mark.parametrize(
    ("elapsed", "timeout"),
    (
        (None, 600),
        (3600, 600),
        (1200, 600),
        (1199, 599),
        (600, 300),
        (300, 150),
        (21, 10),
        (20, 10),
        (5, 10),
        (1, 10),
    ),
)
def test_an_elapsed_limit_bounds_the_default(elapsed, timeout):
    budget = {} if elapsed is None else {"elapsed_seconds": elapsed}
    assert mp.timeout_default_seconds(elapsed) == timeout
    for agent in ("graphite", "autonomous"):
        chosen = new_plan(launch(ENGY, budget=budget), agent)
        assert chosen.settings.timeout_seconds == timeout
        extra = {"graphite": block()} if agent == "graphite" else {}
        plan = json.loads(
            json.dumps(battery.provider_plan(agent, BUDGET, chosen, **extra))
        )
        # The plan records the resolved value and replays it, with or
        # without the same choice supplied again.
        assert plan["model_selection"]["settings"]["timeout_seconds"] == timeout
        for args in (launch(), launch(ENGY)):
            assert battery.plan_selection(args, plan).record() == chosen.record()
    # A timeout the miner sets still wins over the limit.
    own = new_plan(
        launch({**ENGY, "settings": {"timeout_seconds": 450}}, budget=budget),
        "autonomous",
    )
    assert own.settings.timeout_seconds == 450


def test_the_elapsed_limit_reads_only_under_the_new_rule():
    with pytest.raises(mp.ModelSelectionRefused, match="only the v2 timeout"):
        mp.select(
            credential={"kind": "file", "reference": "unset"},
            elapsed_seconds=300,
            **ENGY,
        )
    for bad in (0, -1, 1.5, "300", True):
        with pytest.raises(mp.ModelSelectionRefused, match="elapsed limit"):
            mp.timeout_default_seconds(bad)
    # A development grant's campaign reads no limit and keeps 120 s.
    granted = launch(ENGY, product=False)
    assert campaigns.new_plan_elapsed_seconds(granted) is None
    assert new_plan(granted, "autonomous").settings.timeout_seconds == 120


def test_a_short_elapsed_limit_admits_calls_through_its_first_half(tmp_path):
    # The pinned model, which the fixture reply names.
    pinned = {"provider_id": "openai-responses", "model_id": mp.GPT5_MINI}
    selection = new_plan(launch(pinned, budget={"elapsed_seconds": 300}), "autonomous")
    assert selection.settings.timeout_seconds == 150
    ceilings = {**DEVELOPMENT_CEILINGS, "provider_nanodollars": 10**12}
    meter = ledger(tmp_path / "ledger", ceilings=ceilings, elapsed_seconds=300)
    sent = []

    def call(identity):
        request_model(
            meter,
            owner="alice",
            identity=identity,
            request=request(selection),
            credential_file=None,
            transport=lambda value: sent.append(value) or completed(),
            provider=selection,
            sleep=pytest.fail,
        )

    # The first call starts the campaign's clock; a second about a second
    # later still fits its 150 s timeout in the 299 s left.
    call("model-1")
    meter.clock = lambda: 1001
    call("model-2")
    assert len(sent) == 2
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 2
    # Past the first half, less than the timeout remains: no new call.
    meter.clock = lambda: 1000 + 151
    with pytest.raises(ValueError, match="timeout cannot fit"):
        call("model-3")
    assert len(sent) == 2
