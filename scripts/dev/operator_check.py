#!/usr/bin/env python3
"""Operator-identity check for a Lium GPU build node (LIUM_ADA_SWITCH_PLAN S2, V2 third-party compute condition 4).

Before the autoscaler rents a Lium (Bittensor SN51) node, it asks the door: is this node's operator a registered
Carbon participant? A node is refused when its SN51 ``miner_hotkey`` is itself a hotkey on the Carbon subnet
(``--netuid``, 116 on finney), or when the chain owner coldkey of that hotkey (``SubtensorModule.Owner``) is a coldkey
on the Carbon subnet. Fail closed: a hotkey whose owner cannot be read, or reads as the chain's default (zero)
account, is refused (``owner_unknown``).

Runs ON the door, under a python that has bittensor `carbon.chain.sdk.SDK_VERSION` and this checkout's ``carbon``:

    operator_check.py --network finney --endpoint wss://... --provider <id> --genesis-hash 0x... --netuid 116
        --hotkey <ss58> [--hotkey <ss58> ...]

One finalized, genesis-checked read (`carbon.chain.sdk._observe`, the door's own metagraph read) and each hotkey's
owner at that same block hash, over one connection. Prints ONE JSON object (``carbon.operator-check.v1``) on stdout.
Any failure to read the chain exits non-zero with the failure's type on stderr and prints nothing on stdout. It reads
public chain state only, signs and submits nothing, and decides nothing scientific.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

SCHEMA = "carbon.operator-check.v1"
MAX_HOTKEYS = 64
#: SS58 shape (`carbon.chain.external_signer`)
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{46,48}")
#: SS58 (prefix 42) of 32 zero bytes: what the ``SubtensorModule.Owner`` map answers for a hotkey it holds no owner of
ZERO_ACCOUNT = "5C4hrfjw9DjXZTzV3MwzrrAr9P1MJhSrvWGWqi1eSuyUpnhM"


def decide(hotkeys, carbon_hotkeys, carbon_coldkeys, owners):
    """One result per hotkey, in order: refuse a Carbon hotkey, a hotkey whose owner is a Carbon coldkey, and a hotkey
    whose owner is unknown (missing, malformed or the zero account)."""
    carbon_hotkeys, carbon_coldkeys = set(carbon_hotkeys), set(carbon_coldkeys)
    results = []
    for hotkey in hotkeys:
        owner = owners.get(hotkey)
        if (
            type(owner) is not str
            or not _SS58.fullmatch(owner)
            or owner == ZERO_ACCOUNT
        ):
            owner = None
        if hotkey in carbon_hotkeys:
            why = "carbon_hotkey"
        elif owner is None:
            why = "owner_unknown"
        elif owner in carbon_coldkeys:
            why = "carbon_coldkey"
        else:
            why = None
        results.append(
            {
                "hotkey": hotkey,
                "owner_coldkey": owner,
                "refuse": why is not None,
                "why": why,
            }
        )
    return results


def render(netuid, finalized_block, block_hash, results):
    """The one stdout line."""
    return json.dumps(
        {
            "schema": SCHEMA,
            "netuid": netuid,
            "finalized_block": finalized_block,
            "block_hash": block_hash,
            "results": results,
        },
        separators=(",", ":"),
    )


def _parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--network", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--genesis-hash", required=True)
    parser.add_argument("--netuid", required=True, type=int)
    parser.add_argument("--hotkey", required=True, action="append")
    return parser


def parse_args(argv):
    parser = _parser()
    args = parser.parse_args(argv)
    for hotkey in args.hotkey:
        if not _SS58.fullmatch(hotkey):
            parser.error("--hotkey: not an SS58 address")
    args.hotkey = list(dict.fromkeys(args.hotkey))
    if len(args.hotkey) > MAX_HOTKEYS:
        parser.error(f"--hotkey: at most {MAX_HOTKEYS}")
    if not 0 <= args.netuid <= 65535:
        parser.error("--netuid")
    return args


async def hotkey_owner(substrate, hotkey, block_hash):
    """The owner coldkey of ``hotkey`` at ``block_hash``: the ``SubtensorModule.Owner`` storage map (hotkey ->
    coldkey; the same storage read as `carbon.chain.localnet`'s registration check, through the backend query of
    `carbon.chain.permits`). The only chain-specific piece of this check."""
    return await substrate.query(
        "SubtensorModule", "Owner", [hotkey], block_hash=block_hash
    )


async def _observe_and_owners(context, hotkeys):
    from importlib.metadata import version

    from carbon.chain.models import ChainFailure, FailureCode
    from carbon.chain.sdk import SDK_VERSION, _observe

    if version("bittensor") != SDK_VERSION:
        raise ChainFailure(FailureCode.UNSUPPORTED)
    import bittensor as bt

    # the repo's own connection (`carbon.chain.sdk.BittensorReader._attempt` / `_capture`)
    substrate = bt.RpcSubstrate(
        context.endpoint,
        fallback_endpoints=[],
        archive_endpoints=[],
        retry_forever=False,
    )
    client = bt.Client(context.endpoint, substrate=substrate)
    try:
        await substrate.connect()
        snapshot = await _observe(bt, substrate, client, context)
        owners = {}
        for hotkey in hotkeys:
            try:
                owners[hotkey] = await hotkey_owner(
                    substrate, hotkey, snapshot.block_hash
                )
            # one unreadable owner is that node refused (owner_unknown), not the run failed
            except Exception as failure:  # noqa: BLE001
                print(
                    f"operator_check: owner unreadable: {type(failure).__name__}",
                    file=sys.stderr,
                )
        return snapshot, owners
    finally:
        await client.close()


def read_chain(args, hotkeys):
    """``(finalized_block, block_hash, [(hotkey, coldkey), ...], {hotkey: owner})`` at the finalized head."""
    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        # this checkout's carbon, not whatever the interpreter's environment holds
        sys.path.insert(0, root)
    from carbon.chain.models import ChainContext

    context = ChainContext(
        args.network, args.endpoint, args.provider, args.genesis_hash, args.netuid
    )
    snapshot, owners = asyncio.run(_observe_and_owners(context, hotkeys))
    participants = [(p.hotkey, p.coldkey) for p in snapshot.participants]
    return snapshot.finalized_block, snapshot.block_hash, participants, owners


def main(argv=None, *, read=read_chain):
    args = parse_args(argv)
    try:
        block, block_hash, participants, owners = read(args, args.hotkey)
    # any unread chain prints no verdict: the autoscaler then rents no node
    except Exception as failure:  # noqa: BLE001
        code = getattr(failure, "code", None)
        print(
            f"operator_check: chain read failed: {type(failure).__name__}"
            + (f" {getattr(code, 'value', code)}" if code is not None else ""),
            file=sys.stderr,
        )
        return 1
    results = decide(
        args.hotkey,
        (hotkey for hotkey, _ in participants),
        (coldkey for _, coldkey in participants),
        owners,
    )
    print(render(args.netuid, block, block_hash, results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
