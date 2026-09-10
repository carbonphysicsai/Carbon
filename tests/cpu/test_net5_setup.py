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
    from test_net1_chain_adapter import installed_sdk, context

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
