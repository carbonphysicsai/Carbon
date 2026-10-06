"""The signer's one chain extrinsic: a strategy commitment (COMMITMENT-POSTER-01).

Every bound (B1-B12 of the scope) is shown failing closed on the signer's own
checks, with no chain and no real key: the hotkey is a public development URI
and the pins are SYNTHETIC test values, built here, never the committed record
(which stays unpinned until the localnet round trip measures it).
"""

import io
import json
import os
import pty
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import pytest

from carbon.chain.external_signer import (
    SignerFailure,
    connect_signer,
    request_commitment,
    signatures_obtained,
)
from carbon_miner_signer import SignerServer, refusal_for
from carbon_miner_signer import commitment as cm
from carbon_miner_signer import signer as signer_module

ROOT = Path(__file__).resolve().parents[2]
URI = "//carbon-commitment-signer-specimen"
DIGEST = "sha256:" + "0123456789abcdef" * 4
GENESIS = "0x8f9cf856bf558a14440e75569c9e58594757048d7b3a84b5d25f6bd978263105"
FINNEY = "0x2f0555cc76fc2840a25a6ea3b9637146806f1f44b090c175ffde2a7e5ab36c03"
ERA_HASH = "0x" + "e" * 64
#: SYNTHETIC pins for tests only. The committed record keeps these null.
EXTENSIONS = [
    "CheckNonZeroSender",
    "CheckSpecVersion",
    "CheckTxVersion",
    "CheckGenesis",
    "CheckMortality",
    "CheckNonce",
    "CheckWeight",
    "ChargeTransactionPaymentWrapper",
    "SubtensorTransactionExtension",
    "CheckMetadataHash",
]
CALL_INDEX, DATA_TAG, CEILING = 0, 72, 2_000


def _record(**changes):
    record = json.loads(cm.RECORD_PATH.read_text(encoding="utf-8"))
    record["call"].update(call_index=CALL_INDEX, data_tag=DATA_TAG)
    record["extensions"] = list(EXTENSIONS)
    record["zero_sized_extensions"] = ["SubtensorTransactionExtension"]
    record["fee"].update(
        measured_fee_rao=900, measured_deposit_rao=100, ceiling_rao=CEILING
    )
    for key, value in changes.items():
        record[key] = value
    return record


POLICY, _ = cm.load_policy(_record())


def _keypair():
    from bittensor.keyfiles import Keypair

    return Keypair.create_from_uri(URI)


def _call(digest=DIGEST, netuid=567, pallet=18, call_index=CALL_INDEX, tag=DATA_TAG):
    # Written out byte by byte, independently of commitment.commitment_call.
    return (
        bytes([pallet, call_index])
        + netuid.to_bytes(2, "little")
        + b"\x04"
        + bytes([tag])
        + digest.encode()
    )


def _parts(current=7_200, nonce=5, tip=0, genesis=GENESIS, spec=445, mode=0):
    era = cm.mortal_era(128, current)
    extra = era + cm.compact(nonce) + cm.compact(tip) + bytes([mode])
    additional = (
        spec.to_bytes(4, "little")
        + (1).to_bytes(4, "little")
        + bytes.fromhex(genesis[2:])
        + bytes.fromhex(ERA_HASH[2:])
        + b"\x00"
    )
    return extra, additional


def _request(*, digest=DIGEST, call=None, current=7_200, fee=(900, 100), **unsigned):
    extra, additional = _parts(current=current)
    body = {
        "call_data": "0x" + (call if call is not None else _call(digest)).hex(),
        "era": {"period": 128, "current": current},
        "nonce": 5,
        "tip": 0,
        "genesis_hash": GENESIS,
        "era_block_hash": ERA_HASH,
        "spec_version": 445,
        "transaction_version": 1,
        "metadata_hash": None,
        "included_in_extrinsic": "0x" + extra.hex(),
        "included_in_signed_data": "0x" + additional.hex(),
    }
    body.update(unsigned)
    return {
        "protocol": signer_module.PROTOCOL,
        "op": "commit",
        "netuid": 567,
        "digest": digest,
        "unsigned": body,
        "fee": {"partial_fee_rao": fee[0], "deposit_rao": fee[1]},
    }


class _Asked:
    """The miner at the terminal, played by the test. Records each prompt."""

    def __init__(self, answer=True):
        self.answer, self.prompts = answer, []

    def __call__(self, text, expected):
        self.prompts.append((text, expected))
        return self.answer(expected) if callable(self.answer) else self.answer


def _server(directory, *, policy=POLICY, confirm=None):
    return SignerServer(
        _keypair(),
        Path(directory) / "s.sock",
        log=io.StringIO(),
        commit_policy=policy,
        confirm=confirm or _Asked(),
    )


@pytest.fixture
def short_dir():
    with tempfile.TemporaryDirectory(prefix="cm-", dir="/tmp") as directory:
        yield Path(directory)


def _refusal(response):
    assert response["ok"] is False, response
    return response["refusal"]


# Pins and encodings ---------------------------------------------------------


def test_committed_record_is_unpinned_so_every_commit_is_refused(short_dir):
    policy, missing = cm.load_policy()
    assert policy is None
    assert {"call.call_index", "call.data_tag", "fee.ceiling_rao"} <= set(missing)
    record = json.loads(cm.RECORD_PATH.read_text())
    assert record["fee"]["status"] == "HUMAN_INPUT"
    assert record["network"] == {
        **record["network"],
        "name": "testnet",
        "netuid": 567,
        "genesis_hash": GENESIS,
    }
    asked = _Asked()
    server = _server(short_dir, policy=None, confirm=asked)
    assert _refusal(server.answer(_request())) == "COMMITMENT_NOT_PINNED"
    assert asked.prompts == []


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            {
                "fee": {
                    "multiplier": 2,
                    "measured_fee_rao": 900,
                    "measured_deposit_rao": 100,
                    "ceiling_rao": 5000,
                }
            },
            "multiplier",
        ),
        ({"era": {"sdk_default_period": 128, "max_period": 512}}, "power of two"),
        ({"era": {"sdk_default_period": 128, "max_period": 100}}, "power of two"),
        ({"extensions": EXTENSIONS + ["SomethingNew"]}, "unrecorded"),
    ],
)
def test_an_inconsistent_record_is_broken_not_unset(change, message):
    with pytest.raises(ValueError, match=message):
        cm.load_policy(_record(**change))


def test_scale_encodings_match_substrate_vectors():
    # sp_runtime::generic::Era tests: mortal(64, 42) and mortal(32768, 20000).
    assert cm.mortal_era(64, 42) == bytes([165, 2])
    assert cm.mortal_era(32768, 20000) == bytes([78, 156])
    for value, encoded in (
        (0, "00"),
        (1, "04"),
        (63, "fc"),
        (64, "0101"),
        (16383, "fdff"),
        (16384, "02000100"),
        (2**30, "0300000040"),
    ):
        assert cm.compact(value).hex() == encoded
    import bittensor_core

    # Decoded back, the era's birth is the SDK's own computation.
    for current in (0, 127, 7_200, 1_234_567):
        encoded = int.from_bytes(cm.mortal_era(128, current), "little")
        period, phase = 2 << (encoded & 15), encoded >> 4
        assert period == 128 and phase == current % 128
        birth = (max(current, phase) - phase) // period * period + phase
        assert bittensor_core.era_birth(128, current) == birth


def test_the_signer_imports_nothing_from_carbon():
    import ast

    for name in ("commitment.py", "signer.py", "__init__.py"):
        tree = ast.parse((ROOT / "carbon_miner_signer" / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("carbon"), (name, node.module)
            if isinstance(node, ast.Import):
                assert all(not a.name.startswith("carbon") for a in node.names)


# B1-B11: the request ----------------------------------------------------------


def test_a_valid_commit_signs_the_signers_own_reconstruction(short_dir):
    asked = _Asked()
    server = _server(short_dir, confirm=asked)
    response = server.answer(_request())
    assert response["ok"] is True and set(response) == {
        "ok",
        "signature",
        "call",
        "fee_ceiling_rao",
        "tempo_index",
    }
    extra, additional = _parts()
    payload = _call() + extra + additional
    assert len(payload) <= 256  # signed as-is, not hashed
    from bittensor.sp_core import verify

    signature = bytes.fromhex(response["signature"][2:])
    assert verify(payload, signature, _keypair().ss58_address, 1)
    assert response["call"] == "0x" + _call().hex()
    assert response["fee_ceiling_rao"] == CEILING
    assert response["tempo_index"] == 7_200 // 360
    assert [expected for _, expected in asked.prompts] == [DIGEST[-8:]]


@pytest.mark.parametrize(
    "call",
    [
        bytes([7, 6])
        + (567).to_bytes(2, "little"),  # SubtensorModule.burned_register-shaped
        bytes([5, 0]) + b"\x00" * 33 + b"\x04",  # Balances.transfer-shaped
        bytes([0, 7]) + cm.compact(71) + DIGEST.encode(),  # System.remark_with_event
        bytes([7, 0]) + (567).to_bytes(2, "little") + b"\x00" * 8,  # weights-shaped
        bytes([12, 0]) + _call(),  # Sudo.sudo(commitment)
        _call(call_index=2),  # Commitments.set_max_space index
        _call(pallet=19),
        _call(tag=73),
        _call() + b"\x00",  # trailing bytes
        b"",
    ],
)
def test_any_other_call_is_refused(short_dir, call):
    assert (
        _refusal(_server(short_dir).answer(_request(call=call))) == "NOT_A_COMMITMENT"
    )


@pytest.mark.parametrize(
    "call",
    [
        bytes([20, 0]) + cm.compact(1) + _call(),  # Utility.batch([commitment])
        bytes([20, 2]) + cm.compact(1) + _call(),  # Utility.batch_all
        bytes([16, 0]) + b"\x00" + b"\x11" * 32 + b"\x00" + _call(),  # Proxy.proxy
        bytes([17, 1])
        + (2).to_bytes(2, "little")
        + _call(),  # Multisig.as_multi-shaped
        bytes([18, CALL_INDEX])
        + (567).to_bytes(2, "little")
        + cm.compact(2)
        + bytes([DATA_TAG])
        + DIGEST.encode()
        + bytes([DATA_TAG])
        + DIGEST.encode(),
    ],
)
def test_a_wrapped_or_doubled_commitment_is_refused(short_dir, call):
    assert (
        _refusal(_server(short_dir).answer(_request(call=call))) == "NOT_A_COMMITMENT"
    )


@pytest.mark.parametrize(
    "digest",
    [
        DIGEST.upper().replace("SHA256", "sha256"),
        DIGEST[:-1],
        DIGEST + "0",
        DIGEST[7:] + "0123456",
        DIGEST + "\n",
        DIGEST[:-1] + "٣",  # an Arabic-Indic digit
        "sha256:" + "0" * 65,
        "sha256 " + DIGEST[7:],
        None,
        71,
    ],
)
def test_a_malformed_digest_is_refused(short_dir, digest):
    request = _request(call=_call())
    request["digest"] = digest
    assert _refusal(_server(short_dir).answer(request)) == "BAD_DIGEST"


@pytest.mark.parametrize("netuid", [566, 0, 65535, "567", True, 567.0, None])
def test_only_the_netuid_fixed_at_start_is_accepted(short_dir, netuid):
    request = _request()
    request["netuid"] = netuid
    assert _refusal(_server(short_dir).answer(request)) == "WRONG_NETUID"
    # The call bytes cannot carry another netuid either.
    other = _request(call=_call(netuid=566))
    assert _refusal(_server(short_dir).answer(other)) == "NOT_A_COMMITMENT"


def test_another_networks_genesis_is_refused(short_dir):
    request = _request(genesis_hash=FINNEY)
    assert _refusal(_server(short_dir).answer(request)) == "WRONG_NETWORK"


@pytest.mark.parametrize(
    ("tip", "refusal"), [(1, "NONZERO_TIP"), (True, "NONZERO_TIP")]
)
def test_a_tip_is_refused(short_dir, tip, refusal):
    assert _refusal(_server(short_dir).answer(_request(tip=tip))) == refusal


def test_a_tip_hidden_in_the_extension_bytes_is_refused(short_dir):
    extra, _ = _parts(tip=10**9)
    request = _request(included_in_extrinsic="0x" + extra.hex())
    assert _refusal(_server(short_dir).answer(request)) == "PAYLOAD_MISMATCH"


@pytest.mark.parametrize(
    ("era", "refusal"),
    [
        ("00", "IMMORTAL_ERA"),
        (None, "IMMORTAL_ERA"),
        ({"period": 256, "current": 7_200}, "ERA_TOO_LONG"),
        ({"period": 65536, "current": 7_200}, "ERA_TOO_LONG"),
        ({"period": 100, "current": 7_200}, "MALFORMED_REQUEST"),
        ({"period": 128}, "MALFORMED_REQUEST"),
        ({"period": 128, "current": 7_200, "phase": 0}, "MALFORMED_REQUEST"),
    ],
)
def test_the_era_is_mortal_and_at_most_one_capped_period(short_dir, era, refusal):
    assert _refusal(_server(short_dir).answer(_request(era=era))) == refusal


@pytest.mark.parametrize(
    "parts",
    [
        {"included_in_extrinsic": "0x" + _parts(nonce=6)[0].hex()},
        {"included_in_signed_data": "0x" + _parts(genesis=FINNEY)[1].hex()},
        {"included_in_signed_data": "0x" + _parts(spec=446)[1].hex()},
        {"included_in_extrinsic": "0x" + _parts(mode=1)[0].hex()},
        {"included_in_extrinsic": "0x" + _parts(current=7_201)[0].hex()},
    ],
)
def test_extension_bytes_must_equal_the_signers_reconstruction(short_dir, parts):
    assert _refusal(_server(short_dir).answer(_request(**parts))) == "PAYLOAD_MISMATCH"


def test_metadata_hash_mode_is_refused(short_dir):
    request = _request(metadata_hash="0x" + "1" * 64)
    assert _refusal(_server(short_dir).answer(request)) == "MALFORMED_REQUEST"


@pytest.mark.parametrize(
    ("fee", "refusal"),
    [
        ((1_900, 101), "FEE_OVER_CEILING"),
        ((CEILING + 1, 0), "FEE_OVER_CEILING"),
        ((None, 0), "FEE_UNKNOWN"),
        ((900, None), "FEE_UNKNOWN"),
        ((-1, 0), "FEE_UNKNOWN"),
        (("900", 0), "FEE_UNKNOWN"),
    ],
)
def test_the_fee_ceiling_holds_and_an_unknown_fee_refuses(short_dir, fee, refusal):
    assert _refusal(_server(short_dir).answer(_request(fee=fee))) == refusal


def test_a_fee_at_the_ceiling_is_signed(short_dir):
    assert _server(short_dir).answer(_request(fee=(CEILING, 0)))["ok"] is True


@pytest.mark.parametrize(
    "extra",
    [
        {"confirmed": True},
        {"confirmation": DIGEST[-8:]},
        {"call": "0x00"},
        {"payload": "0x00"},
        {"signature": "0x00"},
        {"tip_asset_id": None},
        {"payload_json": {}},
    ],
)
def test_a_request_with_any_other_field_is_malformed(short_dir, extra):
    asked = _Asked()
    request = {**_request(), **extra}
    assert (
        _refusal(_server(short_dir, confirm=asked).answer(request))
        == "MALFORMED_REQUEST"
    )
    nested = _request()
    nested["unsigned"].update(extra)
    assert (
        _refusal(_server(short_dir, confirm=asked).answer(nested))
        == "MALFORMED_REQUEST"
    )
    nested_fee = _request()
    nested_fee["fee"].update(extra)
    assert (
        _refusal(_server(short_dir, confirm=asked).answer(nested_fee))
        == "MALFORMED_REQUEST"
    )
    assert asked.prompts == []


def test_the_sign_op_still_refuses_extrinsic_bytes(short_dir):
    server = _server(short_dir)
    extra, additional = _parts()
    scale = _call() + extra + additional
    assert (
        refusal_for(
            scale, hotkey=server.hotkey, scheme="sr25519", receivers=None, now_ns=0
        ).value
        == "NOT_A_CARBON_REQUEST"
    )
    response = server.answer(
        {"protocol": signer_module.PROTOCOL, "op": "sign", "payload": scale.hex()}
    )
    assert _refusal(response) == "NOT_A_CARBON_REQUEST"


# Confirmation: only the terminal ----------------------------------------------


def test_an_agent_cannot_confirm_its_own_request(short_dir):
    """The socket carries no confirmation; a refusal at the terminal (or no
    terminal at all) signs nothing and records nothing."""
    asked = _Asked(answer=False)
    server = _server(short_dir, confirm=asked)
    request = _request()
    assert (
        _refusal(server.answer({**request, "confirmed": True})) == "MALFORMED_REQUEST"
    )
    assert _refusal(server.answer(request)) == "NOT_CONFIRMED"
    assert len(asked.prompts) == 1
    assert server.ledger.entries() == []


def test_the_prompt_shows_network_netuid_digest_fee_and_todays_count(short_dir):
    asked = _Asked()
    server = _server(short_dir, confirm=asked)
    server.answer(_request())
    server.answer(_request(current=7_200 + 360))
    first, second = (text for text, _ in asked.prompts)
    for text in (first, second):
        assert "testnet" in text and "netuid    567" in text and DIGEST in text
        assert "0.000001000 TAO" in text and "ceiling 0.000002000 TAO" in text
        assert "tip 0" in text and "valid for 128 blocks" in text
        assert server.hotkey in text and "replaces" in text
    assert "today: 0 signed" in first and "today: 1 signed" in second


def _in_child_terminal(answer, expected):
    """Run `tty_confirm` in a child whose controlling terminal is a pty."""
    pid, master = pty.fork()
    if pid == 0:  # pragma: no cover - the child
        os._exit(0 if cm.tty_confirm("Type: ", expected, seconds=10) else 1)
    output = b""
    while b"Type: " not in output:
        output += os.read(master, 1024)
    os.write(master, answer.encode() + b"\n")
    _, status = os.waitpid(pid, 0)
    os.close(master)
    return os.waitstatus_to_exitcode(status) == 0


@pytest.mark.skipif(sys.platform != "linux", reason="pty controlling terminal")
def test_only_the_typed_suffix_confirms_on_the_terminal():
    assert _in_child_terminal(DIGEST[-8:], DIGEST[-8:]) is True
    assert _in_child_terminal("wrong123", DIGEST[-8:]) is False
    assert _in_child_terminal(DIGEST[-7:], DIGEST[-8:]) is False
    assert _in_child_terminal("", DIGEST[-8:]) is False


@pytest.mark.skipif(sys.platform != "linux", reason="controlling terminal")
def test_without_a_terminal_nothing_can_confirm():
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from carbon_miner_signer.commitment import tty_confirm;"
                "raise SystemExit(0 if tty_confirm('x', 'abcd1234', seconds=1) else 7)"
            ),
        ],
        input="abcd1234\n",
        text=True,
        cwd=ROOT,
        start_new_session=True,
        capture_output=True,
        check=False,
    )
    assert child.returncode == 7, child.stderr


# D4 and B10: the ledger and one at a time ------------------------------------


def test_one_commitment_per_tempo_survives_a_restart(short_dir):
    first = _server(short_dir)
    assert first.answer(_request(current=7_200))["ok"] is True
    again = _server(short_dir)  # a restarted signer, same ledger
    for current in (7_200, 7_200 + 359):
        refused = again.answer(_request(current=current))
        assert _refusal(refused) == "ALREADY_COMMITTED_THIS_TEMPO"
    assert again.answer(_request(current=7_200 + 360))["ok"] is True
    rows = again.ledger.entries()
    assert [row["tempo_index"] for row in rows] == [20, 21]
    assert all(
        set(row) >= {"digest", "netuid", "genesis_hash", "nonce"} for row in rows
    )
    assert oct(again.ledger.path.stat().st_mode & 0o777) == "0o600"


def test_a_chain_context_older_than_the_ledger_is_refused(short_dir):
    server = _server(short_dir)
    assert server.answer(_request(current=7_200 + 720))["ok"] is True
    assert _refusal(server.answer(_request(current=7_200))) == "STALE_CHAIN_CONTEXT"


def test_a_second_commit_while_one_is_being_asked_is_refused(short_dir):
    release, waiting = threading.Event(), threading.Event()

    def slow(expected):
        waiting.set()
        release.wait(5)
        return True

    server = _server(short_dir, confirm=_Asked(answer=slow))
    results = []
    worker = threading.Thread(target=lambda: results.append(server.answer(_request())))
    worker.start()
    assert waiting.wait(5)
    assert _refusal(server.answer(_request(current=7_200 + 360))) == "COMMIT_IN_FLIGHT"
    release.set()
    worker.join(5)
    assert results[0]["ok"] is True


def test_an_unrecordable_signature_is_not_given_out(short_dir):
    server = _server(short_dir)
    server.ledger.path.mkdir()  # the ledger cannot be appended
    assert _refusal(server.answer(_request())) == "LEDGER_UNAVAILABLE"


def test_a_corrupt_ledger_refuses(short_dir):
    server = _server(short_dir)
    server.ledger.path.write_text("not json\n")
    assert _refusal(server.answer(_request())) == "LEDGER_UNAVAILABLE"


# Across the real socket ------------------------------------------------------


def test_carbons_client_carries_the_request_and_counts_the_signature(short_dir):
    server = _server(short_dir).bind()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        signer = connect_signer(server.hotkey, socket_path=server.socket_path)
        before = signatures_obtained()
        body = _request()
        del body["protocol"], body["op"]
        answer = request_commitment(signer, body)
        assert answer["call"] == _call() and len(answer["signature"]) == 64
        assert signatures_obtained() == before + 1 and signer.issued == 1
        with pytest.raises(SignerFailure) as refused:
            request_commitment(signer, body)
        assert str(refused.value) == "signer_refused:ALREADY_COMMITTED_THIS_TEMPO"
        assert signatures_obtained() == before + 1
    finally:
        server.close()
        thread.join(timeout=0.1)  # a daemon thread blocked in accept


# B12 / D8: the key file at start ----------------------------------------------


@pytest.mark.parametrize(
    ("mode", "fragment"),
    [
        (0o640, "chmod 600"),
        (0o644, "chmod 600"),
        (0o604, "chmod 600"),
        (0o660, "chmod 600"),
    ],
)
def test_a_key_file_others_can_read_is_refused_with_the_fix(tmp_path, mode, fragment):
    key = tmp_path / "hotkey"
    key.write_text("{}")
    key.chmod(mode)
    problem = cm.key_file_problem(key)
    assert problem is not None and fragment in problem and str(key) in problem


def test_a_symlinked_key_file_is_refused(tmp_path):
    target = tmp_path / "real"
    target.write_text("{}")
    target.chmod(0o600)
    link = tmp_path / "hotkey"
    link.symlink_to(target)
    assert "symlink" in cm.key_file_problem(link)


def test_another_users_key_file_is_refused(tmp_path, monkeypatch):
    key = tmp_path / "hotkey"
    key.write_text("{}")
    key.chmod(0o600)
    other = os.getuid() + 1
    monkeypatch.setattr(cm.os, "getuid", lambda: other)
    assert "another user" in cm.key_file_problem(key)


def test_an_owner_only_key_file_is_accepted(tmp_path):
    key = tmp_path / "hotkey"
    key.write_text("{}")
    key.chmod(0o600)
    assert cm.key_file_problem(key) is None
    assert cm.key_file_problem(tmp_path / "missing") is None  # the SDK says so


def test_signer_start_refuses_before_opening_the_key(tmp_path, monkeypatch):
    key = tmp_path / "hotkey"
    key.write_text("{}")
    key.chmod(0o644)
    opened = []
    monkeypatch.setattr(signer_module, "load_hotkey", lambda **kw: opened.append(kw))
    with pytest.raises(SystemExit) as stopped:
        signer_module.main(["--key-file", str(key)])
    assert f"chmod 600 {key}" in str(stopped.value) and opened == []
    wallets = tmp_path / "wallets"
    hotkeys = wallets / "w" / "hotkeys"
    hotkeys.mkdir(parents=True)
    (hotkeys / "h").write_text("{}")
    (hotkeys / "h").chmod(0o640)
    with pytest.raises(SystemExit) as stopped:
        signer_module.main(
            ["--wallet", "w", "--hotkey", "h", "--wallet-path", str(wallets)]
        )
    assert "chmod 600" in str(stopped.value) and opened == []


def test_signer_start_fixes_the_commit_policy_from_the_record(tmp_path, monkeypatch):
    key = tmp_path / "hotkey"
    key.write_text("{}")
    key.chmod(0o600)
    built = {}

    class Stop(Exception):
        pass

    class Recording(SignerServer):
        def bind(self):
            built["policy"] = self.commit_policy
            raise Stop

    monkeypatch.setattr(signer_module, "load_hotkey", lambda **kw: _keypair())
    monkeypatch.setattr(signer_module, "SignerServer", Recording)
    monkeypatch.setattr(signer_module.cm, "load_policy", lambda: (POLICY, []))
    with pytest.raises(Stop):
        signer_module.main(["--key-file", str(key), "--socket", str(tmp_path / "s")])
    assert built["policy"] is POLICY and POLICY.netuid == 567


def test_the_checked_payload_is_the_unhashed_reconstruction():
    # Under 256 bytes the SDK signs the payload itself (extrinsics.py:150-168).
    checked = cm.check_request(POLICY, _request())
    assert checked["payload"] == _call() + b"".join(_parts())
    assert len(checked["payload"]) < 256
