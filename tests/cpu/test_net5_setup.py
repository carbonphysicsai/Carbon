"""Localnet isolation/fixture contracts; runtime results have a separate lane."""

import asyncio
import copy
import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.chain.localnet import (
    DIGEST,
    IMAGE,
    ROOT_SETTINGS,
    STARTUP,
    inspect_isolation,
    root_setting,
)
from carbon.chain.publication import PublicationFailure
from carbon.traineval import FixtureStubProfile
from carbon.traineval.model import FixtureRunRequestError


def docker_state():
    item = {
        "Id": "disposable-id",
        "Config": {
            "Image": IMAGE + "@" + DIGEST,
            "Entrypoint": ["/bin/bash"],
            "Cmd": ["-c", STARTUP],
            "Labels": {"carbon.scope": "disposable-localnet"},
        },
        "State": {"Running": True},
        "HostConfig": {"Privileged": False},
        "Mounts": [],
        "NetworkSettings": {
            "Networks": {"internal": {"IPAddress": "172.18.0.2"}},
            "Ports": {
                "9944/tcp": [{"HostIp": "127.0.0.1", "HostPort": "40001"}],
                "9945/tcp": [{"HostIp": "127.0.0.1", "HostPort": "40002"}],
                "30333/tcp": None,
            },
        },
    }
    network = {"Id": "internal-id", "Internal": True, "Containers": {item["Id"]: {}}}
    return item, network


def test_runtime_diagnostic_log_distinguishes_shield_decryption_failures():
    assert "basic-authorship=debug" in STARTUP
    assert "mev-shield=debug" in STARTUP
    assert "pallet-shield=debug" in STARTUP


@pytest.mark.parametrize(
    "defect",
    [None, "public-port", "bridge", "other-container", "image", "mount", "privileged"],
)
def test_docker_isolation_is_derived_and_fails_closed(monkeypatch, defect):
    item, network = docker_state()
    if defect == "public-port":
        item["NetworkSettings"]["Ports"]["9944/tcp"][0]["HostIp"] = "0.0.0.0"
    elif defect == "bridge":
        network["Internal"] = False
    elif defect == "other-container":
        network["Containers"]["unrelated"] = {}
    elif defect == "image":
        item["Config"]["Image"] = IMAGE + ":latest"
    elif defect == "mount":
        item["Mounts"] = [{"Source": "/valuable/keys"}]
    elif defect == "privileged":
        item["HostConfig"]["Privileged"] = True

    def run(command, **kwargs):
        assert command[0] == "docker" and kwargs["timeout"] == 15
        return SimpleNamespace(
            stdout=json.dumps([network if command[1] == "network" else item])
        )

    monkeypatch.setattr("carbon.chain.localnet.subprocess.run", run)
    if defect:
        with pytest.raises(PublicationFailure):
            inspect_isolation("carbon-localnet-test")
    else:
        proof = inspect_isolation("carbon-localnet-test")
        assert proof["endpoints"] == ["ws://127.0.0.1:40001", "ws://127.0.0.1:40002"]
        assert proof["scope"] == "DISPOSABLE_LOCALNET_ONLY"


def test_fixed_additional_fixtures_have_exact_pins_and_unchanged_science():
    root = Path(__file__).parents[1] / "fixtures" / "score_packs"
    original = json.loads((root / "a5_fixture_v1.json").read_text())
    for suffix in ("b", "c"):
        name = "a5_fixture_net5_" + suffix
        profile = FixtureStubProfile(localnet_fixture=name)
        # Git text line endings are normalized for this cross-host diagnostic.
        data = (root / (name + "_v1.json")).read_text().encode()
        assert profile.scoring_digest == "sha256:" + hashlib.sha256(data).hexdigest()
        document = json.loads(data)
        assert document.pop("challenge_id") == name
        comparison = copy.deepcopy(original)
        comparison.pop("challenge_id")
        assert document == comparison
        assert profile.score_pack_pin().fixture_origin is True


@pytest.mark.parametrize("value", ["live", "a5_fixture", "arbitrary", 1, {}, False])
def test_fixture_extension_cannot_select_arbitrary_scientific_profiles(value):
    with pytest.raises(FixtureRunRequestError):
        FixtureStubProfile(localnet_fixture=value)


def test_installed_sdk_local_settings_are_closed_and_root_wrapped():
    from test_net1_chain_adapter import installed_sdk

    installed_sdk()
    calls = []

    async def verify():
        calls.append("verify")

    class Sub:
        async def compose(self, call):
            calls.append(call)
            return call

    for action, (method, _) in ROOT_SETTINGS.items():
        intent = root_setting(action, verify)
        assert intent.origin == "root" and intent.netuid == 2
        call = asyncio.run(intent.build(Sub(), None))
        assert (
            calls[-2] == "verify"
            and call.module == "AdminUtils"
            and call.function == method
        )
    with pytest.raises(PublicationFailure):
        root_setting("set-unchecked-weights", verify)


def test_duplicate_challenge_version_is_already_rejected_by_candidate_owner(tmp_path):
    from test_reward_ledger import initialized
    from test_traineval_stub import _limits

    from carbon.candidates.model import CandidateFailure
    from carbon.candidates.store import CandidateJournal

    _, first, _, _ = initialized(tmp_path)
    with pytest.raises(CandidateFailure, match="CANDIDATE_CONFLICT"):
        CandidateJournal(
            first.receipts,
            replace(
                first.context,
                environment=replace(
                    first.context.environment, container_digest="sha256:" + "4" * 64
                ),
            ),
            _limits(),
        )


@pytest.mark.skipif(
    os.name == "nt",
    reason="A3 secure descriptor-relative fixture registry needs canonical Linux",
)
def test_all_registered_exam_variants_use_existing_a7_a8_acceptance(tmp_path):
    from net5_fixture_support import Exam
    from test_net2_transport import CONTEXT, Adapter, FakeVerifier, headers, snapshot

    from carbon.transport.store import ReceiptJournal

    async def exercise():
        receipts = ReceiptJournal(tmp_path / "receipts.sqlite", CONTEXT)
        adapter = Adapter(snapshot())
        for suffix in (None, "b", "c"):
            exam = Exam(
                tmp_path / (suffix or "a"),
                receipts,
                adapter,
                "validator",
                FakeVerifier(),
                suffix,
            )
            accepted = []
            for variant in range(8):
                ref = await exam.commit(
                    variant,
                    lambda body, now, hotkey: headers(body, now, hotkey),
                    hotkey="miner",
                )
                result = exam.evaluate(ref)
                if result:
                    accepted.append(result)
                    assert (
                        result.challenge_id == exam.profile.challenge_key.challenge_id
                    )
                    assert exam.journal.resolve_accepted_fixture(ref) == result
            assert (
                accepted
            ), "Fixed synthetic fixture must produce at least one admitted score"

    asyncio.run(exercise())


def test_process_relay_cannot_be_supplied_as_an_unverified_endpoint(monkeypatch):
    import carbon.chain.localnet as module

    item, network = docker_state()
    item["NetworkSettings"]["Ports"] = {}
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda cmd, **kw: SimpleNamespace(
            stdout=json.dumps([network if cmd[1] == "network" else item])
        ),
    )
    with pytest.raises(PublicationFailure, match="LOOPBACK_RPC_REQUIRED"):
        inspect_isolation("carbon-localnet-test")
    proof = module._inspect_container("carbon-localnet-test")
    proof.pop("ports")
    server = SimpleNamespace(
        is_serving=lambda: True,
        sockets=[SimpleNamespace(getsockname=lambda: ("127.0.0.1", 40001))],
    )
    monkeypatch.setattr(module, "_ACTIVE_RELAY", (proof, [server, server]))
    assert (
        inspect_isolation("carbon-localnet-test")["transport"]
        == "PROCESS_LOOPBACK_RELAY"
    )
    item["Id"] = "replaced-container"
    network["Containers"] = {item["Id"]: {}}
    with pytest.raises(PublicationFailure, match="RELAY_CONTAINER_CHANGED"):
        inspect_isolation("carbon-localnet-test")


@pytest.mark.parametrize("value", [0, 2**32, {"bits": 2**31}])
def test_miner_burned_pinned_fixed_point_decoding(value):
    from carbon.chain.localnet import miner_burned_q32

    assert miner_burned_q32(value) == (value["bits"] if type(value) is dict else value)


@pytest.mark.parametrize(
    "value", [True, 0.5, -1, 2**32 + 1, {"fraction": 1}, {"bits": 1, "extra": 0}]
)
def test_unknown_burn_measurement_never_becomes_success(value):
    from carbon.chain.localnet import miner_burned_q32

    with pytest.raises(PublicationFailure, match="UNSUPPORTED_MINER_BURNED_ENCODING"):
        miner_burned_q32(value)


def test_installed_sdk_inner_signing_checks_identity_before_key_use():
    from test_net1_chain_adapter import context, installed_sdk

    installed_sdk()
    from bittensor._transport.contract import CallBytes, SignedExtrinsic
    from bittensor.keyfiles import Keypair

    from carbon.chain.sdk_weights import journaled_substrate

    order = []
    blocked = True

    async def guard(call, signer):
        order.append("guard")
        if blocked:
            raise PublicationFailure("ENDPOINT_GENESIS_MISMATCH")

    async def journal(tx_hash):
        pytest.fail("An inner signature is not an outer dispatch")

    class Raw:
        async def create_signed_extrinsic(self, call, keypair, **kwargs):
            assert order[-1] == "guard" and kwargs == {
                "nonce": 1,
                "era": {"period": 64},
            }
            order.append("sign")
            return SignedExtrinsic(b"synthetic", "0x" + "a" * 64)

    sub = journaled_substrate(context(), guard, journal)
    sub._substrate = (
        Raw()
    )  # Installed SDK contract with a deterministic transport double.
    key = Keypair.create_from_uri("//Alice")
    call = CallBytes(b"fixture", 445)
    with pytest.raises(PublicationFailure, match="ENDPOINT_GENESIS_MISMATCH"):
        asyncio.run(sub.sign_extrinsic(call, key, nonce=1, period=64))
    assert order == ["guard"]
    blocked = False
    assert asyncio.run(sub.sign_extrinsic(call, key, nonce=1, period=64)) == (
        b"synthetic",
        "0x" + "a" * 64,
    )
    assert order == ["guard", "guard", "sign"]


def test_pinned_sdk_and_runtime_manifest_agree_on_shield_mortality():
    from test_net1_chain_adapter import installed_sdk

    installed_sdk()
    from bittensor.settings import MEV_SHIELD_ERA_PERIOD

    from carbon.chain.sdk_weights import require_shield_era_period

    manifest = json.loads(
        (Path(__file__).parents[2] / "scripts/dev/localnet-runtime.json").read_text()
    )
    assert MEV_SHIELD_ERA_PERIOD == require_shield_era_period() == 8
    assert manifest["development"]["shield_era_blocks"] == 8
    assert (
        "MAX_SHIELD_ERA_PERIOD=8" in manifest["development"]["shield_mortality_source"]
    )


def test_shield_diagnostics_bind_key_nonce_and_era_before_signing():
    from test_net1_chain_adapter import context, installed_sdk

    installed_sdk()
    from bittensor._transport.contract import CallBytes, SignedExtrinsic
    from bittensor.keyfiles import Keypair

    from carbon.chain.sdk_weights import journaled_substrate

    observed = []

    async def guard(call, signer):
        observed.append(("guard", signer))

    async def journal(tx_hash):
        pass

    async def key(digest, length):
        observed.append(("key", digest, length))

    async def signing(kind, kwargs):
        observed.append((kind, kwargs["nonce"], kwargs["period"]))

    class Raw:
        async def query(self, module, item, params, block_hash):
            assert (module, item, params, block_hash) == (
                "MevShield",
                "NextKey",
                [],
                None,
            )
            return bytes(range(256)) * 4 + bytes(range(160))

        async def create_signed_extrinsic(self, call, keypair, **kwargs):
            return SignedExtrinsic(b"synthetic", "0x" + "a" * 64)

    sub = journaled_substrate(
        context(),
        guard,
        journal,
        after_shield_key=key,
        before_signed_extrinsic=signing,
    )
    sub._substrate = Raw()
    key_bytes = asyncio.run(sub.mev_next_key())
    assert len(key_bytes) == 1184
    assert observed[0] == (
        "key",
        "sha256:" + hashlib.sha256(key_bytes).hexdigest(),
        1184,
    )
    signer = Keypair.create_from_uri("//Bob")
    asyncio.run(
        sub.sign_extrinsic(CallBytes(b"fixture", 445), signer, nonce=11, period=8)
    )
    assert observed[1:] == [("guard", signer.ss58_address), ("inner", 11, 8)]


@pytest.mark.parametrize("present", [True, False])
def test_installed_sdk_transaction_reconciliation_uses_public_lookup(present):
    from test_net1_chain_adapter import BLOCK, GENESIS, context, installed_sdk

    bt = installed_sdk()
    from bittensor._transport.contract import InclusionReport
    from bittensor._transport.errors import ExtrinsicNotFound

    from carbon.chain.sdk_weights import BittensorPublicationBackend

    class Sub(bt.RpcSubstrate):
        async def block_hash(self, block):
            return GENESIS if block == 0 else BLOCK

    class Raw:
        async def resolve_extrinsic(self, tx_hash, block_hash):
            assert tx_hash == "0x" + "c" * 64 and block_hash == BLOCK
            if not present:
                raise ExtrinsicNotFound("synthetic missing transaction")
            return InclusionReport(
                tx_hash,
                finalized=True,
                block_hash=BLOCK,
                block_number=100,
                extrinsic_idx=1,
                is_success=True,
            )

    sub = Sub(context().endpoint)
    sub._substrate = Raw()
    backend = BittensorPublicationBackend(context(), "synthetic-publisher", None)
    backend.substrate, backend.client = sub, object()
    observation = asyncio.run(backend.transaction("0x" + "c" * 64, 100))
    if present:
        assert observation.success and observation.block == 100
    else:
        assert observation is None


@pytest.mark.parametrize("inner_success", [None, False, True])
def test_setup_reconciliation_requires_exact_finalized_inner_receipt(
    tmp_path, inner_success
):
    from carbon.chain.localnet import LocalnetSession

    inner_hash, outer_hash, block_hash = ("0x" + c * 64 for c in "abc")
    expected = SimpleNamespace(
        success=inner_success, block_hash=block_hash, extrinsic_id="10-0003"
    )

    class Client:
        async def blocks(self, *, finalized):
            assert finalized
            yield SimpleNamespace(number=10)

    class Sub:
        async def block_hash(self, block):
            assert block == 10
            return block_hash

        async def find_extrinsic(self, identity, observed_block):
            assert observed_block == block_hash
            if identity == inner_hash and inner_success is not None:
                return expected
            return None

    session = LocalnetSession("carbon-localnet-fixture", tmp_path)
    session.client, session.sub = Client(), Sub()

    async def verify():
        pass

    session.verify, session.save = verify, lambda: None
    reported = SimpleNamespace(success=False)
    record = {
        "state": "REJECTED",
        "start_finalized_block": 10,
        "transaction": outer_hash,
        "inner_transaction": inner_hash,
    }
    result = asyncio.run(session.reconcile_inner(record, reported))
    assert result is (reported if inner_success is None else expected)
    assert (record["state"] == "FINALIZED_RECONCILED") is (inner_success is True)
    assert record["reconciled_at_finalized_block"] == 10


def test_archived_runtime_evidence_bytes_match_recorded_hashes():
    import gzip

    root = Path(__file__).parents[2] / ".agent/evidence/wave_c/net-5-runtime"
    for manifest_path in root.glob("*/manifest.json"):
        manifest = json.loads(manifest_path.read_text())
        assert len(manifest["head"]) == 40
        for name, expected in manifest["hashes_sha256"].items():
            if name == "node.log(uncompressed)":
                data = gzip.decompress(
                    (manifest_path.parent / "node.log.gz").read_bytes()
                )
            else:
                data = (manifest_path.parent / name).read_bytes()
            assert hashlib.sha256(data).hexdigest() == expected


@pytest.mark.skipif(
    os.name == "nt", reason="canonical A3 descriptor-relative registry required"
)
def test_three_real_fixture_exams_feed_shared_winner_complete_vector(tmp_path):
    from net5_fixture_support import Exam
    from test_net2_transport import CONTEXT, Adapter, FakeVerifier, headers, snapshot
    from test_net4b_publication import capabilities

    from carbon.candidates.store import CandidateJournal
    from carbon.chain import Participant
    from carbon.chain.publication import compile_targets, validate_integers
    from carbon.rewards.core import Q12, DevelopmentTerms
    from carbon.rewards.intents import LocalnetIntentIssuer
    from carbon.rewards.ledger import FixtureRewardLedger
    from carbon.transport.store import ReceiptJournal

    async def exercise():
        receipts = ReceiptJournal(tmp_path / "receipts.sqlite", CONTEXT)
        adapter = Adapter(
            snapshot()
        )  # Deterministic chain/auth doubles, explicitly not localnet.
        exams = [
            Exam(
                tmp_path / (suffix or "a"),
                receipts,
                adapter,
                "validator",
                FakeVerifier(),
                suffix,
            )
            for suffix in (None, "b", "c")
        ]
        ledger = FixtureRewardLedger(receipts, adapter, tuple(e.journal for e in exams))
        signer = lambda body, now, hotkey: headers(body, now, hotkey)

        async def paced_commit(exam, variant, hotkey):
            # Advance the explicit chain double, preserving the real 32/s ingress limit.
            block = adapter.state.finalized_block + 1
            adapter.state = replace(
                adapter.state,
                finalized_block=block,
                block_hash=f"0x{block:064x}",
                timestamp_ms=adapter.state.timestamp_ms + 100,
            )
            return await exam.commit(variant, signer, hotkey=hotkey)

        baselines = []
        for exam in exams:
            for variant in range(20):
                ref = await paced_commit(exam, variant, "validator")
                accepted = exam.evaluate(
                    ref
                )  # Existing A7/A8/A5 acceptance; never injected flags.
                if accepted:
                    break
            else:
                pytest.fail(
                    "No admitted baseline within registered synthetic attempt budget"
                )
            baselines.append(accepted.score_hex)
            opens = adapter.state.timestamp_ms
            await ledger.register(
                DevelopmentTerms(
                    exam.journal.context.identity,
                    ref.identity,
                    accepted.score_hex,
                    "1",
                    opens,
                    opens + 3600000,
                    opens + 3600000,
                    ((opens, Q12 // 3),),
                ),
                exam.pack,
                exam.profile.challenge_key.challenge_id,
            )
        assert (
            ledger.resolve_projection(await ledger.project())["targets"]["burn"] == Q12
        )
        winners = []
        for exam, baseline in zip(exams[::2], baselines[::2]):
            for variant in range(20, 60):
                ref = await paced_commit(exam, variant, "miner")
                batch = await ledger.open_batch(
                    exam.journal.context.identity,
                    f"{exam.profile.challenge_key.challenge_id}-{variant}",
                )
                accepted = exam.evaluate(ref)
                state = await ledger.close_batch(batch)
                if accepted and float.fromhex(state.record_hex) > float.fromhex(
                    baseline
                ):
                    winners.append((ref, variant))
                    break
            else:
                pytest.fail(
                    "No accepted improvement; never relax scientific thresholds"
                )
        target = ledger.resolve_projection(await ledger.project())
        assert len(target["targets"]["challenges"]) == 3
        assert len(target["targets"]["winners"]) == 1
        assert 0 < target["targets"]["burn"] < Q12
        issuer = LocalnetIntentIssuer(ledger)
        intent = await issuer.issue("offline-three-exam-integration")
        caps = capabilities(adapter.state)
        plan = compile_targets(
            issuer.resolve(intent, adapter.state), adapter.state, caps, "validator"
        )
        assert sum(v for _, v in plan.q12) == Q12 and len(plan.q12) == 2
        validate_integers(
            plan, [u for u, _ in plan.integers], [v for _, v in plan.integers], caps
        )
        assert await paced_commit(exams[0], winners[0][1], "validator") == winners[0][0]
        assert (
            ledger.resolve_projection(await ledger.project())["states"]
            == target["states"]
        )
        after_copy = ledger.resolve_projection(await ledger.project())
        restarted = FixtureRewardLedger(
            receipts,
            adapter,
            tuple(
                CandidateJournal(receipts, e.journal.context, e.journal.limits)
                for e in exams
            ),
        )
        assert (
            restarted.resolve_projection(await restarted.project())["targets"]
            == after_copy["targets"]
        )
        adapter.state = replace(
            adapter.state,
            finalized_block=adapter.state.finalized_block + 1,
            block_hash="0x" + "3" * 64,
            participants=(
                adapter.state.participants[0],
                Participant(
                    1, "replacement", "other-cold", adapter.state.finalized_block + 1
                ),
            ),
        )
        assert (
            restarted.resolve_projection(await restarted.project())["targets"]["burn"]
            == Q12
        )

    asyncio.run(exercise())
