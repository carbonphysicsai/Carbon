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

import functools
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
    #: Optional prospective multi-validator feedback and partial-status file.
    multi_feedback_schema: str | None = None
    multi_feedback_status: str | None = None
    #: (code) -> closed transport refusal code, owned by this campaign.
    intake_code: Callable | None = None
    #: () -> validated public unified construction contract, or not offered.
    construction_contract: Callable | None = None
    #: () -> prospective Challenge-owned construction kit and limits digest.
    #: five-field direct recipe identity; None means this path is unserved.
    construction_kit: Callable | None = None
    #: Exact direct-recipe reconstruction operation. Absence means the new
    #: public path is unserved even when a Challenge can describe its kit.
    construction_reconstruct: Callable | None = None
    #: () -> Challenge-owned public TRAIN, input and output material for the
    #: shared isolated source-bundle worker. None means bundle practice is
    #: unserved; this is a task adapter, never a backbone permission list.
    construction_bundle_material: Callable | None = None
    #: (strategy, level binding) -> public, non-blocking construction notices.
    construction_notices: Callable | None = None
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
    #: (args, root, epoch, connect) -> the permitted feedback when one read of
    #: the epoch's queued submission at its validator intake finds a verdict,
    #: else None (LA-F18). Read-only: signed through the signer's read-only
    #: kind, throttled per epoch; nothing is submitted or committed.
    #: `connect()` reaches the miner's signer once a read is due. None: the
    #: Challenge offers no such read.
    queued_verdict: Callable | None = None
    #: (ledger, owner, epoch, feedback) -> None: store a verdict exactly as
    #: its `evaluate` stores a submit's. Set with `queued_verdict`.
    record_verdict: Callable | None = None
    #: Whether this campaign compiles, freezes and commits at a construction
    #: level its launch names (LAUNCHPAD-LEVELS-01 S2,
    #: `carbon.development_session.construction_level`). False: a launch at
    #: any level above 0 is refused, never silently run at Level 0.
    construction_levels: bool = False
    #: (intake facts) -> whether that intake takes a Level 4 submission's
    #: envelope in signed parts (LAUNCHPAD-LEVELS-01 S4). None: the Challenge
    #: has no Level 4 envelope transport, so Level 4 is refused (fail closed).
    level4_parts: Callable | None = None
    #: () -> the Challenge's smoke practice hook
    #: (`development_session.smoke_practice.SmokeHook`): how a smoke practice
    #: truncates its recipe and judges its result (LAUNCHPAD-SMOKE-PRACTICE-01).
    #: None: smoke practice is refused `smoke_practice_unavailable`.
    smoke_practice: Callable | None = None

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
    from carbon.battery import construction_kit as battery_construction_kit
    from carbon.battery import direct_graph_worker as battery_direct_graph_worker
    from carbon.battery import level4_parts as battery_level4
    from carbon.battery import multi_intake as battery_multi
    from carbon.battery import research_view as battery_view
    from carbon.battery import smoke_practice as battery_smoke
    from carbon.battery import unified_contract as battery_unified
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
        multi_feedback_schema=battery_multi.SCHEMA,
        multi_feedback_status=battery_multi.STATUS_NAME,
        intake_code=battery.intake_code,
        construction_contract=battery_unified.contract,
        construction_kit=battery_construction_kit.construction_kit,
        construction_reconstruct=battery_direct_graph_worker.reconstruct_public,
        construction_notices=battery.construction_notices,
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
        queued_verdict=battery.queued_verdict,
        record_verdict=battery.record_verdict,
        construction_levels=True,
        level4_parts=battery_level4.carries_parts,
        smoke_practice=battery_smoke.hook,
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


def _catalog_gpu(key):
    """The one shared GPU practice hooks of a catalog campaign (S3,
    `development_session.catalog_gpu`), with its remote GPU worker (S4): the
    same for every Challenge."""
    from carbon.development_session import catalog_gpu

    return {
        "gpu_image": lambda root, runtime: catalog_gpu.registered_gpu_image(
            root, runtime, key.challenge_id
        ),
        "gpu_scope": lambda image: catalog_gpu.gpu_scope(key.challenge_id, image),
        "declared_gpu": catalog_gpu.declared_scope,
        "remote_worker": catalog_gpu.remote_worker,
    }


def _motor_catalog(version="1.2"):
    """A Motor catalog version (OWNER-BACKBONE-CATALOG-01): Carbon's tested
    backbones by catalog id on the direct recipe path; 1.3 is 1.2 plus
    allowlist v7. Each hook runs under that version's research key, so Motor's
    shared campaign code serves exactly that version."""
    from carbon.challenge_kit import physical_material, physical_public
    from carbon.development_session import direct_submission
    from carbon.motor import campaign as motor
    from carbon.motor import research_view as motor_view
    from carbon.motor.contracts import key_for, keyed

    if version not in motor.CATALOG_VERSIONS:
        raise ValueError("motor catalog version required")
    key = key_for(version)

    def bound(function):
        @functools.wraps(function)
        def call(*args, **kwargs):
            with keyed(key):
                return function(*args, **kwargs)

        return call

    def bound_async(function):
        @functools.wraps(function)
        async def call(*args, **kwargs):
            with keyed(key):
                return await function(*args, **kwargs)

        return call

    def intake(url):
        facts = direct_submission.read_intake(url)
        return facts

    return ChallengeCampaign(
        key=key,
        prepare=bound_async(motor.prepare_motor),
        evaluate=bound_async(motor.evaluate_frozen),
        observation=bound(motor.agent_observation),
        refusal_retains_candidate=True,
        check_attached=bound(motor.check_attached),
        compose=bound(motor.compose),
        feedback_modes=motor.FEEDBACK_MODES,
        feedback_schema="carbon.motor.permitted-feedback.v1",
        research_view=motor_view.research_view,
        practice_provenance=motor.PRACTICE_PROVENANCE,
        backends=("torch_cpu",),
        construction_kit=lambda: physical_public.construction_kit(
            key.challenge_id, key.version
        ),
        construction_reconstruct=lambda *args, **kwargs: None,
        **_catalog_gpu(key),
        construction_bundle_material=lambda: physical_material.bundle_material(
            key.challenge_id, key.version
        ),
        intake_check=intake,
        record_verdict=motor.record_verdict,
    )


def _cold_plate_catalog(version):
    """A Cooling catalog version (OWNER-BACKBONE-CATALOG-01, as Motor's):
    Carbon's tested backbones by catalog id on the direct recipe path. Each
    hook runs under that version's research key, so Cooling's shared campaign
    code serves exactly that version. Practice reuses Cooling's practice
    provenance, so a practised catalog recipe supports a freeze."""
    from carbon.challenge_kit import physical_material, physical_public
    from carbon.cold_plate import campaign as cold_plate
    from carbon.cold_plate import research_view as cold_plate_view
    from carbon.cold_plate.contracts import key_for, keyed
    from carbon.development_session import direct_submission

    if version not in cold_plate.CATALOG_VERSIONS:
        raise ValueError("cooling catalog version required")
    key = key_for(version)

    def bound(function):
        @functools.wraps(function)
        def call(*args, **kwargs):
            with keyed(key):
                return function(*args, **kwargs)

        return call

    def bound_async(function):
        @functools.wraps(function)
        async def call(*args, **kwargs):
            with keyed(key):
                return await function(*args, **kwargs)

        return call

    return ChallengeCampaign(
        key=key,
        prepare=bound_async(cold_plate.prepare_cold_plate),
        evaluate=bound_async(cold_plate.evaluate_frozen),
        observation=bound(cold_plate.agent_observation),
        refusal_retains_candidate=True,
        check_attached=bound(cold_plate.check_attached),
        compose=bound(cold_plate.compose),
        feedback_modes=cold_plate.FEEDBACK_MODES,
        feedback_schema="carbon.cold-plate.permitted-feedback.v1",
        research_view=cold_plate_view.research_view,
        practice_provenance=cold_plate.PRACTICE_PROVENANCE,
        backends=("torch_cpu",),
        construction_kit=lambda: physical_public.construction_kit(
            key.challenge_id, key.version
        ),
        construction_reconstruct=lambda *args, **kwargs: None,
        **_catalog_gpu(key),
        construction_bundle_material=lambda: physical_material.bundle_material(
            key.challenge_id, key.version
        ),
        intake_check=direct_submission.read_intake,
        record_verdict=cold_plate.record_verdict,
    )


def _direct(campaign, view, contracts, version):
    """A direct-recipe-only version (F08 1.4, F02 2.3, Battery 2.2;
    `carbon.direct_campaign`):
    catalog or graph recipes on the direct recipe path, as the catalog versions
    above. Each hook runs under that version's research key. Practice carries
    the Challenge's own provenance (`versioned_practice_provenances`), so a
    practised recipe supports a freeze."""
    from carbon.challenge_kit import physical_material
    from carbon.development_session import direct_submission

    key = contracts.key_for(version)

    def bound(function):
        @functools.wraps(function)
        def call(*args, **kwargs):
            with contracts.keyed(key):
                return function(*args, **kwargs)

        return call

    def bound_async(function):
        @functools.wraps(function)
        async def call(*args, **kwargs):
            with contracts.keyed(key):
                return await function(*args, **kwargs)

        return call

    spec = contracts.SPEC
    return ChallengeCampaign(
        key=key,
        prepare=bound_async(getattr(campaign, "prepare_" + spec.prefix)),
        evaluate=bound_async(campaign.evaluate_frozen),
        observation=bound(campaign.agent_observation),
        refusal_retains_candidate=True,
        check_attached=bound(campaign.check_attached),
        compose=bound(campaign.compose),
        feedback_modes=campaign.FEEDBACK_MODES,
        feedback_schema=spec.feedback_schema,
        research_view=bound(view.research_view),
        practice_provenance=campaign.PRACTICE_PROVENANCE,
        backends=campaign.BACKENDS,
        construction_kit=lambda: spec.public().construction_kit(
            key.challenge_id, key.version
        ),
        construction_reconstruct=lambda *args, **kwargs: None,
        **_catalog_gpu(key),
        construction_bundle_material=lambda: physical_material.bundle_material(
            key.challenge_id, key.version
        ),
        intake_check=direct_submission.read_intake,
        record_verdict=campaign.record_verdict,
    )


def _f08_direct(version):
    from carbon.f08 import campaign, contracts, research_view

    return _direct(campaign, research_view, contracts, version)


def _f02_direct(version):
    from carbon.f02 import campaign, contracts, research_view

    return _direct(campaign, research_view, contracts, version)


def _battery_catalog_direct(version):
    """Battery 2.2 (the Validator, 2026-10-22): 2.1 plus the catalog binding,
    catalog recipes only. One module binds the key, hooks and view."""
    from carbon.battery import catalog_campaign

    return _direct(catalog_campaign, catalog_campaign, catalog_campaign, version)


def _versioned_campaigns():
    """Campaigns registered for a Challenge version beyond its first, by
    (Challenge id, version)."""
    from carbon.challenge_kit import version_registry
    from carbon.reconstruction.capability_registry import (
        COLD_PLATE_CHALLENGE,
        MOTOR_CHALLENGE,
    )

    # Every catalog campaign the version registry declares (Motor 1.2 keeps its
    # one-argument default).
    return {
        **{
            (MOTOR_CHALLENGE, version): (
                _motor_catalog
                if version == "1.2"
                else functools.partial(_motor_catalog, version)
            )
            for version in version_registry.versions(
                MOTOR_CHALLENGE, campaign="catalog"
            )
        },
        **{
            (COLD_PLATE_CHALLENGE, version): functools.partial(
                _cold_plate_catalog, version
            )
            for version in version_registry.versions(
                COLD_PLATE_CHALLENGE, campaign="catalog"
            )
        },
        **_direct_campaigns(),
    }


def _direct_campaigns():
    """The direct-recipe-only versions: their Challenges have no id-level
    campaign (no Level-0 version), so each is registered by version only."""
    from carbon.challenge_kit import version_registry

    builders = {"f08-ribbed-bracket": _f08_direct, "f02": _f02_direct}
    return {
        (challenge, version): functools.partial(builder, version)
        for challenge, builder in builders.items()
        for version in version_registry.versions(challenge, campaign="direct")
    } | {
        # Battery has an id-level campaign (1.0); its catalog version 2.2 is
        # registered by version and reuses Battery's practice provenance.
        ("battery-fastcharge-ageing-development-v1", version): functools.partial(
            _battery_catalog_direct, version
        )
        for version in version_registry.versions(
            "battery-fastcharge-ageing-development-v1", campaign="battery_catalog"
        )
    }


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


def _provenance_sources():
    """The campaigns whose practice provenance and backends count: every
    id-level campaign, and each version-keyed campaign of a Challenge with no
    id-level one (F08 1.4, F02 2.3), whose provenance no other campaign
    declares. A versioned campaign of a Challenge with an id-level campaign
    (Motor 1.2/1.3, Cooling 1.2) reuses that one's provenance, so the sets are
    exactly what they were for those Challenges."""
    with_id = set(_campaigns())
    return [
        *_campaigns().values(),
        *(
            build
            for (challenge_id, _), build in _versioned_campaigns().items()
            if challenge_id not in with_id
        ),
    ]


def practice_provenances():
    """Every registered campaign's public-practice result provenance."""
    values = []
    for build in _provenance_sources():
        provenance = build().practice_provenance
        if provenance is not None:
            values.append(provenance)
    return frozenset(values)


def implemented_backends():
    """Every reconstruction backend a registered campaign may name."""
    values = []
    for build in _provenance_sources():
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
    campaign = _composed_for(entry)
    if campaign is None:
        raise NoCampaignComposition(
            f"{entry.challenge_id} {entry.version} has no research campaign composition"
        )
    return campaign


def _composed_for(entry):
    """The campaign composed for exactly `entry`'s version, or None. A campaign
    serves the version its own key names; another registered version of the
    same Challenge has no composition until one is registered for it."""
    from .registry import entries

    build = _versioned_campaigns().get((entry.challenge_id, entry.version))
    if build is not None:
        return build()
    build = _campaigns().get(entry.challenge_id)
    if build is None:
        return None
    campaign = build()
    # The id-level campaign belongs to the version its key names; it never
    # serves another registered version of the same Challenge.
    owned_elsewhere = campaign.key.version != entry.version and any(
        other.challenge_id == entry.challenge_id
        and other.version == campaign.key.version
        for other in entries()
    )
    return None if owned_elsewhere else campaign


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
        if entry.status == IMPLEMENTED:
            campaign = _composed_for(entry)
            if campaign is not None:
                found.append((entry, campaign))
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
    from carbon.development_session import catalog_gpu

    scopes = runtime.get(catalog_gpu.RUNTIME_KEY) if type(runtime) is dict else None
    if (
        type(scopes) is list
        and scopes
        and type(scopes[0]) is dict
        and scopes[0].get("schema") == catalog_gpu.SCOPE_SCHEMA
    ):
        # A catalog campaign's shared scope, whatever its Challenge or version.
        return catalog_gpu.declared_scope(runtime)
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
    from carbon.development_session import catalog_gpu

    if declared_gpu(runtime)[0].get("schema") == catalog_gpu.SCOPE_SCHEMA:
        # A catalog campaign's shared scope: every catalog version offers
        # remote practice through the shared remote worker (S4).
        return scope
    if campaign_for_id(runtime_challenge(runtime)).remote_worker is None:
        raise ValueError("this Challenge offers no remote GPU practice")
    return scope
