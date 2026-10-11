"""Testnet-only auto-confirm of commitments (OWNER-SIGNER-TESTNET-AUTOCONFIRM-01).

A signer started with ``--auto-confirm-commitments <allow-list>`` signs a
strategy commitment without the terminal prompt only for testnet 567 and only
for a hotkey the owner listed. Every other case is refused, at start or per
request, and never falls back to the prompt. Without the flag nothing changes.

No chain and no real key: the hotkey is a public development URI and the
allow-lists are written here.
"""

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from carbon_miner_signer import SignerServer
from carbon_miner_signer import autoconfirm as ac
from carbon_miner_signer import commitment as cm
from carbon_miner_signer import signer as signer_module
from tests.cpu._signer_harness import in_thread_signer
from tests.cpu.test_miner_signer_commit import (
    CEILING,
    DIGEST,
    FINNEY,
    GENESIS,
    POLICY,
    ZERO_FEE,
    _Asked,
    _keypair,
    _parts,
    _record,
    _refusal,
    _request,
)

ROOT = Path(__file__).resolve().parents[2]
OTHER = "5" + "F" * 47  # an ss58-shaped address that is not the specimen's
MAINNET_POLICY, _ = cm.load_policy(
    _record(
        network={
            "name": "finney",
            "genesis_hash": FINNEY,
            "netuid": 567,
            "tempo_blocks": 360,
        }
    )
)


def _never(text, expected):
    raise AssertionError("the auto path asked the terminal")


def _allowlist(directory, *, hotkeys=None, mode=0o600, **changes):
    record = {
        "schema": ac.ALLOWLIST_SCHEMA,
        "network": "testnet",
        "netuid": 567,
        "hotkeys": [_keypair().ss58_address] if hotkeys is None else hotkeys,
        **changes,
    }
    path = Path(directory) / "allowlist.json"
    path.write_text(json.dumps(record))
    path.chmod(mode)
    return path


def _auto(directory, **options):
    return ac.load_allowlist(_allowlist(directory, **options))


def _auto_server(directory, *, policy=POLICY, auto=None, confirm=_never):
    log = io.StringIO()
    server = SignerServer(
        _keypair(),
        Path(directory) / "s.sock",
        log=log,
        commit_policy=policy,
        confirm=confirm,
        auto_confirm=auto if auto is not None else _auto(directory),
    )
    return server, log


# The auto path: signed, shown, recorded ---------------------------------------


def test_an_allow_listed_testnet_commitment_is_signed_without_asking(tmp_path):
    server, _ = _auto_server(tmp_path)
    response = server.answer(_request())
    assert response["ok"] is True and response["fee_ceiling_rao"] == CEILING
    from bittensor.sp_core import verify

    checked = cm.check_request(POLICY, _request())
    signature = bytes.fromhex(response["signature"][2:])
    assert verify(checked["payload"], signature, server.hotkey, 1)


def test_an_auto_confirm_is_shown_and_recorded_as_the_prompt_shows_it(tmp_path):
    server, log = _auto_server(tmp_path)
    assert server.answer(_request())["ok"] is True
    shown = log.getvalue()
    assert "AUTO-CONFIRMED (allow-listed testnet hotkey)" in shown
    checked = cm.check_request(POLICY, _request())
    # Exactly the manual prompt's lines: network, netuid, digest, fee, era.
    assert cm.prompt_lines(POLICY, checked, 0) in shown
    assert "testnet" in shown and "netuid    567" in shown and DIGEST in shown
    assert "0.000001000 TAO" in shown and "from block 7200" in shown
    assert "Type the last 8" not in shown
    (row,) = server.ledger.entries()
    assert row["confirmation"] == "AUTO-CONFIRMED (allow-listed testnet hotkey)"
    assert row["network"] == "testnet" and row["netuid"] == 567
    assert row["genesis_hash"] == GENESIS and row["digest"] == DIGEST
    assert row["fee_rao"] == 1_000 and row["era_current"] == 7_200
    assert row["tempo_index"] == 20


def test_the_per_tempo_limit_holds_on_the_auto_path(tmp_path):
    server, _ = _auto_server(tmp_path)
    assert server.answer(_request(current=7_200))["ok"] is True
    again, _ = _auto_server(tmp_path)  # a restarted signer, same ledger
    for current in (7_200, 7_200 + 359):
        refused = again.answer(_request(current=current))
        assert _refusal(refused) == "ALREADY_COMMITTED_THIS_TEMPO"
    assert again.answer(_request(current=7_200 + 360))["ok"] is True
    assert [row["tempo_index"] for row in again.ledger.entries()] == [20, 21]


@pytest.mark.parametrize("fee", [(CEILING + 1, 0), (1_900, 101), (None, 0)])
def test_over_the_fee_ceiling_is_refused_on_the_auto_path(tmp_path, fee):
    server, _ = _auto_server(tmp_path)
    assert _refusal(server.answer(_request(fee=fee))) in {
        "FEE_OVER_CEILING",
        "FEE_UNKNOWN",
    }
    assert server.ledger.entries() == []


def test_the_committed_zero_ceiling_holds_on_the_auto_path(tmp_path):
    policy, missing = cm.load_policy()
    assert missing == [] and policy.fee_ceiling_rao == 0
    server, _ = _auto_server(tmp_path, policy=policy)
    assert _refusal(server.answer(_request(fee=(1, 0)))) == "FEE_OVER_CEILING"
    assert server.answer(_request(fee=(0, 0)))["ok"] is True


def test_any_other_call_is_refused_on_the_auto_path(tmp_path):
    server, _ = _auto_server(tmp_path)
    call = bytes([5, 0]) + b"\x00" * 33 + b"\x04"  # Balances.transfer-shaped
    assert _refusal(server.answer(_request(call=call))) == "NOT_A_COMMITMENT"
    request = {**_request(), "confirmed": True}
    assert _refusal(server.answer(request)) == "MALFORMED_REQUEST"
    assert server.ledger.entries() == []


# The genesis lock ------------------------------------------------------------


def test_any_other_genesis_is_refused_at_start(tmp_path):
    with pytest.raises(ValueError, match="testnet netuid 567 only"):
        _auto_server(tmp_path, policy=MAINNET_POLICY)
    with pytest.raises(ValueError, match="not pinned"):
        _auto_server(tmp_path, policy=None)


def test_any_other_genesis_is_refused_per_request(tmp_path):
    server, _ = _auto_server(tmp_path)
    # A request for another chain never reaches the auto path...
    additional = "0x" + _parts(genesis=FINNEY)[1].hex()
    request = _request(genesis_hash=FINNEY, included_in_signed_data=additional)
    assert _refusal(server.answer(request)) == "WRONG_NETWORK"
    # ...and the auto path's own lock holds even if the policy it checks
    # against were another network's.
    server.commit_policy = MAINNET_POLICY
    assert _refusal(server.answer(request)) == "AUTO_CONFIRM_NOT_ALLOWED"
    with pytest.raises(cm.Refused) as refused:
        server.auto_confirm.check(POLICY, server.hotkey, FINNEY)
    assert refused.value.refusal is cm.CommitRefusal.AUTO_CONFIRM_NOT_ALLOWED
    assert server.ledger.entries() == []


def test_the_genesis_lock_is_testnet_567s():
    assert ac.TESTNET_GENESIS == GENESIS == POLICY.genesis_hash
    assert (ac.TESTNET_NETWORK, ac.TESTNET_NETUID) == ("testnet", 567)
    assert ac.TESTNET_GENESIS != FINNEY


# The allow-list ---------------------------------------------------------------


def test_an_unlisted_hotkey_is_refused_at_start_and_per_request(tmp_path):
    with pytest.raises(ValueError, match="not in the auto-confirm allow-list"):
        _auto_server(tmp_path, auto=_auto(tmp_path, hotkeys=[OTHER]))
    server, _ = _auto_server(tmp_path)
    server.auto_confirm = ac.AutoConfirm(path="x", hotkeys=frozenset({OTHER}))
    assert _refusal(server.answer(_request())) == "AUTO_CONFIRM_NOT_ALLOWED"
    assert server.ledger.entries() == []


@pytest.mark.parametrize(
    ("make", "fragment"),
    [
        (lambda d: _allowlist(d, mode=0o640), "chmod 600"),
        (lambda d: _allowlist(d, mode=0o604), "chmod 600"),
        (lambda d: _allowlist(d, mode=0o660), "chmod 600"),
        (lambda d: _allowlist(d, network="finney"), "network testnet"),
        (lambda d: _allowlist(d, netuid=566), "netuid 567"),
        (lambda d: _allowlist(d, netuid="567"), "netuid 567"),
        (lambda d: _allowlist(d, netuid=True), "netuid 567"),
        (lambda d: _allowlist(d, schema="v0"), "is not carbon.signer"),
        (lambda d: _allowlist(d, extra=1), "exactly"),
        (lambda d: _allowlist(d, hotkeys=[]), "distinct ss58"),
        (lambda d: _allowlist(d, hotkeys=[OTHER, OTHER]), "distinct ss58"),
        (lambda d: _allowlist(d, hotkeys=["not-an-address"]), "distinct ss58"),
        (lambda d: _allowlist(d, hotkeys=OTHER), "distinct ss58"),
        (
            lambda d: _allowlist(
                d, hotkeys=["5" + "F" * 46 + c for c in "ABCDEFGHJKLMNPQRS"]
            ),
            "1 to 16",
        ),
    ],
)
def test_a_bad_allow_list_refuses_start(tmp_path, make, fragment):
    with pytest.raises(ac.AllowListProblem, match=fragment):
        ac.load_allowlist(make(tmp_path))


def _written(directory, text, mode=0o600):
    path = Path(directory) / "allowlist.json"
    path.write_bytes(text if isinstance(text, bytes) else text.encode())
    path.chmod(mode)
    return path


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("{not json", "not valid JSON"),
        (b"\xff\xfe", "not valid JSON"),
        ("[]", "exactly"),
        ('{"schema": 1, "schema": 2}', "not valid JSON"),
        (" " * 4097, "too large"),
    ],
)
def test_a_malformed_allow_list_refuses_start(tmp_path, text, fragment):
    with pytest.raises(ac.AllowListProblem, match=fragment):
        ac.load_allowlist(_written(tmp_path, text))


def test_a_symlinked_missing_or_non_regular_allow_list_refuses_start(tmp_path):
    real = _allowlist(tmp_path)
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(ac.AllowListProblem, match="symlink"):
        ac.load_allowlist(link)
    with pytest.raises(ac.AllowListProblem, match="no auto-confirm allow-list"):
        ac.load_allowlist(tmp_path / "missing.json")
    folder = tmp_path / "folder"
    folder.mkdir(mode=0o700)
    with pytest.raises(ac.AllowListProblem, match="not a regular file"):
        ac.load_allowlist(folder)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo, 0o600)
    with pytest.raises(ac.AllowListProblem, match="not a regular file"):
        ac.load_allowlist(fifo)


def test_another_users_allow_list_refuses_start(tmp_path, monkeypatch):
    path = _allowlist(tmp_path)
    other = os.getuid() + 1
    monkeypatch.setattr(ac.os, "getuid", lambda: other)
    with pytest.raises(ac.AllowListProblem, match="another user"):
        ac.load_allowlist(path)


def test_a_sound_allow_list_is_read_once(tmp_path):
    path = _allowlist(tmp_path, hotkeys=[_keypair().ss58_address, OTHER])
    auto = ac.load_allowlist(path)
    assert auto.hotkeys == {_keypair().ss58_address, OTHER}
    server, _ = _auto_server(tmp_path, auto=auto)
    path.write_text("{}")  # a change after start is not read
    assert server.answer(_request())["ok"] is True
    assert server.auto_confirm is auto


# Start: the CLI ---------------------------------------------------------------


class _Stop(Exception):
    pass


def _start(tmp_path, monkeypatch, *extra, policy=POLICY):
    key = tmp_path / "hotkey"
    key.write_text("{}")
    key.chmod(0o600)
    opened, built = [], {}

    def load(**kw):
        opened.append(kw)
        return _keypair()

    class Recording(SignerServer):
        def bind(self):
            built["server"] = self
            raise _Stop

    monkeypatch.setattr(signer_module, "load_hotkey", load)
    monkeypatch.setattr(signer_module, "SignerServer", Recording)
    monkeypatch.setattr(signer_module.cm, "load_policy", lambda: (policy, []))
    argv = ["--key-file", str(key), "--socket", str(tmp_path / "s"), *extra]
    return argv, opened, built


def test_the_flag_starts_an_auto_confirming_signer(tmp_path, monkeypatch):
    allowlist = _allowlist(tmp_path)
    argv, opened, built = _start(
        tmp_path, monkeypatch, "--auto-confirm-commitments", str(allowlist)
    )
    with pytest.raises(_Stop):
        signer_module.main(argv)
    assert len(opened) == 1
    assert built["server"].auto_confirm.hotkeys == {_keypair().ss58_address}


def test_without_the_flag_the_signer_starts_as_before(tmp_path, monkeypatch):
    argv, opened, built = _start(tmp_path, monkeypatch)
    with pytest.raises(_Stop):
        signer_module.main(argv)
    assert len(opened) == 1 and built["server"].auto_confirm is None


@pytest.mark.parametrize("policy", [MAINNET_POLICY, None])
def test_the_flag_off_testnet_is_refused_before_the_key_opens(
    tmp_path, monkeypatch, policy
):
    allowlist = _allowlist(tmp_path)
    argv, opened, built = _start(
        tmp_path,
        monkeypatch,
        "--auto-confirm-commitments",
        str(allowlist),
        policy=policy,
    )
    with pytest.raises(SystemExit):
        signer_module.main(argv)
    assert opened == [] and built == {}


def test_a_bad_allow_list_is_refused_before_the_key_opens(tmp_path, monkeypatch):
    allowlist = _allowlist(tmp_path, mode=0o644)
    argv, opened, built = _start(
        tmp_path, monkeypatch, "--auto-confirm-commitments", str(allowlist)
    )
    with pytest.raises(SystemExit) as stopped:
        signer_module.main(argv)
    assert f"chmod 600 {allowlist}" in str(stopped.value)
    assert opened == [] and built == {}


def test_an_unlisted_expect_is_refused_before_the_key_opens(tmp_path, monkeypatch):
    allowlist = _allowlist(tmp_path, hotkeys=[OTHER])
    argv, opened, built = _start(
        tmp_path,
        monkeypatch,
        "--auto-confirm-commitments",
        str(allowlist),
        "--expect",
        _keypair().ss58_address,
    )
    with pytest.raises(SystemExit, match="not in the auto-confirm allow-list"):
        signer_module.main(argv)
    assert opened == [] and built == {}


def test_an_unlisted_loaded_key_is_refused_before_it_serves(tmp_path, monkeypatch):
    allowlist = _allowlist(tmp_path, hotkeys=[OTHER])
    argv, opened, built = _start(
        tmp_path, monkeypatch, "--auto-confirm-commitments", str(allowlist)
    )
    with pytest.raises(SystemExit, match="not in the auto-confirm allow-list"):
        signer_module.main(argv)
    assert len(opened) == 1 and built == {}


# Everything else is unchanged ------------------------------------------------


def test_message_signing_is_still_governed_by_receiver(tmp_path):
    import time

    from carbon.chain.external_signer import SignerFailure

    receiver = "5" + "E" * 47  # an ss58-shaped validator hotkey
    auto = _auto(tmp_path)

    def payload(hotkey, to, path=signer_module.PATH):
        lines = ["btauth/1", "sr25519", "POST", path, "0" * 64]
        return "\n".join([*lines, str(time.time_ns()), hotkey, to]).encode()

    with in_thread_signer(
        _keypair(), receivers=[receiver], commit_policy=POLICY, auto_confirm=auto
    ) as signer:
        assert len(signer.sign(payload(signer.ss58_address, receiver))) == 64
        with pytest.raises(SignerFailure, match="RECEIVER_NOT_ALLOWED"):
            signer.sign(payload(signer.ss58_address, OTHER))
        answer_key = payload(signer.ss58_address, receiver, "/carbon/v1/answer-key")
        with pytest.raises(SignerFailure, match="NOT_A_CARBON_REQUEST"):
            signer.sign(answer_key)


def test_without_the_flag_a_commit_still_asks_the_terminal(tmp_path):
    asked = _Asked()
    server = SignerServer(
        _keypair(),
        tmp_path / "s.sock",
        log=io.StringIO(),
        commit_policy=POLICY,
        confirm=asked,
    )
    assert server.auto_confirm is None
    assert server.answer(_request())["ok"] is True
    assert [expected for _, expected in asked.prompts] == [DIGEST[-8:]]
    (row,) = server.ledger.entries()
    # The manual ledger row is exactly as before: no auto-confirm marks.
    assert set(row) == {
        "schema",
        "digest",
        "netuid",
        "genesis_hash",
        "nonce",
        "era_current",
        "era_period",
        "tempo_index",
        "fee_rao",
        "signed_at",
    }


def test_the_manual_prompt_is_byte_for_byte_unchanged():
    checked = cm.check_request(POLICY, _request())
    hotkey, today, genesis = _keypair().ss58_address, 3, POLICY.genesis_hash
    expected = (
        f"\nCarbon asks to post an on-chain commitment with hotkey {hotkey}\n"
        f"  network   {POLICY.network} (genesis {genesis[:6]}...{genesis[-4:]})\n"
        f"  netuid    {POLICY.netuid}\n"
        f"  digest    {checked['digest']}\n"
        f"  fee       {checked['fee_rao'] / 1e9:.9f} TAO incl. any deposit, "
        f"Carbon's estimate (ceiling {POLICY.fee_ceiling_rao / 1e9:.9f} TAO), "
        "paid by the hotkey's coldkey; tip 0\n"
        f"  valid for {checked['era_period']} blocks from block "
        f"{checked['era_current']}; today: {today} signed, at most one per tempo\n"
        "  It replaces this hotkey's current commitment on this subnet.\n"
        "Type the last 8 characters of the digest to post, anything else to refuse: "
    )
    assert cm.prompt_text(POLICY, hotkey, checked, today) == expected


@pytest.mark.skipif(sys.platform != "linux", reason="controlling terminal")
def test_without_the_flag_and_without_a_terminal_nothing_is_signed():
    """The default signer, with no injected confirmation and no controlling
    terminal, refuses: the flag is the only way past the prompt."""
    script = (
        "import io, tempfile\n"
        "from pathlib import Path\n"
        "from carbon_miner_signer import SignerServer\n"
        "from tests.cpu.test_miner_signer_commit import POLICY, _keypair, _request\n"
        "d = tempfile.mkdtemp(prefix='cm-', dir='/tmp')\n"
        "s = SignerServer(_keypair(), Path(d) / 's.sock', log=io.StringIO(),"
        " commit_policy=POLICY)\n"
        "r = s.answer(_request())\n"
        "raise SystemExit(0 if r == {'ok': False, 'refusal': 'NOT_CONFIRMED'}"
        " and s.ledger.entries() == [] else 7)\n"
    )
    child = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        cwd=ROOT,
        env=dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT), *sys.path])),
        start_new_session=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert child.returncode == 0, child.stderr


def test_the_auto_confirm_module_imports_nothing_from_carbon():
    import ast

    tree = ast.parse((ROOT / "carbon_miner_signer" / "autoconfirm.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("carbon"), node.module
        if isinstance(node, ast.Import):
            assert all(not a.name.startswith("carbon") for a in node.names)


def test_the_launchpad_reports_the_new_refusal_as_itself():
    from carbon.chain.external_signer import COMMIT_REFUSALS

    assert {code.value for code in cm.CommitRefusal} == COMMIT_REFUSALS


def test_a_zero_ceiling_record_with_auto_confirm_still_refuses_any_fee(tmp_path):
    policy, _ = cm.load_policy(_record(fee={**ZERO_FEE, "ceiling_rao": 0}))
    server, _ = _auto_server(tmp_path, policy=policy)
    assert _refusal(server.answer(_request(fee=(0, 1)))) == "FEE_OVER_CEILING"
