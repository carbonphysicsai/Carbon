"""The owner's Null-consensus switch (scripts/dev/null_consensus_switch.py): dry by default, and every
refusal rule holds before anything is signed. A fake substrate stands in for the chain; no network, no SDK.
"""

from __future__ import annotations

import asyncio
import importlib.util
import io
import json
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/dev/null_consensus_switch.py"
spec = importlib.util.spec_from_file_location("null_consensus_switch", SCRIPT)
switch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(switch)

OWNER = "5D9oP2ZTF1G7pg25EdPjCyy22315c6SvQqwrVzXg2WWF1QMu"


class Call:
    def __init__(self, data):
        self.data = data
        self.call_hash = "0x" + "ab" * 32


class Rows:
    def __init__(self, count):
        self.count = count

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for _ in range(self.count):
            yield object()


class Raw:
    def __init__(self, chain):
        self.chain = chain

    async def get_chain_finalised_head(self):
        return "0xhead"

    async def compose_call(self, module, function, params, block_hash=None):
        self.chain.composed.append((module, function, params))
        return Call(self.chain.call_data)

    async def query_map(self, module, name, params, block_hash=None):
        assert (module, name) == ("SubtensorModule", "TimelockedWeightCommits")
        return Rows(1 if params[0] in self.chain.pending else 0)

    async def query(self, module, name, params, block_hash=None):
        assert module == "SubtensorModule"
        if name == "SubnetEpochConsensus":
            return self.chain.mode
        if name == "ValidatorPermit":
            return self.chain.permits
        if name == "Keys":
            return self.chain.keys[params[1]]
        if name == "SubnetOwner":
            return OWNER
        raise AssertionError(name)


class Chain:
    """The fake chain and substrate in one."""

    def __init__(self):
        self.genesis = switch.TESTNET_GENESIS
        self.spec = 486
        self.call_data = bytes.fromhex("136f370201")
        self.pending = set()
        self.mode = "Yuma"
        self.permits = [True, False, True]
        self.keys = ["5HWGP", "5Other", "5Receiver"]
        self.composed = []
        self.submitted = []
        self.submit_error = None
        self.after_submit_mode = "Null"
        self.raw = Raw(self)
        self.closed = False

    async def block_hash(self, block=None):
        return self.genesis

    async def spec_version(self):
        return self.spec

    async def submit(
        self, call, keypair, wait_for_inclusion=True, wait_for_finalization=True
    ):
        self.submitted.append((call, keypair))
        if not self.submit_error:
            self.mode = self.after_submit_mode
            self.permits = [True, False, False]

        class Result:
            error = self.submit_error
            extrinsic_id = "8315500-3"
            block_hash = "0xincluded"

        return Result()

    async def close(self):
        self.closed = True


class Wallet:
    def __init__(self, coldkey_ss58=OWNER):
        self.coldkeypub = type("Pub", (), {"ss58_address": coldkey_ss58})()
        self.coldkey_reads = 0

    @property
    def coldkey(self):
        self.coldkey_reads += 1
        return "KEYPAIR"


def run(chain, argv, *, answer="567", wallet=None):
    out = io.StringIO()
    wallets = []

    def factory(name, path):
        wallets.append((name, path))
        return wallet or Wallet()

    async def connect(endpoint):
        return chain

    code = asyncio.run(
        switch.main_async(
            argv,
            connect=connect,
            wallet_factory=factory,
            ask=lambda prompt: answer,
            out=out,
        )
    )
    return code, out.getvalue(), wallets


def test_the_default_is_a_dry_run_that_signs_nothing():
    chain = Chain()
    code, out, wallets = run(chain, ["switch"])
    assert code == 0
    assert "DRY RUN" in out and "0x136f370201" in out
    assert chain.submitted == [] and wallets == []
    assert chain.composed == [
        ("AdminUtils", "sudo_set_epoch_consensus", {"netuid": 567, "mode": "Null"})
    ]
    assert chain.closed


def test_the_composed_call_must_be_the_reviewed_bytes():
    chain = Chain()
    chain.call_data = bytes.fromhex("136f370200")  # Yuma, or any other call
    code, _, _ = run(chain, ["switch", "--submit", "--wallet-name", "owner"])
    assert code == switch.EXIT_REFUSED and chain.submitted == []


def test_only_netuid_567_is_accepted():
    chain = Chain()
    code, _, _ = run(chain, ["switch", "--netuid", "1"])
    assert code == switch.EXIT_REFUSED and chain.composed == []


def test_a_different_genesis_is_refused():
    chain = Chain()
    chain.genesis = "0x" + "11" * 32  # finney, localnet, anything else
    code, _, _ = run(chain, ["switch", "--submit", "--wallet-name", "owner"])
    assert (
        code == switch.EXIT_REFUSED and chain.composed == [] and chain.submitted == []
    )


def test_a_runtime_before_the_null_epoch_fix_is_refused():
    chain = Chain()
    chain.spec = 481
    code, _, _ = run(chain, ["switch"])
    assert code == switch.EXIT_REFUSED and chain.composed == []


@pytest.mark.parametrize("mechanism", [0, 1, 15])
def test_any_pending_timelocked_commit_refuses_even_a_dry_run(mechanism):
    chain = Chain()
    chain.pending = {567 + 4096 * mechanism}
    code, _, _ = run(chain, ["switch"])
    assert code == switch.EXIT_REFUSED and chain.submitted == []


def test_already_null_is_reported_not_submitted():
    chain = Chain()
    chain.mode = "Null"
    code, out, _ = run(chain, ["switch", "--submit", "--wallet-name", "owner"])
    assert code == 0 and "already Null" in out and chain.submitted == []


def test_submitting_needs_a_wallet_name():
    chain = Chain()
    code, _, _ = run(chain, ["switch", "--submit"])
    assert code == switch.EXIT_REFUSED and chain.submitted == []


def test_the_typed_netuid_must_match_before_the_wallet_is_opened():
    chain = Chain()
    code, _, wallets = run(
        chain, ["switch", "--submit", "--wallet-name", "owner"], answer="yes"
    )
    assert code == switch.EXIT_REFUSED
    assert (
        chain.submitted == [] and wallets == []
    )  # the password prompt is never reached


def test_a_wallet_that_is_not_the_subnet_owner_is_refused_before_the_key_is_decrypted():
    chain = Chain()
    wallet = Wallet("5NotTheOwner")
    code, _, _ = run(
        chain, ["switch", "--submit", "--wallet-name", "owner"], wallet=wallet
    )
    assert code == switch.EXIT_REFUSED
    assert wallet.coldkey_reads == 0 and chain.submitted == []


def test_the_confirmed_submission_signs_once_and_reads_back_null_and_the_permit_holder():
    chain = Chain()
    wallet = Wallet()
    code, out, wallets = run(
        chain,
        ["switch", "--submit", "--wallet-name", "owner", "--wallet-path", "/w"],
        wallet=wallet,
    )
    assert code == 0
    assert wallets == [("owner", Path("/w"))]
    assert wallet.coldkey_reads == 1 and len(chain.submitted) == 1
    assert chain.submitted[0][0].data == bytes.fromhex("136f370201")
    assert "extrinsic 8315500-3" in out and "0xincluded" in out
    assert "READ-BACK epoch consensus = Null" in out
    assert "READ-BACK permit holders  = UID 0 5HWGP" in out


def test_a_failed_submission_exits_three():
    chain = Chain()
    chain.submit_error = "TxRateLimitExceeded"
    code, out, _ = run(chain, ["switch", "--submit", "--wallet-name", "owner"])
    assert code == switch.EXIT_SUBMIT_FAILED and "TxRateLimitExceeded" in out


def test_a_read_back_that_is_not_null_exits_four():
    chain = Chain()
    chain.after_submit_mode = "Yuma"
    code, out, _ = run(chain, ["switch", "--submit", "--wallet-name", "owner"])
    assert code == switch.EXIT_NOT_NULL and "READ-BACK epoch consensus = Yuma" in out


def test_no_option_takes_a_password_or_a_key():
    parser = switch.build_parser()
    text = parser.format_help() + "".join(
        action.format_help()
        for action in parser._subparsers._group_actions[0].choices.values()
    )
    for word in ("password", "passphrase", "mnemonic", "seed", "--key"):
        assert word not in text.lower().replace("password prompt", "")
    source = SCRIPT.read_text()
    assert "getpass" not in source and "environ" not in source


posix_modes = pytest.mark.skipif(
    os.name == "nt", reason="owner-only file modes are POSIX"
)


def _config(tmp_path, name, body, mode=0o600):
    path = tmp_path / name
    path.write_text(json.dumps(body))
    path.chmod(mode)
    return str(path)


def _weights(tmp_path, operator_hotkey, standing_hotkey, mode=0o600):
    operator = _config(
        tmp_path,
        "operator.json",
        {"publisher": {"hotkey": operator_hotkey, "coldkey": OWNER}},
        mode,
    )
    standing = _config(
        tmp_path, "standing.json", {"publisher_hotkey": standing_hotkey}, mode
    )
    return ["check-weights", "--operator", operator, "--standing", standing]


@posix_modes
def test_the_weights_signer_must_be_uid_0s_hotkey_in_both_files(tmp_path):
    chain = Chain()
    chain.keys[0] = switch.WEIGHTS_SIGNER_HOTKEY
    code, out, _ = run(
        chain,
        _weights(tmp_path, switch.WEIGHTS_SIGNER_HOTKEY, switch.WEIGHTS_SIGNER_HOTKEY),
    )
    assert code == 0 and "UID 0" in out


@posix_modes
def test_the_receiver_hotkey_must_not_sign_weights(tmp_path):
    chain = Chain()
    chain.keys[0] = switch.WEIGHTS_SIGNER_HOTKEY
    code, _, _ = run(
        chain, _weights(tmp_path, switch.RECEIVER_HOTKEY, switch.WEIGHTS_SIGNER_HOTKEY)
    )
    assert code == switch.EXIT_REFUSED
    code, _, _ = run(
        chain, _weights(tmp_path, switch.WEIGHTS_SIGNER_HOTKEY, switch.RECEIVER_HOTKEY)
    )
    assert code == switch.EXIT_REFUSED


@posix_modes
def test_a_hotkey_that_is_not_uid_0_on_chain_is_refused(tmp_path):
    chain = Chain()
    chain.keys[0] = "5SomeoneElse"
    code, _, _ = run(
        chain,
        _weights(tmp_path, switch.WEIGHTS_SIGNER_HOTKEY, switch.WEIGHTS_SIGNER_HOTKEY),
    )
    assert code == switch.EXIT_REFUSED


@posix_modes
def test_a_config_readable_by_others_is_refused(tmp_path):
    chain = Chain()
    chain.keys[0] = switch.WEIGHTS_SIGNER_HOTKEY
    code, _, _ = run(
        chain,
        _weights(
            tmp_path, switch.WEIGHTS_SIGNER_HOTKEY, switch.WEIGHTS_SIGNER_HOTKEY, 0o644
        ),
    )
    assert code == switch.EXIT_REFUSED
