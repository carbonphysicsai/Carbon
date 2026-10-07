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
    #: (manifest, *, implementation, images, julia_image) -> None; raises if
    #: the frozen binding changed. `julia_image` is the host's verified
    #: authored Julia image, or None.
    check_attached: Callable
    #: (**attach, julia_image, gpu_image, remote) -> (composition, wrapper);
    #: `remote` is `remote_runner`'s runner, or None.
    compose: Callable
    #: (root, runtime) -> the campaign's verified GPU worker image, or None
    #: when its runtime declares no GPU practice.
    gpu_image: Callable = lambda root, runtime: None
    # What the Control Center reads, so it never names a Challenge itself
    # (C-MLP-04). Each defaults to "not offered".
    #: The practice feedback modes this Challenge applies; FULL is every
    #: Challenge's default.
    feedback_modes: tuple = ("FULL",)
    #: The schema of the permitted feedback its validator returns, or None.
    feedback_schema: str | None = None
    #: (url) -> the validator intake's public facts, checked to serve this
    #: chain and Challenge; raises ValueError or OSError. None: no intake.
    intake_check: Callable | None = None
    #: (code) -> QUEUED, UNAVAILABLE or REFUSED for a closed code a submit
    #: through its intake ended with, or None for a code that is not one
    #: (LAUNCHPAD-ACCEPT-04: both doors read it back beside the refusal).
    intake_outcome: Callable | None = None
    #: (image) -> the GPU practice scope for the pinned GPU worker; None when
    #: the Challenge offers no GPU practice.
    gpu_scope: Callable | None = None
    #: (runtime) -> the declared GPU practice scope, checked for shape.
    declared_gpu: Callable | None = None
    #: (gpu image) -> the Challenge's worker on the miner's own remote setup
    #: (`carbon.compute.remote_runner.RemoteWorker`): its pinned GPU worker
    #: and the environment its GPU practice program needs there. None: the
    #: Challenge offers no remote practice (OWNER-MINER-COMPUTE-LINK-ONLY-01).
    remote_worker: Callable | None = None
    #: () -> the Challenge's research-surface declaration
    #: (`research_view.ResearchView`): its outputs by kind, practice
    #: components and per-case disclosure. None: aggregates only.
    research_view: Callable | None = None
    #: Public practice provenance emitted by this campaign, if any.
    practice_provenance: str | None = None
    #: Reconstruction backends this campaign may name in corrective feedback.
    backends: tuple = ()
    #: (record, manifest) -> the `sha256:` digest a miner commits on chain for
    #: a frozen candidate (`selected-recipe.json`) before its validator admits
    #: it (OWNER-COMMITMENT-POSTER-01). None: the Challenge uses no commitment.
    commitment: Callable | None = None
    #: (args, root, epoch) -> whether that commitment must read back on chain
    #: before this epoch's candidate is sent: its first send through the
    #: Challenge's validator intake (LAUNCHPAD-ACCEPT-02). A deployment on
    #: this machine checks its own setting; a submission the intake already
    #: holds is not gated again.
    commitment_due: Callable | None = None

    def remote_runner(self, runtime, machine, gpu_image):
        """The campaign's practice runner on the miner's own remote setup, or
        None when its runtime declares no remote practice. Both campaign
        doors call this; the route itself names no Challenge
        (`carbon.compute.remote_route`, LINKONLY-D9).

        `machine` is the runner profile's `remote_machine` and `gpu_image`
        the campaign's verified GPU worker (`gpu_image`). Nothing is reached
        until a trial runs.
        """
        from carbon.compute.remote_route import campaign_runner

        return campaign_runner(
            self, runtime=runtime, machine=machine, gpu_image=gpu_image
        )


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


class IntakeMismatch(ValueError):
    """An intake that answers, but for another chain or Challenge."""


def _battery_intake(url):
    from carbon.battery import intake_client

    facts = intake_client.read_intake(url)
    try:
        intake_client._context(facts)
        intake_client._challenge(facts)
    except intake_client.IntakeMismatch:
        raise IntakeMismatch("the intake serves another chain or Challenge") from None
    return facts


def _battery_intake_outcome(code):
    """The battery intake's outcome class for `code` (`campaign.intake_outcome`),
    or None when `code` is not one a trip through its intake reports."""
    from carbon.battery import campaign as battery
    from carbon.battery import intake_client

    known = (
        set(intake_client.REFUSALS) | battery.INTAKE_QUEUED | battery.INTAKE_UNAVAILABLE
    )
    return battery.intake_outcome(code) if code in known else None


def _battery():
    from carbon.battery import campaign as battery
    from carbon.battery import research_view as battery_view
    from carbon.development_session import battery_gpu
    from carbon.reconstruction.capability_registry import BATTERY_BACKENDS

    return ChallengeCampaign(
        key=battery.CHALLENGE,
        prepare=battery.prepare_battery,
        evaluate=battery.evaluate_frozen,
        observation=battery.agent_observation,
        refusal_retains_candidate=True,
        check_attached=battery.check_attached,
        compose=battery.compose,
        gpu_image=battery.host_gpu_image,
        # Fail closed: a campaign that declares no modes knows only FULL.
        feedback_modes=tuple(getattr(battery, "FEEDBACK_MODES", ("FULL",))),
        feedback_schema="carbon.battery.permitted-feedback.v1",
        intake_check=_battery_intake,
        intake_outcome=_battery_intake_outcome,
        gpu_scope=battery_gpu.gpu_scope,
        declared_gpu=battery_gpu.declared_scope,
        remote_worker=battery_gpu.remote_worker,
        research_view=battery_view.research_view,
        practice_provenance="BATTERY_PUBLIC_PRACTICE",
        backends=tuple(BATTERY_BACKENDS),
        commitment=battery.frozen_commitment,
        commitment_due=battery.commitment_due,
    )


def _cold_plate():
    from carbon.cold_plate import campaign as cold_plate
    from carbon.cold_plate import research_view as cold_plate_view

    return ChallengeCampaign(
        key=cold_plate.CHALLENGE,
        prepare=cold_plate.prepare_cold_plate,
        evaluate=cold_plate.evaluate_frozen,
        observation=cold_plate.agent_observation,
        refusal_retains_candidate=True,
        check_attached=cold_plate.check_attached,
        compose=cold_plate.compose,
        feedback_modes=cold_plate.FEEDBACK_MODES,
        feedback_schema=None,
        research_view=cold_plate_view.research_view,
        practice_provenance=cold_plate.PRACTICE_PROVENANCE,
        backends=cold_plate.BACKENDS,
    )


def _motor():
    from carbon.motor import campaign as motor
    from carbon.motor import research_view as motor_view

    return ChallengeCampaign(
        key=motor.CHALLENGE,
        prepare=motor.prepare_motor,
        evaluate=motor.evaluate_frozen,
        observation=motor.agent_observation,
        refusal_retains_candidate=True,
        check_attached=motor.check_attached,
        compose=motor.compose,
        feedback_modes=motor.FEEDBACK_MODES,
        feedback_schema=None,
        research_view=motor_view.research_view,
        practice_provenance=motor.PRACTICE_PROVENANCE,
        backends=motor.BACKENDS,
    )


def _campaigns():
    from carbon.reconstruction.capability_registry import (
        BATTERY_CHALLENGE,
        COLD_PLATE_CHALLENGE,
        MOTOR_CHALLENGE,
    )

    return {
        BATTERY_CHALLENGE: _battery,
        COLD_PLATE_CHALLENGE: _cold_plate,
        MOTOR_CHALLENGE: _motor,
    }


def practice_provenances():
    """Every registered campaign's public-practice result provenance."""
    values = []
    for build in _campaigns().values():
        provenance = build().practice_provenance
        if provenance is not None:
            values.append(provenance)
    return frozenset(values)


def implemented_backends():
    """Every reconstruction backend a registered campaign may name."""
    values = []
    for build in _campaigns().values():
        values.extend(build().backends)
    return frozenset(values)


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


def challenge_ref(challenge_id):
    """`{id, version}` for a registered Challenge id, at its registered
    version; the registry refuses an unknown id."""
    from .registry import entries

    for entry in entries():
        if entry.challenge_id == challenge_id:
            return {"id": challenge_id, "version": entry.version}
    return {"id": challenge_id, "version": None}


def campaign_for_id(challenge_id):
    return campaign_for(challenge_ref(challenge_id))


def implemented_campaigns():
    """`(entry, campaign)` for every IMPLEMENTED Challenge with a campaign."""
    from .registry import IMPLEMENTED, entries

    found = []
    for entry in entries():
        if entry.status == IMPLEMENTED and entry.challenge_id in _campaigns():
            found.append((entry, _campaigns()[entry.challenge_id]()))
    return found


def runtime_challenge(runtime):
    """The Challenge a runtime's GPU practice scope is bound to, or None for a
    runtime that declares no GPU practice."""
    scopes = (runtime or {}).get("gpu_research")
    if not scopes:
        return None
    if type(scopes) is not list or type(scopes[0]) is not dict:
        raise ValueError("exact GPU practice scope required")
    return scopes[0].get("challenge")


def declared_gpu(runtime):
    """The declared GPU scope, checked by the Challenge it names."""
    campaign = campaign_for_id(runtime_challenge(runtime))
    if campaign.declared_gpu is None:
        raise ValueError("this Challenge offers no GPU practice")
    return campaign.declared_gpu(runtime)


def declared_remote(runtime):
    """The declared remote GPU practice scope, checked for shape, for a
    Challenge whose campaign offers remote practice; None without one."""
    from carbon.compute.remote_route import declared_remote as shape

    scope = shape(runtime)
    if scope is None:
        return None
    declared_gpu(runtime)
    if campaign_for_id(runtime_challenge(runtime)).remote_worker is None:
        raise ValueError("this Challenge offers no remote GPU practice")
    return scope
