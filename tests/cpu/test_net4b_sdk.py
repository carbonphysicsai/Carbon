"""Installed 11.1 SDK contracts, with explicit transport doubles and no network."""

import ast
import hashlib
import inspect
import textwrap
from dataclasses import replace

import pytest
from test_net1_chain_adapter import (
    BLOCK,
    GENESIS,
    InstalledSubstrate,
    context,
    installed_sdk,
)
from test_net4b_publication import prepared
from test_reward_ledger import run

from carbon.chain.publication import (
    PublicationFailure,
    compile_targets,
    validate_integers,
)
from carbon.chain.sdk_weights import (
    capture_capabilities,
    guarded_weights,
    journaled_substrate,
)


def test_installed_sdk_hook_source_contracts_are_exact():
    bt = installed_sdk()
    from bittensor.intents import SetWeights

    for function, expected in (
        (
            SetWeights.build,
            "bea5b5014bdbfe2b9884fe3ef7784b100279560cbc1da8ac5c82c539bbb5717e",
        ),
        (
            bt.RpcSubstrate.submit,
            "dad54a796e48b4a0be575f9f4732395611b9d7190d852f7eabc4b1cb1f7bc704",
        ),
        (
            bt.RpcSubstrate._submit_and_report,
            "00b3a0de166ac561e297415aa1775660a2dc4f05f4dac18f09406938ca6b0060",
        ),
    ):
        node = ast.parse(textwrap.dedent(inspect.getsource(function))).body[0]
        assert (
            hashlib.sha256(
                ast.dump(node, include_attributes=False).encode()
            ).hexdigest()
            == expected
        )


class WeightSubstrate:
    def __init__(self, *, cr=False):
        self.cr, self.maximum, self.minimum = cr, 65535, 1
        self.composed, self.submitted = [], []

    async def block_number(self):
        return 100

    async def block_hash(self, _):
        return BLOCK

    async def block_time(self):
        return 0.25

    async def query(self, module, item, params=None, block_hash=None):
        values = {
            "Uids": 0,
            "CommitRevealWeightsEnabled": self.cr,
            "WeightsSetRateLimit": 0,
            "LastUpdate": [0, 0],
            "MinAllowedWeights": self.minimum,
            "MaxWeightsLimit": self.maximum,
            "Tempo": 10,
            "RevealPeriodEpochs": 1,
            "LastEpochBlock": 90,
            "PendingEpochAt": 0,
            "SubnetEpochIndex": 7,
            "BlocksSinceLastStep": 10,
        }
        assert module == "SubtensorModule" and item in values
        return values[item]

    async def compose(self, call):
        from bittensor._transport.contract import CallBytes

        self.composed.append(call)
        return CallBytes(b"synthetic checked call", 445)

    async def estimate_fee(self, call, public_key):
        import bittensor as bt

        return bt.Balance.from_rao(1)

    async def submit(self, call, keypair, **kwargs):
        from bittensor.result import ExtrinsicResult

        self.submitted.append(call)
        return ExtrinsicResult(success=True, block_hash=BLOCK, extrinsic_id="100-0001")


@pytest.mark.parametrize("cr", [False, True])
def test_installed_sdk_execute_rebuild_is_guarded_before_composition_or_encryption(
    tmp_path, monkeypatch, cr
):
    bt = installed_sdk()
    from bittensor.intents import weights
    from bittensor.keyfiles import Keypair

    _, _, gate, caps, resolved = prepared(tmp_path)
    caps = replace(caps, commit_reveal=cr)
    plan = compile_targets(resolved, gate.adapter.state, caps, "validator")
    sub, calls = WeightSubstrate(cr=cr), []

    def encryption(**kwargs):
        calls.append("encrypt")
        assert kwargs["uids"] == [0, 1] and kwargs["weights"] == [3449, 65535]
        return b"fixture ciphertext", 123

    monkeypatch.setattr(weights._core, "get_encrypted_commit_v2", encryption)

    async def guard(uids, values, preflight):
        calls.append("guard")
        validate_integers(plan, uids, values, caps)

    async def checked(call, extras):
        calls.append("call")
        assert call.spec_version == 445
        assert extras == ({"reveal_round": 123} if cr else {})

    wallet = Keypair.create_from_uri("//Alice")
    intent = guarded_weights(1, plan, guard, checked)
    client = bt.Client(
        gate.context.endpoint, substrate=sub, policy=bt.Policy(allowed_netuids=[1])
    )
    assert run(client.plan(intent, wallet)).ok
    assert calls[:2] == (["guard", "encrypt"] if cr else ["guard", "call"])
    sub.maximum = 32767  # execution rebuild would clip the earlier valid preview
    prior_compositions = len(sub.composed)
    with pytest.raises(PublicationFailure, match="DISTORTION"):
        run(client.execute(intent, wallet, retries=0))
    assert len(sub.composed) == prior_compositions and sub.submitted == []
    assert calls.count("encrypt") == int(cr)


def test_installed_sdk_policy_remains_enforced_after_final_vector_guard(tmp_path):
    bt = installed_sdk()
    from bittensor.keyfiles import Keypair

    _, _, gate, caps, resolved = prepared(tmp_path)
    plan = compile_targets(resolved, gate.adapter.state, caps, "validator")
    checked = []

    async def guard(uids, values, preflight):
        validate_integers(plan, uids, values, caps)
        checked.append(True)

    async def call_checked(call, extras):
        pass

    sub = WeightSubstrate()
    client = bt.Client(
        gate.context.endpoint, substrate=sub, policy=bt.Policy(allowed_netuids=[2])
    )
    with pytest.raises(bt.PolicyError):
        run(
            client.execute(
                guarded_weights(1, plan, guard, call_checked),
                Keypair.create_from_uri("//Alice"),
            )
        )
    assert checked and sub.submitted == []


def test_installed_sdk_actual_timelock_encryptor_receives_checked_integers(tmp_path):
    installed_sdk()
    from bittensor.keyfiles import Keypair

    _, _, gate, caps, resolved = prepared(tmp_path)
    caps = replace(caps, commit_reveal=True)
    plan = compile_targets(resolved, gate.adapter.state, caps, "validator")
    order = []

    async def guard(uids, values, preflight):
        validate_integers(plan, uids, values, caps)
        order.append("checked")

    async def checked(call, extras):
        assert order == ["checked"] and type(extras["reveal_round"]) is int

    sub = WeightSubstrate(cr=True)
    run(
        guarded_weights(1, plan, guard, checked).build(
            sub, Keypair.create_from_uri("//Alice")
        )
    )
    call = sub.composed[0]
    assert call.function == "commit_timelocked_mechanism_weights"
    assert len(call.params["commit"]) > 32


def test_installed_sdk_records_hash_before_actual_transport_submission():
    installed_sdk()
    from bittensor._transport.contract import (
        CallBytes,
        InclusionReport,
        SignedExtrinsic,
    )
    from bittensor.keyfiles import Keypair

    order = []

    async def before_sign(call, signer):
        order.append("guard")

    async def before_dispatch(tx_hash):
        assert order == ["guard", "sign"] and tx_hash == "0x" + "a" * 64
        order.append("journal")

    class Raw:
        async def create_signed_extrinsic(self, call, keypair, **kwargs):
            order.append("sign")
            signature = keypair.sign(b"NET-4B synthetic signing contract")
            assert len(signature) == 64
            return SignedExtrinsic(b"synthetic signed bytes", "0x" + "a" * 64)

        async def submit_extrinsic(self, extrinsic, **kwargs):
            assert order == ["guard", "sign", "journal"]
            order.append("wire")
            return InclusionReport(
                extrinsic.extrinsic_hash,
                finalized=True,
                block_hash=BLOCK,
                block_number=100,
                extrinsic_idx=1,
                is_success=True,
            )

    sub = journaled_substrate(context(), before_sign, before_dispatch)
    sub._substrate = Raw()  # Test-only backend injection; no network or real extrinsic.
    result = run(
        sub.submit(CallBytes(b"fixture", 445), Keypair.create_from_uri("//Alice"))
    )
    assert result.success and order == ["guard", "sign", "journal", "wire"]


def test_installed_sdk_capability_capture_uses_pinned_finalized_runtime_state():
    bt = installed_sdk()
    from bittensor.keyfiles import Keypair

    owner = Keypair.create_from_uri("//Alice").ss58_address
    miner = Keypair.create_from_uri("//Bob").ss58_address

    class Sub(InstalledSubstrate):
        async def runtime_call(self, *args, **kwargs):
            return {
                "netuid": 1,
                "num_uids": 2,
                "hotkeys": [owner, miner],
                "coldkeys": [owner, miner],
                "block_at_registration": [1, 2],
                "total_stake": [100, 0],
            }

        async def query(self, module, item, params=None, block_hash=None):
            assert block_hash == BLOCK
            if module == "Timestamp":
                return 100000
            if module == "System":
                return {"spec_version": 445, "spec_name": "node-subtensor"}
            values = {
                "SubnetOwner": owner,
                "SubnetOwnerHotkey": owner,
                "OwnedHotkeys": [owner],
                "MechanismCountCurrent": 1,
                "MaxMechanismCount": 2,
                "RecycleOrBurn": "Burn",
                "MinAllowedWeights": 1,
                "MaxWeightsLimit": 65535,
                "WeightsVersionKey": 0,
                "WeightsSetRateLimit": 0,
                "LastUpdate": [0, 0],
                "CommitRevealWeightsEnabled": False,
                "ValidatorPermit": [True, False],
                "StakeThreshold": 1000,
            }
            return values[item]

    sub = Sub()
    client = bt.Client(context().endpoint, substrate=sub)
    snapshot, caps = run(capture_capabilities(client, sub, context(), owner))
    caps.validate(snapshot, owner)
    assert (
        caps.sufficient_stake
    )  # Runtime's owner-hotkey exception, even below threshold.
    sub.genesis = BLOCK
    with pytest.raises(PublicationFailure, match="GENESIS"):
        run(capture_capabilities(client, sub, context(), owner))
    assert context().genesis_hash == GENESIS
