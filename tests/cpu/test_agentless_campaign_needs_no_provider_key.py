"""A campaign with no agent never asks for a model-provider key.

The key belongs to Carbon's autonomous agent. A person driving their own
journey calls no model, so requiring one would make a miner's own client
depend on a credential it has no use for. The specimen is the same launch with
the agent, which does construct the provider transport.
"""

import asyncio

import pytest
from test_miner_launchpad_finite_completion import setup_campaign
from test_miner_launchpad_runner import HOTKEY, registered

from carbon.development_session import research_campaign as campaign
from carbon.development_session.product_campaign import ProductLaunch
from carbon.development_session.profile import canonical
from carbon.development_session.research_agent_policy import AUTONOMOUS


def prepare(tmp_path, monkeypatch, agent):
    args, meter, _ = setup_campaign(tmp_path, monkeypatch, None)
    public = tmp_path / "public-hotkey.json"
    public.write_bytes(
        canonical({"netuid": 567, "hotkey": HOTKEY, "key_file": "unused-fixture"})
    )
    public.chmod(0o600)
    args.miner_public = public
    args.agent_policy = AUTONOMOUS
    args.product = ProductLaunch(
        campaign_id="cmp-agentless",
        principal="alice",
        miner=registered(),
        runtime={
            "implementation": "fixture",
            "images": ["trusted-fixture", "analysis-fixture"],
        },
        budget={},
        agent=agent,
    )
    constructed = []
    monkeypatch.setattr(campaign, "ResponsesTransport", constructed.append)
    prepared = asyncio.run(campaign.prepare(args, ledger=meter))
    return prepared, constructed, args


def test_an_agentless_campaign_prepares_without_a_provider_key(tmp_path, monkeypatch):
    prepared, constructed, _ = prepare(tmp_path, monkeypatch, "none")
    assert prepared.agent == "none"
    assert constructed == []


@pytest.mark.parametrize("agent", ["autonomous"])
def test_the_agent_still_needs_its_key(tmp_path, monkeypatch, agent):
    prepared, constructed, args = prepare(tmp_path, monkeypatch, agent)
    assert prepared.agent == "autonomous"
    assert constructed == [args.api_key_file]
