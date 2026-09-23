"""A product campaign: admitted by registration, controlled, and bounded only by
what its miner chose (C-MLP-02-D11).

Until this kind existed, every controlled campaign - owner-bound, fenced by
pause and stop - was a development grant campaign, so every advanced research
capability (sequences, authored Julia, GPU, public scientific tasks) could be
reached only under a grant. These tests hold the product kind to the same
control and ownership rules with no grant, no expiry and no invented limit.

The registration record in every manifest here is produced by a real
`RegisteredMiner` from a real metagraph snapshot, not written by hand.
"""

import asyncio

import pytest

from carbon.chain.models import MetagraphSnapshot, Participant
from carbon.development_session.chain_onboarding import (
    OnboardingFailure,
    PublicAddress,
    RegisteredMiner,
    carbon_testnet_context,
    registered_miner,
)
from carbon.development_session.profile import digest
from carbon.development_session.research_control import (
    CampaignControl,
    DispatchPaused,
    DispatchStopped,
)
from carbon.development_session.research_ledger import (
    PRODUCT,
    VERSION,
    CampaignLedger,
)
from carbon.development_session.research_sequences import SCOPE

HOTKEY = "5F3sa2TJAWMqDhXG6jhV4N8ko9SxwGy8TpaNS1repo5EYjQX"
OTHER = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
OWNER = "product-owner"
SCOPE_DOCUMENT = {
    "schema": SCOPE,
    "case_digests": [digest(b"first"), digest(b"second")],
}
RESOURCES = {
    "numerical_milliseconds": 720000,
    "reference_trajectories": 2,
    "reference_invocations": 2,
    "retained_bytes": 402653184,
}
CHILDREN = [
    {
        "request": {"request_digest": pin, "image": "sha256:" + "a" * 64},
        "resources": RESOURCES,
    }
    for pin in SCOPE_DOCUMENT["case_digests"]
]


def snapshot(*hotkeys):
    return MetagraphSnapshot(
        context=carbon_testnet_context(),
        finalized_block=100,
        block_hash="0x" + "cd" * 32,
        timestamp_ms=1,
        participants=tuple(
            Participant(uid=i, hotkey=h, coldkey="5" + "C" * 47, registered_at=10)
            for i, h in enumerate(hotkeys)
        ),
    )


def admission():
    return RegisteredMiner(snapshot(HOTKEY), PublicAddress(HOTKEY)).record()


def manifest(**changes):
    value = {
        "schema": PRODUCT,
        "campaign_id": "product-fixture",
        "principal": "alice",
        "owner": OWNER,
        "runtime": {"implementation": "fixture", "scientific_tasks": [SCOPE_DOCUMENT]},
        "admission": admission(),
        **dict.fromkeys(
            (
                "implementation",
                "objective",
                "sampling",
                "control",
                "selection",
                "replica_policy",
                "provider",
            ),
            "fixture",
        ),
    }
    value.update(changes)
    return {k: v for k, v in value.items() if v is not None}


def product(tmp_path, **changes):
    tmp_path.chmod(0o700)
    ledger = CampaignLedger(tmp_path / "campaign", clock=lambda: 1000)
    ledger.generation = CampaignControl(ledger).acquire()
    ledger.freeze(manifest(**changes))
    return ledger


# --- registration is constructed, not checked --------------------------------


def test_a_registered_hotkey_becomes_a_registered_miner():
    miner = RegisteredMiner(snapshot(OTHER, HOTKEY), PublicAddress(HOTKEY))
    assert (miner.hotkey, miner.uid, miner.observed_block) == (HOTKEY, 1, 100)
    assert miner.record()["admission"] == "SUBNET_REGISTRATION"


def test_a_valid_address_that_is_not_registered_is_refused():
    """The specimen above is the same construction with the hotkey present."""
    with pytest.raises(OnboardingFailure) as refused:
        RegisteredMiner(snapshot(OTHER), PublicAddress(HOTKEY))
    assert refused.value.reason == "NOT_REGISTERED"


def test_a_bare_string_or_a_look_alike_observation_is_refused():
    """Valid values that did not come through validation or the chain read."""
    with pytest.raises(TypeError):
        RegisteredMiner(snapshot(HOTKEY), HOTKEY)

    class LooksLikeASnapshot:
        def resolve(self, hotkey):
            return object()

    with pytest.raises(TypeError):
        RegisteredMiner(LooksLikeASnapshot(), PublicAddress(HOTKEY))


def test_the_admission_read_is_the_status_read():
    class Reader:
        async def capture(self, context):
            return snapshot(HOTKEY)

    miner = asyncio.run(registered_miner(Reader(), carbon_testnet_context(), HOTKEY))
    assert miner.hotkey == HOTKEY
    with pytest.raises(AttributeError):
        miner.uid = 7


# --- a product campaign is controlled, with no grant ---------------------------


def test_a_product_campaign_has_authority_without_a_grant_or_expiry(tmp_path):
    ledger = product(tmp_path)
    frozen = ledger.status(owner=OWNER)
    assert frozen["budget"] is None
    authority = ledger.authority(manifest())
    assert authority == {"kind": "SUBNET_REGISTRATION", "expires_unix": None}


def test_a_product_manifest_must_record_its_registration(tmp_path):
    tmp_path.chmod(0o700)
    ledger = CampaignLedger(tmp_path / "campaign")
    for broken in (
        manifest(admission=None),
        manifest(admission={**admission(), "admission": "DEVELOPMENT_GRANT"}),
        manifest(admission={**admission(), "extra": True}),
        manifest(grant={"path": "/x", "digest": "sha256:0"}),
    ):
        with pytest.raises(ValueError, match="product campaign"):
            ledger.freeze(broken)


def test_the_development_cli_campaign_is_still_not_controlled(tmp_path):
    """VERSION has no control surface; it must not acquire authority by accident."""
    ledger = product(tmp_path)
    assert ledger.controlled(manifest())
    assert not ledger.controlled({**manifest(), "schema": VERSION})
    with pytest.raises(ValueError, match="controlled campaign authority required"):
        ledger.authority({**manifest(), "schema": VERSION})


def test_owner_binding_and_control_fencing_apply_to_a_product_campaign(tmp_path):
    ledger = product(tmp_path)
    with pytest.raises(ValueError, match="owner differs"):
        ledger.reserve(
            "someone-elses",
            owner="bob",
            phase="research",
            request={"n": 1},
            resources={"research_trials": 1},
        )
    specimen = ledger.reserve(
        "own-work",
        owner=OWNER,
        phase="research",
        request={"n": 1},
        resources={"research_trials": 1},
    )
    assert specimen["dispatch"] is True
    control = CampaignControl(ledger)
    control.request("stop")
    with pytest.raises(DispatchStopped):
        ledger.reserve(
            "after-stop",
            owner=OWNER,
            phase="research",
            request={"n": 2},
            resources={"research_trials": 1},
        )


def test_with_no_elapsed_budget_a_worker_has_no_wall_clock_to_fit(tmp_path):
    """Before this, `now + worker > deadline` compared against None and raised."""
    ledger = product(tmp_path)
    reserved = ledger.reserve(
        "worker",
        owner=OWNER,
        phase="research",
        request={"n": 1},
        resources={"numerical_milliseconds": 720000},
    )
    assert reserved["dispatch"] is True


def test_a_budget_the_miner_set_binds_a_product_campaign(tmp_path):
    ledger = product(tmp_path, ceilings={"research_trials": 1})
    ledger.reserve(
        "first",
        owner=OWNER,
        phase="research",
        request={"n": 1},
        resources={"research_trials": 1},
    )
    with pytest.raises(ValueError, match="miner budget: research_trials"):
        ledger.reserve(
            "second",
            owner=OWNER,
            phase="research",
            request={"n": 2},
            resources={"research_trials": 1},
        )


def test_an_elapsed_budget_the_miner_set_is_a_deadline(tmp_path):
    clock = [1000]
    tmp_path.chmod(0o700)
    ledger = CampaignLedger(tmp_path / "campaign", clock=lambda: clock[0])
    ledger.generation = CampaignControl(ledger).acquire()
    ledger.freeze(manifest(elapsed_seconds=60))
    ledger.reserve(
        "early",
        owner=OWNER,
        phase="research",
        request={"n": 1},
        resources={"research_trials": 1},
    )
    clock[0] = 1061
    with pytest.raises((ValueError, DispatchStopped)):
        ledger.reserve(
            "late",
            owner=OWNER,
            phase="research",
            request={"n": 2},
            resources={"research_trials": 1},
        )


def test_a_product_campaign_never_consumes_a_development_grant(tmp_path):
    from carbon.development_session.research_admission import Admission

    ledger = product(tmp_path)
    ledger.admission = object.__new__(Admission)
    with pytest.raises(ValueError):
        ledger.authority(manifest())


# --- retained ownership and the research capabilities -----------------------


def test_retained_ownership_is_the_manifest_owner_and_generation(tmp_path):
    ledger = product(tmp_path)
    assert ledger.retained_owner(OWNER)["owner"] == OWNER
    with pytest.raises(ValueError, match="ownership changed"):
        ledger.retained_owner("bob")
    ledger.generation = ledger.generation + 1
    with pytest.raises(ValueError, match="ownership changed"):
        ledger.retained_owner(OWNER)


def test_a_product_campaign_reaches_sequences_with_no_grant_and_no_deadline(tmp_path):
    """The capability that was grant-only, reached by registration alone."""
    ledger = product(tmp_path)
    reserved = ledger.reserve_sequence(
        "sequence", owner=OWNER, scope=SCOPE_DOCUMENT, children=CHILDREN
    )
    assert reserved["dispatch"] is True
    control = CampaignControl(ledger)
    control.request("pause")
    with pytest.raises(DispatchPaused):
        ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=0)


def test_a_product_campaign_reaches_authored_julia_with_its_scope(tmp_path):
    from carbon.development_session import julia_analysis as julia
    from carbon.development_session.profile import canonical
    from carbon.development_session.research_image import ResearchImageIdentity

    parent = ResearchImageIdentity(
        "sha256:" + "a" * 64, "sha256:" + "b" * 64, "sha256:" + "c" * 64
    )
    image = julia.JuliaResearchImageIdentity(
        "sha256:" + "d" * 64, parent, digest(canonical(julia.runtime_document(parent)))
    )
    ledger = product(
        tmp_path,
        runtime={
            "implementation": "fixture",
            "authored_research": [julia.authored_julia_scope(image)],
        },
    )
    julia.authorize_julia(ledger, OWNER, image)
    with pytest.raises(ValueError, match="authored Julia scope"):
        julia.authorize_julia(ledger, "bob", image)
