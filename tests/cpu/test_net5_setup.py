"""Localnet isolation/fixture contracts; runtime results have a separate lane."""

import asyncio
import copy
import gzip
import hashlib
import json
import os
import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.chain.localnet import (
    DIGEST,
    IMAGE,
    ROOT_SETTINGS,
    STARTUP,
    inspect_image_profile,
    inspect_isolation,
    root_setting,
    runtime_profile,
    startup_for,
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
            "Labels": {
                "carbon.scope": "disposable-localnet",
                "carbon.runtime-profile": "fast",
                "carbon.execution-mode": "full",
            },
        },
        "State": {"Running": True},
        "HostConfig": {
            "Privileged": False,
            "Memory": 5 * 1024**3,
            "NanoCpus": 3 * 10**9,
            "PidsLimit": 1024,
        },
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


def test_runtime_diagnostic_log_excludes_decrypted_inner_payloads():
    assert "basic-authorship=debug" not in STARTUP
    assert "mev-shield=debug" in STARTUP
    assert "pallet-shield=debug" in STARTUP


def test_standard_profile_is_separate_exact_non_fast_release():
    name, profile = runtime_profile("standard")
    assert name == "standard"
    assert profile["selector"] == "False"
    assert profile["binary_path"] == "/target/non-fast-runtime/release/node-subtensor"
    assert profile["build_profile"] == "release"
    assert profile["cargo_features"] == ["pow-faucet", "metadata-hash"]
    assert "fast-runtime" not in profile["cargo_features"]
    assert "exec /scripts/carbon-localnet.sh False --no-purge" in startup_for(name)
    assert startup_for(name) != STARTUP


def test_pinned_image_inspection_proves_distinct_installed_profiles(
    monkeypatch, tmp_path
):
    manifest = json.loads(
        (Path(__file__).parents[2] / "scripts/dev/localnet-runtime.json").read_text()
    )
    output = []
    for name in ("fast", "standard"):
        profile = manifest["profiles"][name]
        output.extend(
            (
                f"{name}_binary_present=true",
                f"{name}_binary_executable=true",
                f"{name}_wasm_present=true",
                f"{name}_binary_sha256={profile['binary_sha256']}",
                f"{name}_wasm_sha256={profile['wasm_sha256']}",
                f"{name}_version_rc=2",
                f"{name}_version=error: version flag unsupported",
            )
        )

    def run(command, **kwargs):
        assert command[0] == "docker" and kwargs["check"]
        if command[1:3] == ["image", "inspect"]:
            assert kwargs["timeout"] == 45
            value = [
                {
                    "Config": {
                        "Entrypoint": ["/scripts/localnet.sh"],
                        "Cmd": ["True"],
                    }
                }
            ]
            return SimpleNamespace(stdout=json.dumps(value))
        assert kwargs["timeout"] == 90
        assert (
            "--network" in command and command[command.index("--network") + 1] == "none"
        )
        assert IMAGE + "@" + DIGEST in command
        return SimpleNamespace(stdout="\n".join(output))

    monkeypatch.setattr("carbon.chain.localnet.subprocess.run", run)
    proof = inspect_image_profile(IMAGE + "@" + DIGEST, "standard", tmp_path)
    assert proof["profiles_distinct"]
    assert (
        proof["profiles"]["standard"]["binary_sha256"]
        != proof["profiles"]["fast"]["binary_sha256"]
    )
    assert json.loads((tmp_path / "image-profile.json").read_text()) == proof


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

    async def key(digest, length, context):
        observed.append(("key", digest, length, context))

    async def signing(kind, kwargs):
        observed.append((kind, kwargs["nonce"], kwargs["period"]))

    class Raw:
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
    key_bytes = bytes(range(256)) * 4 + bytes(range(160))

    async def block_number():
        return 41

    async def block_hash(block):
        assert block == 41
        return "0x" + "b" * 64

    async def query(module, item, params=None, block_hash=None):
        assert module == "MevShield" and block_hash == "0x" + "b" * 64
        return key_bytes if item == "NextKey" else 44

    async def query_map(module, item, params=None, block_hash=None):
        assert (module, item, block_hash) == (
            "MevShield",
            "AuthorKeys",
            "0x" + "b" * 64,
        )
        return [(bytes.fromhex("12" * 32), key_bytes)]

    sub.block_number = block_number
    sub.block_hash = block_hash
    sub.query = query
    sub.query_map = query_map
    key_bytes = asyncio.run(sub.mev_next_key())
    assert len(key_bytes) == 1184
    assert observed[0] == (
        "key",
        "sha256:" + hashlib.sha256(key_bytes).hexdigest(),
        1184,
        {
            "block": 41,
            "block_hash": "0x" + "b" * 64,
            "expires_at_exclusive": 44,
            "associated_authors": [bytes.fromhex("12" * 32)],
        },
    )
    signer = Keypair.create_from_uri("//Bob")
    asyncio.run(
        sub.sign_extrinsic(CallBytes(b"fixture", 445), signer, nonce=11, period=8)
    )
    assert observed[1:] == [("guard", signer.ss58_address), ("inner", 11, 8)]


def test_successful_shielded_nonce_transition_reopens_supported_sdk_transport(
    monkeypatch, tmp_path
):
    from carbon.chain.localnet import LocalnetSession

    class Substrate:
        async def query(self, module, item, params, block_hash=None):
            assert (module, item, params, block_hash) == (
                "System",
                "Account",
                ["disposable-signer"],
                "0x" + "b" * 64,
            )
            return {"nonce": 2, "data": "not-retained"}

    refreshed = []
    session = LocalnetSession("carbon-localnet-test", tmp_path)
    session.sub = Substrate()
    session.signer = "disposable-signer"
    session._transport_generation = 1
    session._transport_ready = True
    record = {
        "state": "FINALIZED",
        "block_hash": "0x" + "b" * 64,
        "signed_extrinsics": {
            "carrier": {"nonce": 0, "era_blocks": 8},
            "inner": {"nonce": 1, "era_blocks": 8},
        },
    }
    session.operations = [record]
    monkeypatch.setattr(session, "save", lambda: None)

    async def replace(bound_record):
        assert bound_record is record
        refreshed.append(True)
        session._transport_generation = 2

    monkeypatch.setattr(session, "_replace_sdk_transport", replace)

    async def refresh():
        async with session._submission_lock:
            await session._refresh_after_shielded_inner(record)

    asyncio.run(refresh())
    assert refreshed == [True]
    assert record["nonce_transition"] == {
        "carrier_nonce": 0,
        "inner_nonce": 1,
        "finalized_account_next_nonce": 2,
        "account_identity": "disposable-signer",
        "finalized_block_hash": "0x" + "b" * 64,
        "checked_transport_generation": 1,
        "sdk_transport": "REOPENED_THROUGH_SUPPORTED_PUBLIC_CLIENT",
        "replacement_transport_generation": 2,
    }
    assert "data" not in record["nonce_transition"]


@pytest.mark.parametrize("observed", [0, 1, 3, True, None])
def test_shielded_nonce_transition_fails_closed_on_chain_disagreement(
    monkeypatch, tmp_path, observed
):
    from carbon.chain.localnet import LocalnetSession

    class Substrate:
        async def query(self, *args, **kwargs):
            return {"nonce": observed}

    session = LocalnetSession("carbon-localnet-test", tmp_path)
    session.sub = Substrate()
    session.signer = "disposable-signer"
    session._transport_generation = 1
    session._transport_ready = True
    record = {
        "state": "FINALIZED",
        "block_hash": "0x" + "b" * 64,
        "signed_extrinsics": {
            "carrier": {"nonce": 0, "era_blocks": 8},
            "inner": {"nonce": 1, "era_blocks": 8},
        },
    }
    session.operations = [record]
    monkeypatch.setattr(session, "save", lambda: None)

    async def refresh():
        async with session._submission_lock:
            await session._refresh_after_shielded_inner(record)

    with pytest.raises(PublicationFailure, match="SHIELDED_NONCE_TRANSITION_MISMATCH"):
        asyncio.run(refresh())


def test_transport_handover_verifies_replacement_then_closes_previous(
    monkeypatch, tmp_path
):
    from test_net1_chain_adapter import context, installed_sdk

    bt = installed_sdk()
    import carbon.chain.localnet as module

    events = []

    class Previous:
        async def close(self):
            events.append("previous-closed")

    class Replacement:
        endpoint = context().endpoint

        async def connect(self):
            events.append("replacement-connected")

        async def block_hash(self, block):
            assert block == 0
            events.append("replacement-genesis-verified")
            return context().genesis_hash

        async def spec_version(self):
            events.append("replacement-spec-verified")
            return 445

        async def block_time(self):
            events.append("replacement-profile-verified")
            return 0.25

        async def close(self):
            events.append("replacement-closed")

    replacement = Replacement()
    monkeypatch.setattr(
        module, "journaled_substrate", lambda *args, **kwargs: replacement
    )
    monkeypatch.setattr(bt, "Client", lambda *args, **kwargs: SimpleNamespace())
    session = module.LocalnetSession("carbon-localnet-test", tmp_path)
    session.context = context()
    session._transport_hooks = {
        name: None
        for name in (
            "before_sign",
            "before_dispatch",
            "after_inner_sign",
            "after_shield_key",
            "before_signed_extrinsic",
        )
    }
    session.sub = Previous()
    session._transport_generation = 1
    session._transport_ready = True
    monkeypatch.setattr(session, "save", lambda: None)
    record = {"label": "register-miner", "state": "FINALIZED"}

    async def replace():
        async with session._submission_lock:
            await session._replace_sdk_transport(record)

    asyncio.run(replace())
    assert events == [
        "replacement-connected",
        "replacement-genesis-verified",
        "replacement-spec-verified",
        "replacement-profile-verified",
        "previous-closed",
    ]
    assert session.sub is replacement and session._transport_generation == 2
    assert session._transport_ready is True
    assert record["transport_handover"] == {
        "previous_generation": 1,
        "replacement_generation": 2,
        "account_submission_sequence": "EXCLUSIVE",
        "state": "REPLACEMENT_ACTIVE_AFTER_PREVIOUS_CLOSE",
        "replacement_identity": {
            "endpoint": context().endpoint,
            "genesis_hash": context().genesis_hash,
            "spec_version": 445,
            "runtime_profile": "fast",
            "runtime_binary": "/target/fast-runtime/release/node-subtensor",
            "block_time_seconds": 0.25,
        },
        "replacement_verified_before_previous_close": True,
        "previous_transport_closed": True,
    }


def test_ambiguous_submission_blocks_handover_and_later_execution(
    monkeypatch, tmp_path
):
    from carbon.chain.localnet import LocalnetSession

    session = LocalnetSession("carbon-localnet-test", tmp_path)
    session.operations = [{"label": "prior", "state": "AMBIGUOUS_OR_UNAVAILABLE"}]

    async def should_not_execute(*args):
        pytest.fail("Ambiguous submission must be reconciled before later execution")

    monkeypatch.setattr(session, "_execute_locked", should_not_execute)
    with pytest.raises(
        PublicationFailure, match="OUTSTANDING_SUBMISSION_REQUIRES_RECONCILIATION"
    ):
        asyncio.run(session.execute("later", object()))


def test_account_submission_sequence_is_exclusive(monkeypatch, tmp_path):
    from carbon.chain.localnet import LocalnetSession

    session = LocalnetSession("carbon-localnet-test", tmp_path)
    active = 0
    maximum = 0

    async def execute(label, intent, role):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0)
        active -= 1
        return label

    monkeypatch.setattr(session, "_execute_locked", execute)

    async def exercise():
        return await asyncio.gather(
            session.execute("first", object()), session.execute("second", object())
        )

    assert asyncio.run(exercise()) == ["first", "second"]
    assert maximum == 1


def test_ordinary_nonce_is_observed_without_being_supplied(monkeypatch, tmp_path):
    from test_net1_chain_adapter import context

    from carbon.chain.localnet import LocalnetSession

    block_hash = "0x" + "b" * 64
    signer = "disposable-signer"

    class Substrate:
        async def block_hash(self, block):
            assert block == 0
            return context().genesis_hash

        async def spec_version(self):
            return 445

        async def account_next_index(self, address):
            assert address == signer
            return 2

        async def query(self, module, item, params, block_hash=None):
            assert (module, item, params, block_hash) == (
                "System",
                "Account",
                [signer],
                "0x" + "b" * 64,
            )
            return {"nonce": 3}

    class Client:
        async def blocks(self, *, finalized):
            assert finalized
            yield SimpleNamespace(number=10)

        async def execute(self, intent, wallet, **kwargs):
            assert "nonce" not in kwargs
            return SimpleNamespace(
                data={},
                success=True,
                error=None,
                block_hash=block_hash,
                extrinsic_id="11-0002",
            )

    session = LocalnetSession("carbon-localnet-test", tmp_path)
    session.context = context()
    session.sub = Substrate()
    session.client = Client()
    session.roles = {"miner": SimpleNamespace(ss58_address=signer)}
    session._transport_generation = 2
    session._transport_ready = True
    monkeypatch.setattr(session, "save", lambda: None)
    result = asyncio.run(
        session.execute(
            "replace-miner-hotkey",
            SimpleNamespace(mev_shield_required=False),
            "miner",
        )
    )
    assert result.success
    assert session.operations[-1]["sdk_nonce_observation"] == {
        "account_identity": signer,
        "transport_generation": 2,
        "public_next_index_before_signing": 2,
        "sdk_selected_nonce": 2,
        "selection_source": "PINNED_SDK_11_1_0_PUBLIC_NEXT_INDEX",
        "nonce_supplied_by_carbon": False,
        "finalized_block_hash": block_hash,
        "finalized_account_next_nonce": 3,
        "outcome": "FINALIZED_INCREMENT_CONFIRMED",
    }


def test_pinned_sdk_source_exposes_the_shielded_nonce_cache_transition():
    from test_net1_chain_adapter import installed_sdk

    installed_sdk()
    import inspect

    from bittensor._transport.interface import SubstrateConnection
    from bittensor.executor import Executor

    shielded = inspect.getsource(Executor.submit_shielded)
    transport = inspect.getsource(SubstrateConnection.create_signed_extrinsic)
    assert "nonce + 1" in shielded
    assert "nonce=nonce" in shielded
    assert "self._nonces.pin(keypair.ss58_address, nonce)" in transport


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


def test_archived_net5r_standard_evidence_bytes_match_recorded_hashes():
    root = Path(__file__).parents[2] / ".agent/evidence/wave_c/net-5r-runtime"
    failed = json.loads((root / "34472892985" / "manifest.json").read_text())
    assert failed["stage"] == "PRE_KEY_IMAGE_INSPECTION"
    assert failed["signing_performed"] is False
    assert failed["network_created"] is False
    assert failed["outcome"] == "DIAGNOSTIC_INSTRUMENTATION_FAILED"
    for run in (
        "34473145103",
        "34473508494",
        "34474220953",
        "34489505489",
    ):
        manifest_path = root / run / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        assert manifest["profile"] == "standard" and manifest["g2"].startswith(
            "NOT_READY"
        )
        for name, expected in manifest["hashes_sha256"].items():
            data = (manifest_path.parent / name).read_bytes()
            assert hashlib.sha256(data).hexdigest() == expected
    retained_log = gzip.decompress((root / "34474220953" / "node.log.gz").read_bytes())
    assert b"Unshielded inner transaction: [REDACTED_DECRYPTED_BYTES]" in retained_log
    assert not re.search(rb"Unshielded inner transaction: [0-9a-f]{16}", retained_log)


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
