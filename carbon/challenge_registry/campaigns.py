"""A campaign's Challenge-specific behaviour, reached only through the registry.

The research path is one workflow. What differs by Challenge - how a campaign
is prepared, what the agent is shown first, who evaluates a frozen candidate,
how an attach re-checks the frozen binding - is a `ChallengeCampaign`, and the
only way to obtain one is `campaign_for`, which resolves the Challenge through
`registry.resolve` first. So the workflow never names a Challenge: adding one
is registering its campaign here, not threading another branch through
`research_campaign` and `standard_cli`.

A launch that names no Challenge is the historical Burgers campaign, bound at
this edge and nowhere deeper; `resolve` itself keeps no default. A registered
Challenge without a campaign is refused with a typed reason, never run as
another Challenge.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from .registry import CPU_RESEARCH, ResolutionError, resolve


class NoCampaignComposition(ResolutionError):
    code = "challenge_has_no_campaign"
    next_action = (
        "This Challenge is registered but no research campaign is composed "
        "for it yet; select an implemented Challenge."
    )


@dataclass(frozen=True)
class ChallengeCampaign:
    #: The Challenge this campaign serves.
    key: object
    #: async (args, *, ledger) -> PreparedCampaign | None
    prepare: Callable
    #: async (prepared, epoch, strategy) -> permitted final feedback
    evaluate: Callable
    #: (prepared, epoch, feedback) -> the agent's first observation this epoch
    observation: Callable
    #: A submit refused before evaluation keeps the frozen candidate for a
    #: later submit (True), or ends the campaign with the refusal (False).
    refusal_retains_candidate: bool
    #: (manifest, *, implementation, images) -> None; raises if the frozen
    #: binding changed. None: the attach re-checks the historical Burgers
    #: roles, objective and lanes in `standard_cli`.
    check_attached: Callable | None
    #: (**attach) -> (composition, wrapper); None: the historical Burgers
    #: composition in `standard_cli`.
    compose: Callable | None


def campaign_challenge(args):
    """The Challenge a campaign is bound to, or None for the historical
    Burgers campaign. The frozen manifest decides once it exists."""
    path = args.root / "campaign-manifest.json"
    if path.exists():
        return json.loads(path.read_bytes()).get("challenge")
    product = getattr(args, "product", None)
    return getattr(product, "challenge", None)


def _burgers():
    from carbon.development_session import research_campaign as burgers

    return ChallengeCampaign(
        key=burgers.CHALLENGE,
        prepare=burgers.prepare_burgers,
        evaluate=burgers.evaluate_burgers,
        observation=burgers.burgers_observation,
        refusal_retains_candidate=False,
        check_attached=None,
        compose=None,
    )


def _battery():
    from carbon.battery import campaign as battery

    return ChallengeCampaign(
        key=battery.CHALLENGE,
        prepare=battery.prepare_battery,
        evaluate=battery.evaluate_frozen,
        observation=battery.agent_observation,
        refusal_retains_candidate=True,
        check_attached=battery.check_attached,
        compose=battery.compose,
    )


def _campaigns():
    from carbon.reconstruction.capability_registry import (
        BATTERY_CHALLENGE,
        BURGERS_CHALLENGE,
    )

    return {BURGERS_CHALLENGE: _burgers, BATTERY_CHALLENGE: _battery}


def campaign_for(challenge):
    """The campaign for a launch or manifest `challenge` ({"id", "version"}),
    resolved exactly; None is the historical Burgers campaign."""
    if challenge is None:
        return _burgers()
    if type(challenge) is not dict:
        raise TypeError("a challenge {id, version} mapping or None is required")
    entry, _ = resolve(challenge.get("id"), challenge.get("version"), CPU_RESEARCH)
    build = _campaigns().get(entry.challenge_id)
    if build is None:
        raise NoCampaignComposition(
            f"{entry.challenge_id} has no research campaign composition"
        )
    return build()


def campaign_for_manifest(manifest):
    return campaign_for(manifest.get("challenge"))
