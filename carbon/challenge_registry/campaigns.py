"""A campaign's Challenge-specific behaviour, reached only through the registry.

The research path is one workflow. What differs by Challenge - how a campaign
is prepared, what the agent is shown first, who evaluates a frozen candidate,
how an attach re-checks the frozen binding - is a `ChallengeCampaign`, and the
only way to obtain one is `campaign_for`, which resolves the Challenge through
`registry.resolve` first. So the workflow never names a Challenge: adding one
is registering its campaign here, not threading another branch through
`research_campaign` and `standard_cli`.

There is no default Challenge. A launch must name one; a frozen campaign from
before Challenges were named is the retired Burgers campaign and is refused,
never resumed. A registered Challenge without a campaign is refused with a
typed reason, never run as another Challenge.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from .registry import CPU_RESEARCH, ChallengeRetired, ResolutionError, resolve


class ChallengeRequired(ResolutionError):
    code = "challenge_required"
    next_action = "Name the Challenge and its exact version from the catalog."


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
    #: binding changed.
    check_attached: Callable
    #: (**attach) -> (composition, wrapper)
    compose: Callable


def _manifest_challenge(manifest):
    challenge = manifest.get("challenge")
    if challenge is None:
        # Frozen before Challenges were named: the Burgers campaign.
        raise ChallengeRetired(
            "this campaign is a Burgers campaign, retired from the research path"
        )
    return challenge


def campaign_challenge(args):
    """The Challenge a campaign is bound to. The frozen manifest decides once it
    exists; before that, the launch must have named one."""
    path = args.root / "campaign-manifest.json"
    if path.exists():
        return _manifest_challenge(json.loads(path.read_bytes()))
    challenge = getattr(getattr(args, "product", None), "challenge", None)
    if challenge is None:
        raise ChallengeRequired("a campaign must name its Challenge")
    return challenge


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
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    return {BATTERY_CHALLENGE: _battery}


def campaign_for(challenge):
    """The campaign for a launch or manifest `challenge` ({"id", "version"}),
    resolved exactly."""
    if challenge is None:
        raise ChallengeRequired("a campaign must name its Challenge")
    if type(challenge) is not dict:
        raise TypeError("a challenge {id, version} mapping is required")
    entry, _ = resolve(challenge.get("id"), challenge.get("version"), CPU_RESEARCH)
    build = _campaigns().get(entry.challenge_id)
    if build is None:
        raise NoCampaignComposition(
            f"{entry.challenge_id} has no research campaign composition"
        )
    return build()


def campaign_for_manifest(manifest):
    return campaign_for(_manifest_challenge(manifest))
