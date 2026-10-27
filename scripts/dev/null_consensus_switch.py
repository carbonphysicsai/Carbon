#!/usr/bin/env python3
"""Switch testnet netuid 567 to Null consensus: the owner's one extrinsic, dry by default.

Runbook N section (DAY_ONE_4090_RUNBOOK_20261027, Validator): the owner signs
`AdminUtils.sudo_set_epoch_consensus(netuid=567, mode=Null)` with the subnet-owner coldkey. btcli
9.23.2 cannot encode `EpochConsensus`, so this script composes the call through the pinned bittensor
SDK from the LIVE metadata and signs through the SDK's own wallet.

    python scripts/dev/null_consensus_switch.py switch                      # dry run (default): prints only
    python scripts/dev/null_consensus_switch.py switch --submit --wallet-name NAME [--wallet-path DIR]
    python scripts/dev/null_consensus_switch.py check-weights --operator FILE --standing FILE

`switch` refuses, with a closed code and nothing signed, unless ALL of these hold:
- the chain's genesis is the pinned testnet genesis and the netuid is 567;
- the live runtime is at least spec 482 (the first release with the Null-epoch scheduler fix);
- the call composed from the live metadata is byte-for-byte 0x136f370201;
- `TimelockedWeightCommits` has no entry for any of the 16 mechanism indices of 567 (the chain
  itself refuses the switch with `InvalidValue` while one is pending);
- (`--submit` only) the wallet's coldkey is the live `SubnetOwner[567]` and the owner typed the
  netuid back.
Already Null is reported and is not an error. After inclusion it reads back 567's epoch consensus
and the validator-permit holders and prints both; anything but `Null` exits 4.

The wallet password is never an argument, never read, logged or stored here: the SDK decrypts the
coldkey itself and prompts for it (`bt.Wallet(...).coldkey`). Nothing is signed without `--submit`.

`check-weights` is read-only. Under Null only the largest-stake UID holds a validator permit, so the
weights signer must be UID 0's hotkey; it parses the weights operator config and the standing
authorization (owner-only JSON, as `validator_setup` and `testnet_winner_publication.load_standing`
read them) and checks that both name that hotkey on chain.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

TESTNET_GENESIS = "0x8f9cf856bf558a14440e75569c9e58594757048d7b3a84b5d25f6bd978263105"
DEFAULT_ENDPOINT = "wss://test.finney.opentensor.ai:443"
NETUID = 567
#: pallet 0x13, call_index 111 (0x6f), netuid 567 as u16 little-endian, EpochConsensus::Null (index 1).
EXPECTED_CALL_HEX = "0x136f370201"
#: Spec of the first subtensor release (v482) that carries commit c7aa77e, "Run a due Null epoch first".
MINIMUM_SPEC_VERSION = 482
#: The chain probes every mechanism index 0..16 for a pending timelocked commit before it switches.
MECHANISM_SLOTS = 16
SUBNET_SLOTS = 4096
#: UID 0's hotkey on 567 (live `SubnetOwnerHotkey`, Carbon's publisher): the only weights signer under Null.
WEIGHTS_SIGNER_HOTKEY = "5HWGPxuumoCdSXmbT62wNEnBN4rgU1WZXdPJfw4zqjLqV1wR"
#: The receiver/copy hotkey (UID 12): identifies the grading receiver; it must NOT sign weights under Null.
RECEIVER_HOTKEY = "5DWznJMnCeoevFSwsck7LXdYBWAbiw1G1qrxnghqSHqQj2qr"

EXIT_OK, EXIT_REFUSED, EXIT_SUBMIT_FAILED, EXIT_NOT_NULL = 0, 2, 3, 4


class Refused(Exception):
    """A closed refusal: `code` says which rule, `detail` says what was seen."""

    def __init__(self, code, detail=""):
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _value(item):
    return getattr(item, "value", item)


def _hex(value):
    return "0x" + bytes(value).hex() if isinstance(value, (bytes, bytearray)) else value


def call_hex(call):
    """The composed call's bytes as 0x-hex (the SDK's `CallBytes.data`)."""
    return "0x" + bytes(call.data).hex()


async def compose_null(substrate, netuid, block_hash):
    return await substrate.raw.compose_call(
        "AdminUtils",
        "sudo_set_epoch_consensus",
        {"netuid": netuid, "mode": "Null"},
        block_hash=block_hash,
    )


async def pending_commit_indices(substrate, netuid, block_hash):
    """Storage indices of 567's mechanisms that hold at least one timelocked commit."""
    found = []
    for mechanism in range(MECHANISM_SLOTS):
        index = netuid + SUBNET_SLOTS * mechanism
        rows = await substrate.raw.query_map(
            "SubtensorModule", "TimelockedWeightCommits", [index], block_hash=block_hash
        )
        async for _ in rows:
            found.append(index)
            break
    return found


async def read_state(substrate, netuid, block_hash):
    """567's epoch consensus and the validator-permit holders, read at `block_hash`."""
    raw = substrate.raw
    mode = _value(
        await raw.query(
            "SubtensorModule", "SubnetEpochConsensus", [netuid], block_hash=block_hash
        )
    )
    permits = _value(
        await raw.query(
            "SubtensorModule", "ValidatorPermit", [netuid], block_hash=block_hash
        )
    )
    holders = []
    for uid, permitted in enumerate(permits or []):
        if permitted:
            hotkey = _value(
                await raw.query(
                    "SubtensorModule", "Keys", [netuid, uid], block_hash=block_hash
                )
            )
            holders.append({"uid": uid, "hotkey": hotkey})
    return {"epoch_consensus": mode, "permit_holders": holders}


async def make_plan(substrate, netuid):
    """Every refusal rule, in order, with nothing signed. Returns what a submission would carry."""
    if netuid != NETUID:
        raise Refused("NETUID_NOT_567", f"this script switches netuid {NETUID} only")
    genesis = await substrate.block_hash(0)
    if str(genesis).lower() != TESTNET_GENESIS:
        raise Refused("NOT_THE_PINNED_TESTNET_GENESIS", str(genesis))
    head = await substrate.raw.get_chain_finalised_head()
    spec = await substrate.spec_version()
    if spec < MINIMUM_SPEC_VERSION:
        raise Refused(
            "RUNTIME_BEFORE_THE_NULL_EPOCH_FIX", f"spec {spec} < {MINIMUM_SPEC_VERSION}"
        )
    call = await compose_null(substrate, netuid, head)
    composed = call_hex(call)
    if composed != EXPECTED_CALL_HEX:
        raise Refused(
            "CALL_DATA_DIFFERS_FROM_THE_REVIEWED_ONE",
            f"{composed} != {EXPECTED_CALL_HEX}",
        )
    state = await read_state(substrate, netuid, head)
    owner = _value(
        await substrate.raw.query(
            "SubtensorModule", "SubnetOwner", [netuid], block_hash=head
        )
    )
    pending = []
    if state["epoch_consensus"] != "Null":
        pending = await pending_commit_indices(substrate, netuid, head)
        if pending:
            raise Refused("TIMELOCKED_COMMIT_PENDING", f"storage indices {pending}")
    return {
        "genesis": genesis,
        "finalized_hash": head,
        "spec_version": spec,
        "call": call,
        "call_hex": composed,
        "call_hash": _hex(getattr(call, "call_hash", None)),
        "owner": owner,
        "state": state,
        "already_null": state["epoch_consensus"] == "Null",
    }


def _print_plan(plan, out):
    print(f"genesis            {plan['genesis']} (pinned testnet)", file=out)
    print(
        f"runtime spec       {plan['spec_version']} (>= {MINIMUM_SPEC_VERSION})",
        file=out,
    )
    print(
        f"call data          {plan['call_hex']} (= the reviewed {EXPECTED_CALL_HEX})",
        file=out,
    )
    print(f"call hash          {plan['call_hash']}", file=out)
    print(f"subnet owner       {plan['owner']}", file=out)
    print(f"epoch consensus    {plan['state']['epoch_consensus']}", file=out)
    holders = [f"UID {h['uid']} {h['hotkey']}" for h in plan["state"]["permit_holders"]]
    print(f"permit holders     {len(holders)}: {'; '.join(holders)}", file=out)
    print("pending commits    none (checked 16 mechanism indices)", file=out)


def open_wallet(name, path):
    """The SDK wallet; its coldkey is decrypted (and the password prompted) only when asked for."""
    import bittensor as bt

    return bt.Wallet(name=name, **({} if path is None else {"path": str(path)}))


async def submit(substrate, plan, wallet, netuid, out):
    owner = wallet.coldkeypub.ss58_address
    if owner != plan["owner"]:
        raise Refused(
            "WALLET_IS_NOT_THE_SUBNET_OWNER", f"wallet {owner} != owner {plan['owner']}"
        )
    # the password prompt is the SDK's: `wallet.coldkey` decrypts the key file on access
    keypair = wallet.coldkey
    result = await substrate.submit(
        plan["call"], keypair, wait_for_inclusion=True, wait_for_finalization=True
    )
    error = getattr(result, "error", None)
    if error:
        print(f"SUBMISSION FAILED: {error}", file=out)
        return EXIT_SUBMIT_FAILED
    print(
        f"included           extrinsic {getattr(result, 'extrinsic_id', None)}",
        file=out,
    )
    print(f"                   block {getattr(result, 'block_hash', None)}", file=out)
    return None


async def run_switch(
    args, substrate, *, wallet_factory=open_wallet, ask=input, out=sys.stdout
):
    plan = await make_plan(substrate, args.netuid)
    _print_plan(plan, out)
    if plan["already_null"]:
        print("epoch consensus is already Null: nothing to submit", file=out)
        return EXIT_OK
    if not args.submit:
        print(
            "DRY RUN: nothing signed, nothing submitted (add --submit to sign)",
            file=out,
        )
        return EXIT_OK
    if not args.wallet_name:
        raise Refused("WALLET_NAME_REQUIRED_TO_SUBMIT", "pass --wallet-name")
    typed = ask(f"Type the netuid ({args.netuid}) to submit the Null switch: ").strip()
    if typed != str(args.netuid):
        raise Refused("NETUID_CONFIRMATION_DIFFERS", "nothing was signed")
    # the last look before signing: every rule again against the newest finalized head
    plan = await make_plan(substrate, args.netuid)
    if plan["already_null"]:
        print("epoch consensus became Null meanwhile: nothing to submit", file=out)
        return EXIT_OK
    failed = await submit(
        substrate,
        plan,
        wallet_factory(args.wallet_name, args.wallet_path),
        args.netuid,
        out,
    )
    if failed is not None:
        return failed
    head = await substrate.raw.get_chain_finalised_head()
    after = await read_state(substrate, args.netuid, head)
    print(f"READ-BACK epoch consensus = {after['epoch_consensus']}", file=out)
    holders = "; ".join(
        f"UID {h['uid']} {h['hotkey']}" for h in after["permit_holders"]
    )
    print(f"READ-BACK permit holders  = {holders}", file=out)
    return EXIT_OK if after["epoch_consensus"] == "Null" else EXIT_NOT_NULL


def _owner_only_json(path):
    path = Path(path)
    info = path.lstat()
    if path.is_symlink() or info.st_mode & 0o077:
        raise Refused("CONFIG_NOT_OWNER_ONLY", str(path))
    return json.loads(path.read_bytes())


async def run_check_weights(args, substrate, *, out=sys.stdout):
    """The weights operator config and the standing authorization name UID 0's hotkey, nothing else."""
    operator = _owner_only_json(args.operator)
    standing = _owner_only_json(args.standing)
    configured = {
        "operator.publisher.hotkey": (operator.get("publisher") or {}).get("hotkey"),
        "standing.publisher_hotkey": standing.get("publisher_hotkey"),
    }
    for where, hotkey in configured.items():
        print(f"{where:28} {hotkey}", file=out)
    wrong = {w: h for w, h in configured.items() if h != WEIGHTS_SIGNER_HOTKEY}
    if wrong:
        hint = (
            " (the receiver/copy hotkey, UID 12)"
            if RECEIVER_HOTKEY in wrong.values()
            else ""
        )
        raise Refused("WEIGHTS_SIGNER_IS_NOT_UID_0_HOTKEY", f"{wrong}{hint}")
    head = await substrate.raw.get_chain_finalised_head()
    uid0 = _value(
        await substrate.raw.query(
            "SubtensorModule", "Keys", [args.netuid, 0], block_hash=head
        )
    )
    if uid0 != WEIGHTS_SIGNER_HOTKEY:
        raise Refused("CONFIGURED_HOTKEY_IS_NOT_UID_0_ON_CHAIN", f"UID 0 is {uid0}")
    print(f"on chain: UID 0 = {uid0}: both files name it", file=out)
    return EXIT_OK


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help="the testnet RPC; the genesis is pinned anyway",
    )
    common.add_argument("--netuid", type=int, default=NETUID, help="refused unless 567")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    switch = sub.add_parser(
        "switch",
        parents=[common],
        help="dry run by default; --submit signs with the owner coldkey",
    )
    switch.add_argument(
        "--submit",
        action="store_true",
        help="sign and submit (asks you to type the netuid)",
    )
    switch.add_argument(
        "--wallet-name", help="the owner coldkey wallet; the SDK unlocks it itself"
    )
    switch.add_argument(
        "--wallet-path", type=Path, help="wallet root; default the SDK's own"
    )
    check = sub.add_parser(
        "check-weights",
        parents=[common],
        help="read-only: both files name UID 0's hotkey",
    )
    check.add_argument(
        "--operator",
        required=True,
        help="weights operator config (carbon.validator-weights-operator.v1)",
    )
    check.add_argument(
        "--standing", required=True, help="the standing authorization file"
    )
    return parser


async def _connect(endpoint):
    import bittensor as bt

    substrate = bt.RpcSubstrate(endpoint, fallback_endpoints=[], archive_endpoints=[])
    await substrate.connect()
    return substrate


async def main_async(
    argv=None,
    *,
    connect=_connect,
    wallet_factory=open_wallet,
    ask=input,
    out=sys.stdout,
):
    args = build_parser().parse_args(argv)
    substrate = await connect(args.endpoint)
    try:
        if args.command == "check-weights":
            return await run_check_weights(args, substrate, out=out)
        return await run_switch(
            args, substrate, wallet_factory=wallet_factory, ask=ask, out=out
        )
    except Refused as refusal:
        print(f"REFUSED {refusal.code}: {refusal.detail}", file=sys.stderr)
        return EXIT_REFUSED
    finally:
        await substrate.close()


def main(argv=None):
    return asyncio.run(main_async(argv))


if __name__ == "__main__":
    raise SystemExit(main())
