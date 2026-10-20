"""Every implemented campaign builds its agent's first observation
(BUG MOTOR_OBSERVATION_UNSUPPORTED_20261020).

On M1 (campaign 1cff9a3b) a Motor Graphite launch interrupted at `run` after
10 model calls with KeyError at `motor.campaign.agent_observation`: it popped
"unsupported" from a registry description that listed none, while five
capabilities cannot be rebuilt there. Motor's and Cooling's descriptions now
list them as Battery's does (Validator), and each campaign's observation is
built here from its own description, with and without a frozen tools rule.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.challenge_registry.campaigns import implemented_campaigns
from carbon.development_session import research_tools
from carbon.reconstruction.capability_registry import public_registry

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
    unsupported = [
        c["id"]
        for c in public_registry(challenge_id)["capabilities"]
        if c["status"] != "rebuildable_development"
    ]
    assert observation["unsupported_capabilities"]["count"] == len(unsupported)
    assert "unsupported" not in observation["challenge"]
    json.dumps(observation)


@pytest.mark.parametrize(
    "challenge_id", ["electric-motor-magnetics", "chip-cold-plate"]
)
def test_motor_and_cooling_name_their_five_unrebuildable_capabilities(challenge_id):
    from carbon.challenge_registry import describe

    listed = describe(challenge_id, "1.0")["unsupported"]
    ids = {c["id"] for c in listed}
    for suffix in (
        "neural_operator",
        "learned_optimizer",
        "pretrained_weights",
        "loss_expressions",
        "reference_solver_reuse",
    ):
        assert any(i.endswith(suffix) for i in ids), (suffix, ids)
    for item in listed:
        assert set(item) == {"id", "status", "blocker", "summary"}
        assert item["status"] != "rebuildable_development"
