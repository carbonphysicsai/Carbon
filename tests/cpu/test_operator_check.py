"""The Lium node operator-identity check (`scripts/dev/operator_check.py`, LIUM_ADA_SWITCH_PLAN S2, V2 third-party
compute condition 4): a node whose SN51 hotkey is a Carbon hotkey, or whose owner coldkey is a Carbon coldkey, or
whose owner is unknown, is refused; a chain read that fails prints no verdict. No bittensor import, no network.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "operator_check.py"
spec = importlib.util.spec_from_file_location("operator_check", SCRIPT)
check = importlib.util.module_from_spec(spec)
sys.modules["operator_check"] = check
spec.loader.exec_module(check)


def _ss58(tag):
    return ("5Op" + tag * 45)[:48]


CARBON_HOT, CARBON_COLD = _ss58("a"), _ss58("b")
NODE_HOT, NODE_COLD = _ss58("c"), _ss58("d")
BLOCK_HASH = "0x" + "cd" * 32
BASE = [
    "--network",
    "finney",
    "--endpoint",
    "wss://chain.example:443",
    "--provider",
    "public",
    "--genesis-hash",
    "0x" + "ef" * 32,
    "--netuid",
    "116",
]


def _many(count):
    letters = "ABCDEFGHJKLMNPQRSTUV"
    return [
        ("5Op" + "a" * 43 + letters[i // 20] + letters[i % 20]) for i in range(count)
    ]


def test_the_module_imports_no_chain_sdk_at_import():
    assert not hasattr(check, "bt") and not hasattr(check, "ChainContext")


def test_decide_refuses_a_carbon_hotkey_a_carbon_coldkey_and_an_unknown_owner():
    other = _ss58("e")
    results = check.decide(
        [CARBON_HOT, NODE_HOT, other, _ss58("f"), _ss58("g"), _ss58("h")],
        {CARBON_HOT},
        {CARBON_COLD},
        {
            CARBON_HOT: NODE_COLD,
            NODE_HOT: NODE_COLD,
            other: CARBON_COLD,
            _ss58("f"): check.ZERO_ACCOUNT,
            _ss58("g"): "not-an-address",
        },
    )
    assert [(r["refuse"], r["why"]) for r in results] == [
        (True, "carbon_hotkey"),
        (False, None),
        (True, "carbon_coldkey"),
        (True, "owner_unknown"),  # the Owner map's default: no owner
        (True, "owner_unknown"),  # malformed
        (True, "owner_unknown"),  # unread
    ]
    assert results[1]["owner_coldkey"] == NODE_COLD
    assert results[3]["owner_coldkey"] is None


def test_the_zero_account_is_the_ss58_of_32_zero_bytes():
    import hashlib

    payload = bytes([42]) + bytes(32)
    digest = (
        payload + hashlib.blake2b(b"SS58PRE" + payload, digest_size=64).digest()[:2]
    )
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number, text = int.from_bytes(digest, "big"), ""
    while number:
        number, rest = divmod(number, 58)
        text = alphabet[rest] + text
    assert text == check.ZERO_ACCOUNT


def test_main_prints_one_v1_object(capsys):
    def read(args, hotkeys):
        assert hotkeys == [NODE_HOT, CARBON_HOT]
        return 4242, BLOCK_HASH, [(CARBON_HOT, CARBON_COLD)], {NODE_HOT: NODE_COLD}

    argv = [*BASE, "--hotkey", NODE_HOT, "--hotkey", CARBON_HOT, "--hotkey", NODE_HOT]
    assert check.main(argv, read=read) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    reply = json.loads(out[0])
    assert list(reply) == [
        "schema",
        "netuid",
        "finalized_block",
        "block_hash",
        "results",
    ]
    assert reply["schema"] == "carbon.operator-check.v1"
    assert (reply["netuid"], reply["finalized_block"]) == (116, 4242)
    assert reply["block_hash"] == BLOCK_HASH
    assert reply["results"] == [
        {
            "hotkey": NODE_HOT,
            "owner_coldkey": NODE_COLD,
            "refuse": False,
            "why": None,
        },
        {
            "hotkey": CARBON_HOT,
            "owner_coldkey": None,
            "refuse": True,
            "why": "carbon_hotkey",
        },
    ]


def test_an_unread_chain_exits_non_zero_with_nothing_on_stdout(capsys):
    def read(args, hotkeys):
        raise ConnectionError("endpoint down")

    assert check.main([*BASE, "--hotkey", NODE_HOT], read=read) != 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ConnectionError" in captured.err


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--hotkey", "0OIl" * 12],
        ["--hotkey", "5short"],
        [x for h in _many(65) for x in ("--hotkey", h)],
    ],
)
def test_argv_refuses_a_missing_malformed_or_too_long_hotkey_list(extra):
    with pytest.raises(SystemExit):
        check.parse_args([*BASE, *extra])


def test_argv_takes_up_to_64_hotkeys_and_drops_repeats():
    hotkeys = _many(64)
    args = check.parse_args(
        [*BASE, *(x for h in [*hotkeys, hotkeys[0]] for x in ("--hotkey", h))]
    )
    assert args.hotkey == hotkeys and args.netuid == 116
