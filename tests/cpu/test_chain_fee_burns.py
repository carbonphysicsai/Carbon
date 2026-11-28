"""Unit, real-chain fixture (`8536949-6`), timeout, and adversarial event-decoding
tests for `carbon.chain.fee_burns`.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from carbon.chain.fee_burns import (
    ChainFeeBurnReader,
    FeeBurnNotFinalized,
    FeeBurnUnavailable,
    FinalizedBurnIndexer,
    extract_block_fee_burns,
    fee_remark,
    fee_remark_hash,
    parse_extrinsic_id,
    parse_fee_remark,
)
from carbon.chain.models import ChainContext, ChainFailure, FailureCode
from carbon.challenge_validator.submission_fee import FeeLedger

HOTKEY_A = "5C4hrfjw9DjXZTzV3MwzrrAr9P1MJhSrvWGWqi1eSuyUpnhM"
COLDKEY_A = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
RECEIVER_A = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
GENESIS = "0x2f0555cc76fc2840a25a6ea3b9637146806f1f44b090c175ffde2a7e5ab36c03"
BHASH = "0x" + "ab" * 32
CONTEXT = ChainContext("finney", "wss://chain.example", "finney", GENESIS, 116)

#: Verbatim `System.Events` records captured on Bittensor Testnet 567 block #8,536,949
#: (`0xc2c28d47411aab04142a65560d036da099f687d10a90533704c514ce8dbcc55d`), extrinsic 6 (`H9`).
REAL_TESTNET_8536949_BLOCK_HASH = (
    "0xc2c28d47411aab04142a65560d036da099f687d10a90533704c514ce8dbcc55d"
)
REAL_TESTNET_8536949_EXT6_EVENTS = [
    {
        "phase": "ApplyExtrinsic",
        "extrinsic_idx": 6,
        "event": {
            "event_index": "0508",
            "module_id": "Balances",
            "event_id": "Withdraw",
            "attributes": {
                "who": "5HbBYtb4d5Q8MBatfGpnyR2tndYk1R7L2QiRyTPtutCYCFU8",
                "amount": 1008543,
            },
        },
    },
    {
        "phase": "ApplyExtrinsic",
        "extrinsic_idx": 6,
        "event": {
            "event_index": "0502",
            "module_id": "Balances",
            "event_id": "Transfer",
            "attributes": {
                "from": "5HbBYtb4d5Q8MBatfGpnyR2tndYk1R7L2QiRyTPtutCYCFU8",
                "to": "5EYCAe5jLQhn6ofDSw6B2KCu7TbKZrpzM3fJVoDhCLKLmP5E",
                "amount": 25000000,
            },
        },
    },
    {
        "phase": "ApplyExtrinsic",
        "extrinsic_idx": 6,
        "event": {
            "event_index": "0702",
            "module_id": "SubtensorModule",
            "event_id": "StakeAdded",
            "attributes": [
                "5HbBYtb4d5Q8MBatfGpnyR2tndYk1R7L2QiRyTPtutCYCFU8",
                "5HbBYtb4d5Q8MBatfGpnyR2tndYk1R7L2QiRyTPtutCYCFU8",
                25000000,
                179007894916,
                567,
                12588,
            ],
        },
    },
    {
        "phase": "ApplyExtrinsic",
        "extrinsic_idx": 6,
        "event": {
            "event_index": "0762",
            "module_id": "SubtensorModule",
            "event_id": "AlphaBurned",
            "attributes": [
                "5HbBYtb4d5Q8MBatfGpnyR2tndYk1R7L2QiRyTPtutCYCFU8",
                "5HbBYtb4d5Q8MBatfGpnyR2tndYk1R7L2QiRyTPtutCYCFU8",
                179007894916,
                567,
            ],
        },
    },
    {
        "phase": "ApplyExtrinsic",
        "extrinsic_idx": 6,
        "event": {
            "event_index": "077d",
            "module_id": "SubtensorModule",
            "event_id": "AddStakeBurn",
            "attributes": {
                "netuid": 567,
                "hotkey": "5HbBYtb4d5Q8MBatfGpnyR2tndYk1R7L2QiRyTPtutCYCFU8",
                "amount": 25000000,
                "alpha": 179007894916,
            },
        },
    },
    {
        "phase": "ApplyExtrinsic",
        "extrinsic_idx": 6,
        "event": {
            "event_index": "0b03",
            "module_id": "Utility",
            "event_id": "ItemCompleted",
            "attributes": None,
        },
    },
    {
        "phase": "ApplyExtrinsic",
        "extrinsic_idx": 6,
        "event": {
            "event_index": "0005",
            "module_id": "System",
            "event_id": "Remarked",
            "attributes": {
                "sender": "5HbBYtb4d5Q8MBatfGpnyR2tndYk1R7L2QiRyTPtutCYCFU8",
                "hash": "0x162f98b4df27d5fa69335355924578393e923708da3b98063354b49dbe268ddd",
            },
        },
    },
    {
        "phase": "ApplyExtrinsic",
        "extrinsic_idx": 6,
        "event": {
            "event_index": "0b01",
            "module_id": "Utility",
            "event_id": "BatchCompleted",
            "attributes": None,
        },
    },
    {
        "phase": "ApplyExtrinsic",
        "extrinsic_idx": 6,
        "event": {
            "event_index": "0000",
            "module_id": "System",
            "event_id": "ExtrinsicSuccess",
            "attributes": {
                "dispatch_info": {
                    "weight": {"ref_time": 3973677496, "proof_size": 21106},
                    "class": "Normal",
                    "pays_fee": "Yes",
                }
            },
        },
    },
]


class _BalanceObj:
    def __init__(self, rao: int):
        self.rao = rao


def _burn_events(
    *,
    idx: int = 3,
    netuid: int = 116,
    hotkey: str = HOTKEY_A,
    receiver: str = RECEIVER_A,
    payer: str = COLDKEY_A,
    amount_rao: int = 25_000_000,
    alpha_rao: int = 1_865_000_000,
    challenge_id: str = "electric-motor-magnetics",
    extra_events: list[dict] = (),
    include_success: bool = True,
) -> list[dict]:
    rhash = fee_remark_hash(netuid, challenge_id, receiver, hotkey)
    evs = [
        {
            "phase": "ApplyExtrinsic",
            "extrinsic_idx": idx,
            "event": {
                "module_id": "SubtensorModule",
                "event_id": "AddStakeBurn",
                "attributes": {
                    "netuid": netuid,
                    "hotkey": hotkey,
                    "amount": _BalanceObj(amount_rao),
                    "alpha": alpha_rao,
                },
            },
        },
        {
            "phase": "ApplyExtrinsic",
            "extrinsic_idx": idx,
            "event": {
                "module_id": "System",
                "event_id": "Remarked",
                "attributes": {"sender": payer, "hash": rhash},
            },
        },
        *extra_events,
    ]
    if include_success:
        evs.append(
            {
                "phase": "ApplyExtrinsic",
                "extrinsic_idx": idx,
                "event": {
                    "module_id": "System",
                    "event_id": "ExtrinsicSuccess",
                    "attributes": {},
                },
            }
        )
    return evs


def test_real_testnet_567_block_8536949_extrinsic_6_decodes_exact_values():
    """Verify live Subtensor runtime 497 event payload (`H9`)."""
    burns = extract_block_fee_burns(
        REAL_TESTNET_8536949_EXT6_EVENTS,
        block=8_536_949,
        block_hash=REAL_TESTNET_8536949_BLOCK_HASH,
        netuid=567,
    )
    assert len(burns) == 1
    b = burns[0]
    assert b.extrinsic_id == "8536949-6"
    assert b.block == 8_536_949
    assert b.extrinsic_idx == 6
    assert b.netuid == 567
    assert b.hotkey == "5HbBYtb4d5Q8MBatfGpnyR2tndYk1R7L2QiRyTPtutCYCFU8"
    assert b.amount_rao == 25_000_000
    assert b.alpha_burned_rao == 179_007_894_916
    assert (
        b.remark_hash
        == "0x162f98b4df27d5fa69335355924578393e923708da3b98063354b49dbe268ddd"
    )


def test_v2_remark_and_extrinsic_id_codecs_enforce_ss58_checksums():
    raw = fee_remark(116, "electric-motor-magnetics", RECEIVER_A, HOTKEY_A)
    assert (
        raw
        == f"carbon.fee.v2|116|electric-motor-magnetics|{RECEIVER_A}|{HOTKEY_A}".encode(
            "ascii"
        )
    )
    assert parse_fee_remark(raw) == {
        "netuid": 116,
        "challenge_id": "electric-motor-magnetics",
        "receiver": RECEIVER_A,
        "hotkey": HOTKEY_A,
    }
    assert parse_fee_remark("0x" + raw.hex()) == parse_fee_remark(raw)
    bad_checksum_ss58 = HOTKEY_A[:-1] + ("1" if HOTKEY_A[-1] != "1" else "2")
    for bad_remark in (
        f"carbon.fee.v1|116|electric-motor-magnetics|{HOTKEY_A}",
        f"carbon.fee.v2|0116|electric-motor-magnetics|{RECEIVER_A}|{HOTKEY_A}",
        f"carbon.fee.v2|116|UPPERCASE|{RECEIVER_A}|{HOTKEY_A}",
        f"carbon.fee.v2|116|electric-motor-magnetics|not-ss58|{HOTKEY_A}",
        f"carbon.fee.v2|116|electric-motor-magnetics|{RECEIVER_A}|{bad_checksum_ss58}",
        f"carbon.fee.v2|116|electric-motor-magnetics|{RECEIVER_A}|{HOTKEY_A}|extra",
    ):
        assert parse_fee_remark(bad_remark) is None

    with pytest.raises(ValueError):
        fee_remark(116, "electric-motor-magnetics", bad_checksum_ss58, HOTKEY_A)

    assert parse_extrinsic_id("9597065-3") == (9597065, 3)
    assert parse_extrinsic_id("0-0") == (0, 0)
    for bad_ext in ("09597065-3", "9597065-03", "9597065", "-1-2", "abc-1", 123):
        assert parse_extrinsic_id(bad_ext) is None


def test_named_only_add_stake_burn_and_accountid_tuple_decoding_plus_spoof_rejections():
    valid = _burn_events()
    burns = extract_block_fee_burns(valid, block=9600100, block_hash=BHASH, netuid=116)
    assert len(burns) == 1
    assert burns[0].extrinsic_id == "9600100-3"
    assert burns[0].amount_rao == 25_000_000
    assert burns[0].alpha_burned_rao == 1_865_000_000
    assert burns[0].hotkey == HOTKEY_A

    # AccountId32 as 32-int tuple AND nested 1-tuple decode identically (`H9`)
    from bittensor.sp_core import ss58_decode

    decoded_pk = ss58_decode(HOTKEY_A)
    hk_bytes = (
        bytes(decoded_pk)
        if isinstance(decoded_pk, (bytes, bytearray))
        else bytes.fromhex(decoded_pk.removeprefix("0x"))
    )
    tuple_acct_evs = [
        {
            "phase": {"ApplyExtrinsic": 7},
            "event": {
                "pallet": "SubtensorModule",
                "name": "AddStakeBurn",
                "attributes": {
                    "netuid": 116,
                    "hotkey": (tuple(hk_bytes),),
                    "amount": 25_000_000,
                    "alpha": 1_900_000_000,
                },
            },
        },
        {
            "phase": {"ApplyExtrinsic": 7},
            "event": {
                "pallet": "System",
                "name": "Remarked",
                "attributes": {
                    "sender": list(hk_bytes),
                    "hash": fee_remark_hash(
                        116, "f08-ribbed-bracket", RECEIVER_A, HOTKEY_A
                    ),
                },
            },
        },
        {
            "phase": {"ApplyExtrinsic": 7},
            "event": {"pallet": "System", "name": "ExtrinsicSuccess", "params": {}},
        },
    ]
    t_burns = extract_block_fee_burns(
        tuple_acct_evs, block=9600101, block_hash=BHASH, netuid=116
    )
    assert len(t_burns) == 1
    assert t_burns[0].hotkey == HOTKEY_A
    assert t_burns[0].payer == HOTKEY_A

    # Positional 4-tuple AddStakeBurn MUST fail closed (`H9`: prevents amount/alpha swap)!
    positional_burn = [
        {
            "phase": {"ApplyExtrinsic": 2},
            "event": {
                "pallet": "SubtensorModule",
                "name": "AddStakeBurn",
                "params": [116, HOTKEY_A, 25_000_000, 1_900_000_000],
            },
        },
        *tuple_acct_evs[1:],
    ]
    assert (
        extract_block_fee_burns(
            positional_burn, block=9600101, block_hash=BHASH, netuid=116
        )
        == ()
    )

    # Spoof checks: BatchInterrupted, ExtrinsicFailed, Proxy Err, Wrong netuid, 2 remarks
    for spoof in (
        _burn_events(
            extra_events=[
                {
                    "phase": "ApplyExtrinsic",
                    "extrinsic_idx": 3,
                    "event": {
                        "module_id": "Utility",
                        "event_id": "BatchInterrupted",
                        "attributes": {"index": 0},
                    },
                }
            ]
        ),
        _burn_events(
            include_success=False,
            extra_events=[
                {
                    "phase": "ApplyExtrinsic",
                    "extrinsic_idx": 3,
                    "event": {
                        "module_id": "System",
                        "event_id": "ExtrinsicFailed",
                        "attributes": {},
                    },
                }
            ],
        ),
        _burn_events(
            extra_events=[
                {
                    "phase": "ApplyExtrinsic",
                    "extrinsic_idx": 3,
                    "event": {
                        "module_id": "Proxy",
                        "event_id": "ProxyExecuted",
                        "attributes": {"result": {"Err": "BadOrigin"}},
                    },
                }
            ]
        ),
        _burn_events(netuid=89),
        _burn_events(
            extra_events=[
                {
                    "phase": "ApplyExtrinsic",
                    "extrinsic_idx": 3,
                    "event": {
                        "module_id": "System",
                        "event_id": "Remarked",
                        "attributes": {
                            "sender": COLDKEY_A,
                            "hash": fee_remark_hash(
                                116, "f08-ribbed-bracket", RECEIVER_A, HOTKEY_A
                            ),
                        },
                    },
                }
            ]
        ),
    ):
        assert (
            extract_block_fee_burns(spoof, block=9600100, block_hash=BHASH, netuid=116)
            == ()
        )


def test_reader_timeout_nonblocking_range_scan_pruning_and_indexer_watchdog(tmp_path):
    """Verify `H4` (hung RPC timeout does not wedge executor exit), `H15` (range scan),
    and block-index pruning."""
    blocks = {
        100: _burn_events(idx=1),
        101: [],
        102: _burn_events(idx=4, challenge_id="f08-ribbed-bracket"),
    }
    head = 102

    async def fake_head(_ctx):
        return head

    async def fake_block(_ctx, b):
        if b > head:
            raise FeeBurnNotFinalized("ahead")
        return head, BHASH, blocks.get(b, [])

    range_calls = []

    async def fake_range(_ctx, s, e):
        range_calls.append((s, e))
        upper = min(e, head)
        return head, {b: (BHASH, blocks.get(b, [])) for b in range(s, upper + 1)}

    reader = ChainFeeBurnReader(
        CONTEXT,
        fetch_block=fake_block,
        fetch_head=fake_head,
        fetch_range=fake_range,
    )
    with pytest.raises(FeeBurnNotFinalized):
        reader.read_block(103)

    # Single-call range scan (`H15`)
    r_head, r_map = reader.read_blocks_range(100, 102)
    assert r_head == 102 and len(range_calls) == 1
    assert len(r_map[100]) == 1 and len(r_map[101]) == 0 and len(r_map[102]) == 1

    ledger = FeeLedger(
        tmp_path / "fees.sqlite3", expected_netuid=116, expected_genesis_hash=GENESIS
    )
    logs = []
    indexer = FinalizedBurnIndexer(
        reader,
        ledger,
        max_lookback_blocks=10,
        log_fn=lambda ev, **kw: logs.append((ev, kw)),
    )

    assert indexer.poll_once() == 0
    assert ledger.indexer_cursor() == 102

    indexer.ensure_block(100, known_finalized_head=102, min_allowed_block=95)
    assert ledger.is_block_indexed(100)
    assert ledger.unspent_burns_for_hotkey(
        netuid=116,
        challenge_id="electric-motor-magnetics",
        receiver=RECEIVER_A,
        hotkey=HOTKEY_A,
        min_block=95,
        known_finalized_head=102,
    ) == ["100-1"]

    # Dynamic lookback (`update_lookback`): block 50 ignored at lookback=10, indexed once raised to 60!
    indexer.ensure_block(50, known_finalized_head=102, min_allowed_block=10)
    assert not ledger.is_block_indexed(50)
    indexer.update_lookback(60)
    indexer.ensure_block(50, known_finalized_head=102, min_allowed_block=10)
    assert ledger.is_block_indexed(50)

    # Pruning keeps observed_burns intact while trimming old block markers
    indexer.update_lookback(10)
    head = 130
    assert indexer.poll_once() > 0
    assert not ledger.is_block_indexed(50)
    # `100-1` burn row itself is still stored in `observed_burns`
    assert ledger.unspent_burns_for_hotkey(
        netuid=116,
        challenge_id="electric-motor-magnetics",
        receiver=RECEIVER_A,
        hotkey=HOTKEY_A,
        min_block=95,
        known_finalized_head=105,
    ) == ["100-1"]

    # Hung coroutine fails closed within `rpc_timeout_s` without wedging (`H4`)!
    async def hung_head(_ctx):
        await asyncio.sleep(60.0)
        return 999

    hung_reader = ChainFeeBurnReader(CONTEXT, fetch_head=hung_head, rpc_timeout_s=1.0)
    t0 = time.monotonic()
    with pytest.raises(FeeBurnUnavailable):
        hung_reader.finalized_head()
    assert time.monotonic() - t0 < 4.0

    async def broken_block(_ctx, _b):
        raise ChainFailure(FailureCode.UNAVAILABLE)

    bad_reader = ChainFeeBurnReader(
        CONTEXT, fetch_block=broken_block, fetch_head=fake_head
    )
    with pytest.raises(FeeBurnUnavailable):
        bad_reader.read_block(100)


def test_archive_endpoint_validation_genesis_host_mismatch_shared_prune_and_watchdog(
    tmp_path,
):
    """Regression for `H4`, `L2`, and shared-ledger lookback pruning:
    - Bare string `archive_endpoints` raises `ValueError` (never split into characters!).
    - `FeeLedger` refuses mismatched `netuid`, `genesis_hash`, or `host_id`.
    - Shared-ledger `effective_prune_lookback` honors the largest lookback across doors.
    - `FinalizedBurnIndexer.ensure_running()` restarts a dead daemon thread and emits
      `fee_indexer_watchdog_restart` + `fee_indexer_degraded`.
    """
    from carbon.chain.fee_burns import (
        DEFAULT_ARCHIVE_ENDPOINTS,
        MIN_RUNTIME_SPEC_VERSION,
    )

    assert MIN_RUNTIME_SPEC_VERSION == 497

    # 1. Default and explicit list archive endpoints vs bare string / http rejection (`H4`)
    r_default = ChainFeeBurnReader(CONTEXT)
    assert r_default.archive_endpoints == DEFAULT_ARCHIVE_ENDPOINTS["finney"]
    r_custom = ChainFeeBurnReader(
        CONTEXT, archive_endpoints=["wss://archive-custom.example:443"]
    )
    assert r_custom.archive_endpoints == ("wss://archive-custom.example:443",)
    for bad_eps in ("wss://split-me.example:443", ["http://not-ws.example"], [""]):
        with pytest.raises((TypeError, ValueError)):
            ChainFeeBurnReader(CONTEXT, archive_endpoints=bad_eps)  # type: ignore[arg-type]

    # 2. `FeeLedger` genesis, netuid, and host_id binding (`L2`, `N8`)
    db_path = tmp_path / "shared_116.sqlite3"
    ldg = FeeLedger(
        db_path,
        expected_netuid=116,
        expected_genesis_hash=GENESIS,
        expected_host_id="machine:box-alpha",
    )
    with pytest.raises(FeeBurnUnavailable, match="netuid_mismatch"):
        FeeLedger(db_path, expected_netuid=567)
    with pytest.raises(FeeBurnUnavailable, match="genesis_hash_mismatch"):
        FeeLedger(db_path, expected_genesis_hash="0x" + "ff" * 32)
    with pytest.raises(FeeBurnUnavailable, match="host_id_mismatch"):
        FeeLedger(db_path, expected_host_id="machine:box-beta")

    # 3. Shared-ledger pruning honors `MAX(max_lookback_blocks)` across doors!
    ldg.register_lookback(500)
    ldg.register_lookback(10)
    assert ldg.effective_prune_lookback(10) == 500
    ldg.record_indexed_block(200, [])

    cur_head = [600]

    async def dyn_head(_ctx):
        return cur_head[0]

    async def empty_blk(_ctx, _b):
        return cur_head[0], BHASH, []

    short_idx = FinalizedBurnIndexer(
        ChainFeeBurnReader(CONTEXT, fetch_head=dyn_head, fetch_block=empty_blk),
        ldg,
        max_lookback_blocks=10,
    )
    short_idx.poll_once()  # initializes cursor = 600

    cur_head[0] = 605
    short_idx.poll_once()
    # Because `effective_prune_lookback` is 500 (`2 * 500 = 1000 > 605`), block 200 is NOT pruned!
    assert ldg.is_block_indexed(200)

    # 4. Watchdog restart + degraded health telemetry (`H4`)
    events = []
    fail_mode = [True]

    async def flaky_head(_ctx):
        if fail_mode[0]:
            raise ChainFailure(FailureCode.UNAVAILABLE)
        return 605

    wd_idx = FinalizedBurnIndexer(
        ChainFeeBurnReader(CONTEXT, fetch_head=flaky_head, fetch_block=empty_blk),
        ldg,
        poll_interval_s=0.05,
        log_fn=lambda ev, **kw: events.append((ev, kw)),
    )
    wd_idx.start()
    try:
        deadline = time.monotonic() + 2.0
        while wd_idx.consecutive_failures < 3 and time.monotonic() < deadline:
            time.sleep(0.03)
        snap = wd_idx.ensure_running()
        assert snap["degraded"] is True
        assert any(ev == "fee_indexer_degraded" for ev, _ in events)

        # Simulate dead background thread -> `ensure_running()` restarts it!
        wd_idx._stop.set()
        wd_idx._thread.join(timeout=1.0)
        wd_idx._stop.clear()
        fail_mode[0] = False
        restarted = wd_idx.ensure_running()
        assert restarted["alive"] is True
        assert any(ev == "fee_indexer_watchdog_restart" for ev, _ in events)
    finally:
        wd_idx.stop(timeout=1.0)
