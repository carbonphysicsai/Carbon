"""The practice identity and practice-only campaigns (LP practice-only).

Validator receipt (2026-10-23), the conditions these tests hold:
- practice-only runs research and reports only: freeze, submit, finals,
  result checks, commitments and every intake or chain path refuse
  `registration_required` at both the ledger and the runner's doors;
- the practice identity is an install-owned sr25519 key in a 0600 file,
  never logged or sent; its principal `practice:<hex>` matches no ss58 check;
- a local-practice snapshot is refused by every network-path gateway and by
  the chain reader, typed;
- nothing leaves the machine: launch -> practice under the no-outbound guard;
- registering later keeps earlier practice campaigns readable (no new work),
  and the registered path is unchanged (the existing door, runner and
  campaign suites).
"""

from __future__ import annotations

import asyncio
import base64
import json
import pickle
import re
import uuid

import pytest
from no_outbound import no_outbound

from carbon import research
from carbon.chain import practice
from carbon.chain.auth import BittensorMessageSigner
from carbon.chain.models import ChainFailure, FailureCode
from carbon.development_session import research_campaign
from carbon.development_session.practice_identity import PracticeMiner
from carbon.development_session.profile import CHALLENGE
from carbon.development_session.research_ledger import (
    CampaignLedger,
    RegistrationRequired,
)
from carbon.transport.models import TransportFailure, message
from scripts.dev.miner_launchpad import runner
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.journey_fixture import (
    FIXTURE_CHALLENGE,
    journey_host,
)
from scripts.dev.miner_launchpad.operations import perform
from scripts.dev.miner_launchpad.runner import RunnerAdapter
from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS

pytest.importorskip("bittensor")

RECIPE = {
    "schema_version": "1.0",
    "challenge_id": "burgers-dynamics-v1",
    "backbone": "fno",
    "parameters": {"steps": 64},
}


@pytest.fixture
def identity(tmp_path):
    tmp_path.chmod(0o700)
    return practice.create(tmp_path / practice.KEY_FILE)


# --- the practice identity ----------------------------------------------------------


def test_the_identity_is_an_owner_only_install_key(tmp_path, identity):
    path = tmp_path / practice.KEY_FILE
    assert path.stat().st_mode & 0o777 == 0o600
    # Made once: an existing identity is kept.
    assert practice.create(path).public_key == identity.public_key
    seed = path.read_bytes().strip().decode()
    # Never in its representation, never serialised.
    assert seed not in repr(identity) and identity.principal in repr(identity)
    with pytest.raises(TypeError):
        pickle.dumps(identity)
    with pytest.raises(TypeError):
        practice.PracticeSigner(object(), seed)
    path.chmod(0o644)
    with pytest.raises(practice.PracticeIdentityRefused) as refused:
        practice.load(path)
    assert refused.value.code == "practice_identity_not_owner_only"
    path.chmod(0o600)
    path.write_bytes(b"not a seed")
    with pytest.raises(practice.PracticeIdentityRefused) as refused:
        practice.load(path)
    assert refused.value.code == "practice_identity_malformed"
    with pytest.raises(practice.PracticeIdentityRefused) as refused:
        practice.load(tmp_path / "absent.key")
    assert refused.value.code == "practice_identity_missing"
    for code in (
        "practice_identity_missing",
        "practice_identity_not_owner_only",
        "practice_identity_malformed",
        "practice_identity_mismatch",
        "practice_campaign_read_only",
    ):
        assert code in NEXT_ACTIONS


def test_it_signs_what_the_hotkey_verifier_checks(identity):
    from bittensor.sp_core import verify

    signature = identity.sign(b"payload")
    assert verify(b"payload", signature, identity.ss58_address, identity.crypto_type)
    assert identity.publisher != identity.ss58_address


def test_the_practice_principal_matches_no_ss58_check(identity):
    from carbon.development_session.chain_onboarding import (
        OnboardingFailure,
        PublicAddress,
    )
    from scripts.dev.miner_launchpad import environment_setup

    principal = identity.principal
    assert re.fullmatch(r"practice:[0-9a-f]{64}", principal)
    assert practice.is_practice_principal(principal)
    assert not runner.RECEIVER_ADDRESS.fullmatch(principal)
    assert not environment_setup._ADDRESS.fullmatch(principal)
    with pytest.raises(OnboardingFailure):
        PublicAddress(principal)
    from bittensor.sp_core import verify

    with pytest.raises(ValueError):
        verify(b"x", b"\0" * 64, principal, identity.crypto_type)


# --- every network path refuses it ---------------------------------------------------


def test_the_chain_reader_refuses_the_local_practice_context(monkeypatch):
    from carbon.chain.sdk import BittensorReader

    with no_outbound(monkeypatch) as guard, pytest.raises(ChainFailure) as failure:
        asyncio.run(BittensorReader().capture(practice.context()))
    assert failure.value.code is FailureCode.IDENTITY
    assert guard.attempts == []
    assert practice.context().network == "local-practice"
    with pytest.raises(practice.PracticeIdentityRefused):
        practice.refuse_local_practice(practice.context())


def _signed(identity, context, snapshot_id):
    call = research.ServiceCall(
        research.RESEARCH_NAMESPACE,
        "get_challenge_info",
        research.GetChallengeInfoRequest(CHALLENGE),
    )
    body = message(
        context,
        snapshot_id,
        CHALLENGE,
        session="practice-test",
        request="request-" + uuid.uuid4().hex,
        tool=research.RESEARCH_NAMESPACE,
        fields={
            "call_base64": base64.b64encode(research.canonical_bytes(call)).decode()
        },
    )
    headers = BittensorMessageSigner(identity).sign(
        body, receiver=identity.publisher, nonce_ns=__import__("time").time_ns()
    )
    return body, headers


class Window:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    async def observe(self, *, minimum_finalized_block):
        return self.snapshot


def _network_gateway(tmp_path, snapshot, receiver):
    from carbon.chain.auth import BittensorHotkeyVerifier
    from carbon.development_session.chain_onboarding import carbon_testnet_context
    from carbon.transport.gateway import AuthenticatedGateway
    from carbon.transport.store import ReceiptJournal

    network = carbon_testnet_context()
    journal = ReceiptJournal(tmp_path / "network-transport.sqlite3", network)
    return AuthenticatedGateway(
        network,
        CHALLENGE,
        receiver,
        Window(snapshot),
        BittensorHotkeyVerifier(),
        journal,
    )


def test_a_network_gateway_refuses_local_practice_typed(tmp_path, identity):
    """The gateway every network intake builds (battery, direct recipe) on
    Carbon's network: a local-practice envelope, a local-practice snapshot,
    and the practice key on Carbon's network are each refused, typed."""
    from carbon.chain.adapter import translate
    from carbon.development_session.chain_onboarding import carbon_testnet_context

    local = practice.snapshot(identity)
    # 1. An envelope bound to the local-practice context.
    gateway = _network_gateway(tmp_path, local, identity.publisher)
    body, headers = _signed(identity, practice.context(), local.snapshot_id)
    with pytest.raises(TransportFailure) as refused:
        asyncio.run(gateway.receive(body, headers))
    assert refused.value.code.value == "TRANSPORT_CONTEXT"
    # 2. A network envelope, answered with a local-practice snapshot.
    body, headers = _signed(identity, carbon_testnet_context(), local.snapshot_id)
    with pytest.raises(TransportFailure) as refused:
        asyncio.run(gateway.receive(body, headers))
    assert refused.value.code.value == "TRANSPORT_CONTEXT"
    # 3. The practice key on Carbon's network: registered nowhere there.
    now = __import__("time").time()
    chain = translate(
        carbon_testnet_context(),
        int(now),
        "0x" + "ab" * 32,
        int(now * 1000),
        {
            "netuid": 567,
            "num_uids": 1,
            "hotkeys": [identity.publisher],
            "coldkeys": [identity.publisher],
            "block_at_registration": [1],
        },
    )
    (tmp_path / "chain").mkdir(mode=0o700)
    gateway = _network_gateway(tmp_path / "chain", chain, identity.publisher)
    body, headers = _signed(identity, carbon_testnet_context(), chain.snapshot_id)
    with pytest.raises(Exception) as refused:
        asyncio.run(gateway.receive(body, headers))
    assert "IDENTITY" in str(getattr(refused.value, "code", refused.value))


def test_a_status_read_is_refused_and_a_registered_connection_takes_no_local_context(
    tmp_path, identity
):
    from carbon.development_session.service import LocalMinerConnection

    with pytest.raises(practice.PracticeIdentityRefused) as refused:
        BittensorMessageSigner(identity).sign_status_read(
            b"{}", receiver=identity.publisher, nonce_ns=1
        )
    assert refused.value.code == "registration_required"
    session = tmp_path / "session"
    session.mkdir(mode=0o700)
    with pytest.raises(ValueError):
        LocalMinerConnection(
            session, tmp_path / "image.json", practice.context(), "5Pub", identity
        )


# --- the practice connection: signed, verified, local --------------------------------


def test_the_practice_connection_authenticates_locally_with_no_send(
    tmp_path, identity, monkeypatch
):
    from carbon.development_session.service import (
        PracticeMinerConnection,
        practice_connection,
    )

    session = tmp_path / "research-auth"
    session.mkdir(mode=0o700)
    with no_outbound(monkeypatch) as guard:
        connection = practice_connection(session, tmp_path / "image.json", identity)
        owner = asyncio.run(research_campaign.requester(connection))
        again = asyncio.run(research_campaign.requester(connection))
    assert guard.attempts == []
    assert type(owner) is str and owner == again
    assert connection.observed.value.context.network == "local-practice"
    with pytest.raises(ValueError):
        PracticeMinerConnection(
            session, tmp_path / "image.json", practice.context(), "5Other", identity
        )


# --- the ledger: research and reports only -------------------------------------------


def _practice_manifest(identity):
    return {
        "schema": "carbon.launchpad.campaign.v1",
        "authority": "MINER_LAUNCH_BUDGET",
        "campaign_id": "practice-campaign",
        "principal": identity.principal,
        "runtime": {"implementation": {"revision": "a" * 40}, "images": []},
        "admission": PracticeMiner(identity).record(),
        "agent": "none",
        "owner": "practice-owner",
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


def test_the_ledger_admits_practice_for_research_and_reports_only(tmp_path, identity):
    from carbon.development_session import research_ledger

    manifest = _practice_manifest(identity)
    research_ledger._check_product(manifest)
    ledger = CampaignLedger(tmp_path / "ledger")
    assert ledger.authority(manifest) == {
        "kind": "PRACTICE_ONLY",
        "expires_unix": None,
    }
    # A forged identity or principal is refused.
    forged = {**manifest, "principal": "practice:" + "0" * 64}
    with pytest.raises(ValueError):
        research_ledger._check_product(forged)
    assert research_ledger.PRACTICE_PHASES == {"research", "report"}
    assert RegistrationRequired().code == "registration_required"


@pytest.mark.parametrize("phase", ["final", "selection"])
def test_a_practice_campaign_reserves_research_and_never_another_phase(
    tmp_path, identity, phase
):
    from carbon.development_session.research_control import CampaignControl

    ledger = CampaignLedger(tmp_path / "campaign", clock=lambda: 1000)
    ledger.generation = CampaignControl(ledger).acquire()
    ledger.freeze(_practice_manifest(identity))
    work = {"owner": "practice-owner", "resources": {"research_trials": 1}}
    assert ledger.reserve("practice-trial", phase="research", request={"n": 1}, **work)[
        "dispatch"
    ]
    with pytest.raises(RegistrationRequired):
        ledger.reserve("needs-registration", phase=phase, request={"n": 2}, **work)


# --- the runner: profile, admission, doors -------------------------------------------


def _practice_cfg(tmp_path, identity, **extra):
    paths = {
        name: str(tmp_path / (name + ".json"))
        for name in runner.PATH_FIELDS - {"miner_public"}
    }
    paths["practice_identity"] = str(tmp_path / practice.KEY_FILE)
    return {
        "schema": runner.PROFILE_SCHEMA,
        "profile_id": "practice-profile",
        "principal": identity.principal,
        "enabled": True,
        "paths": paths,
        "accepted_revision": "a" * 40,
        "campaigns_root": str(tmp_path / "campaigns"),
        "runtime": {"implementation": {"revision": "a" * 40}, "images": []},
        "practice_identity": {
            "kind": "PRACTICE_ONLY",
            "public_key": identity.public_key.hex(),
        },
        **extra,
    }


def test_a_practice_profile_is_admitted_with_no_chain_or_signer(
    tmp_path, identity, monkeypatch
):
    cfg = _practice_cfg(tmp_path, identity)
    with pytest.raises(ValueError):
        runner.validated_profile(_practice_cfg(tmp_path, identity, intakes={}))
    with pytest.raises(ValueError):
        runner.validated_profile({**cfg, "principal": "practice:" + "1" * 64})
    with pytest.raises(ValueError):
        runner.validated_profile(
            {**cfg, "paths": {**cfg["paths"], "miner_network": "/x.json"}}
        )
    with no_outbound(monkeypatch) as guard:
        miner = runner.chain_registration(cfg)
        assert runner.signer_ready(cfg) is None
    assert guard.attempts == []
    assert type(miner) is PracticeMiner and miner.principal == identity.principal
    with pytest.raises(Rejected) as refused:
        runner.miner_hotkey(cfg)
    assert refused.value.code == "registration_required"
    other = practice.create(tmp_path / "other.key")
    with pytest.raises(Rejected) as refused:
        runner.chain_registration({**cfg, "principal": other.principal})
    assert refused.value.code == "practice_identity_mismatch"


@pytest.fixture
def practising(tmp_path, monkeypatch, identity):
    """The real campaign host for a practice-only profile: its real
    registration and signer hooks, the real practice connection and
    requester, and the real ledger and records; only the trial's training
    and the campaign's other preparation are the journey fixture's."""
    from carbon.development_session.miner_connection import campaign_connection

    base = journey_host(tmp_path, patch=monkeypatch.setattr, historical_launch=True)
    monkeypatch.setattr(RunnerAdapter, "spawn", staticmethod(lambda _: None))
    fixture_prepare = research_campaign.prepare
    owners = []

    async def prepare(args, *, ledger=None):
        path = args.root / "campaign-manifest.json"
        frozen = json.loads(path.read_bytes()) if path.exists() else None
        connection, key, config = campaign_connection(
            args, args.root, frozen=frozen, product=args.product
        )
        assert type(key) is practice.PracticeSigner and config is None
        owners.append(await research_campaign.requester(connection))
        return await fixture_prepare(args, ledger=ledger)

    monkeypatch.setattr(research_campaign, "prepare", prepare)
    practice_cfg = _practice_cfg(tmp_path, identity)
    cfg = {
        **base.configured(),
        **{k: practice_cfg[k] for k in ("principal", "paths", "practice_identity")},
    }
    host = RunnerAdapter(tmp_path / "practice.sqlite3", principal=identity.principal)
    host.configured = lambda: cfg
    host.preflight = base.preflight
    yield host, owners, cfg
    host.close()
    base.close()


def _join(host):
    for thread in list(host.threads.values()):
        thread.join(timeout=30)
        assert not thread.is_alive()


def _launch(host, **extra):
    return perform(
        host,
        "launch",
        {
            "challenge": FIXTURE_CHALLENGE["id"],
            "challenge_version": FIXTURE_CHALLENGE["version"],
            "agent": "none",
            "idempotency_key": "practice-launch-0001",
            **extra,
        },
    )


def test_practice_only_launches_and_practises_and_nothing_leaves(
    practising, monkeypatch
):
    host, owners, cfg = practising
    with no_outbound(monkeypatch) as guard:
        identity = _launch(host)["id"]
        _join(host)
        perform(
            host,
            "practice",
            {
                "campaign": identity,
                "strategy": RECIPE,
                "hypothesis": "width helps",
                "idempotency_key": "practice-key-00001",
            },
        )
        _join(host)
        view = host.get(identity)
        # Freeze, submit, commit and a result check: registration_required,
        # typed, before anything runs.
        for name, body in (
            (
                "freeze_candidate",
                {"strategy": RECIPE, "reason": "it practised well"},
            ),
            ("submit", {}),
            ("commit", {}),
            ("check_result", {}),
        ):
            with pytest.raises(Rejected) as refused:
                perform(host, name, {"campaign": identity, **body})
            assert (refused.value.code, refused.value.status) == (
                "registration_required",
                403,
            )
    assert guard.attempts == []
    assert view.get("last_refusal") is None, view.get("last_refusal")
    # Signed by the practice identity and verified, every preparation.
    assert len(owners) >= 2 and len(set(owners)) == 1
    manifest = json.loads(
        (host._bound(identity)[2] / "campaign-manifest.json").read_bytes()
    )
    assert manifest["admission"]["admission"] == "PRACTICE_ONLY"
    assert manifest["principal"] == cfg["principal"]


@pytest.mark.parametrize(
    "extra",
    [
        {"agent": "graphite"},
        {"agent": "graphite", "graphite_mode": "BUILD"},
        {"agent": "autonomous"},
    ],
)
def test_an_agent_that_would_submit_is_refused_at_launch(practising, extra):
    host, _, _ = practising
    with pytest.raises(Rejected) as refused:
        _launch(host, **extra)
    assert refused.value.code == "registration_required"


def test_registering_keeps_practice_campaigns_readable_and_takes_no_work(
    practising, tmp_path
):
    host, _, cfg = practising
    identity = _launch(host)["id"]
    _join(host)
    registered = RunnerAdapter(host.database, principal="5" + "R" * 47)
    registered.practice_principal = cfg["principal"]
    registered.configured = lambda: {
        **{k: v for k, v in cfg.items() if k != "practice_identity"},
        "principal": "5" + "R" * 47,
        "practice_principal": cfg["principal"],
    }
    registered.registration = lambda _cfg: object()
    registered.signer = None
    try:
        assert identity in [row["id"] for row in registered.recent()]
        assert registered.get(identity)["id"] == identity
        with pytest.raises(Rejected) as refused:
            perform(
                registered,
                "practice",
                {"campaign": identity, "strategy": RECIPE, "hypothesis": "h"},
            )
        assert refused.value.code == "practice_campaign_read_only"
    finally:
        registered.close()
