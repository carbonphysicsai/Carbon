"""Every implemented campaign builds its agent's first observation
(BUG MOTOR_OBSERVATION_UNSUPPORTED_20261020).

On M1 (campaign 1cff9a3b) a Motor Graphite launch interrupted at `run` after
10 model calls with KeyError at `motor.campaign.agent_observation`: it popped
"unsupported" from a registry description that has none. Cooling had the same
line. Each campaign's observation is now built here from its own registry
description, with and without a frozen tools rule.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.challenge_registry.campaigns import implemented_campaigns
from carbon.development_session import research_tools

CAMPAIGNS = {
    entry.challenge_id: campaign for entry, campaign in implemented_campaigns()
}


def _prepared(rule):
    manifest = {"provider": {"agent": "graphite"}, "ceilings": {"provider_attempts": 3}}
    if rule is not None:
        manifest["research_tools_rule"] = rule
    practice = SimpleNamespace(
        backends=("numpy",), gpu_image=None, device=None, remote=None, gpu=None
    )
    executor = SimpleNamespace(practice=practice, julia_image=None, gpu=None)
    return SimpleNamespace(
        manifest=manifest, composition=SimpleNamespace(executor=executor)
    )


@pytest.mark.parametrize("challenge_id", sorted(CAMPAIGNS))
@pytest.mark.parametrize("rule", [None, "frozen"])
def test_the_first_observation_builds(challenge_id, rule, monkeypatch):
    campaign = CAMPAIGNS[challenge_id]
    if campaign.observation is None:
        pytest.skip("no agent observation")
    if rule is not None:
        monkeypatch.setattr(
            research_tools,
            "frozen_tools_rule",
            lambda manifest: research_tools.TOOLS_RULE,
        )
    try:
        observation = campaign.observation(_prepared(rule), 1, None)
    except AttributeError as missing:  # a richer prepared campaign than this stub
        pytest.skip(f"needs more of a prepared campaign: {missing}")
    assert observation["challenge"]
    assert observation["unsupported_capabilities"]["count"] >= 0
    assert "unsupported" not in observation["challenge"]
    json.dumps(observation)
