#!/usr/bin/env python3
"""Switch finney netuid 116 to Null consensus: the owner's one extrinsic, dry by default, with a watcher.

The finney copy of scripts/dev/null_consensus_switch.py (testnet 567, unchanged). The owner signs
`AdminUtils.sudo_set_epoch_consensus(netuid=116, mode=Null)` with the 116 subnet-owner coldkey. The
call is composed through the pinned bittensor SDK from the LIVE metadata and signed through the SDK's
own wallet.

    python scripts/dev/null_consensus_switch_116.py switch                          # dry run, one look
    python scripts/dev/null_consensus_switch_116.py switch --watch-minutes 120      # dry watch: report the first empty moment
    python scripts/dev/null_consensus_switch_116.py switch --submit --wallet-name NAME --watch-minutes 120
    python scripts/dev/null_consensus_switch_116.py check-weights --operator FILE --standing FILE

`switch` refuses, with a closed code and nothing signed, unless ALL of these hold:
- the chain's genesis is the pinned finney genesis and the netuid is 116;
- the live runtime is at least spec 482 (the first release with the Null-epoch scheduler fix);
- the call composed from the live metadata is byte-for-byte 0x136f740001;
- `TimelockedWeightCommits` has no entry for any of the 16 mechanism indices of 116 (the chain
  itself refuses the switch with `InvalidValue` while one is pending);
- (`--submit` only) the wallet's coldkey is the live `SubnetOwner[116]` and the owner typed the
  netuid back.

THE WATCHER (`--watch-minutes M`, 1..240). On 116 other validators commit timelocked weights every
tempo, so a moment with no pending commit is short and not ours to schedule. With a watch the
pending check is not a refusal: the tool re-reads every `--poll-seconds` (default 6) and acts at the
first moment when BOTH the finalized head and the best head show no pending commit in any of the 16
indices, with every other rule re-checked at that moment. Dry, it prints that moment and exits 0.
With `--submit`, the owner types the netuid and the SDK prompts for the coldkey password ONCE,
before the wait (so the key stays decrypted in this process's memory until it exits: attended use
only); it then submits at the first empty moment. A commit that lands between the read and the
inclusion makes the chain answer `InvalidValue`; the watcher then keeps watching, at most
`--max-attempts` submissions in all (default 3, each costs one transaction fee). No empty moment
before the deadline exits 5 with nothing submitted.

Already Null is reported and is not an error. After inclusion it reads back 116's epoch consensus
and the validator-permit holders and prints both; anything but `Null` exits 4.

The wallet password is never an argument, never read, logged or stored here: the SDK decrypts the
coldkey itself and prompts for it (`bt.Wallet(...).coldkey`). Nothing is signed without `--submit`.

`check-weights` is read-only. Under Null only the largest-stake UID holds a validator permit, so the
weights signer must be UID 0's hotkey; it parses the weights operator config and the standing
authorization (owner-only JSON) and checks that both name that hotkey on chain.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

FINNEY_GENESIS = "0x2f0555cc76fc2840a25a6ea3b9637146806f1f44b090c175ffde2a7e5ab36c03"
DEFAULT_ENDPOINT = "wss://entrypoint-finney.opentensor.ai:443"
NETUID = 116
#: pallet 0x13, call_index 111 (0x6f), netuid 116 as u16 little-endian, EpochConsensus::Null (index 1).
#: Read from live finney metadata at spec 488 on 9 Nov 2026 (dry compose, nothing signed).
EXPECTED_CALL_HEX = "0x136f740001"
#: Spec of the first subtensor release (v482) that carries commit c7aa77e, "Run a due Null epoch first".
MINIMUM_SPEC_VERSION = 482
#: The chain probes the mechanism indices for a pending timelocked commit before it switches.
MECHANISM_SLOTS = 16
SUBNET_SLOTS = 4096
#: UID 0's hotkey on 116 (live `SubnetOwnerHotkey`, owner coldkey 5D5Rwy...): the only weights signer under Null.
WEIGHTS_SIGNER_HOTKEY = "5DDLUnX2yicKLC1T5PN7bkwgU51buJt93XQFV1giqhDsGUTk"
MAX_WATCH_MINUTES = 240

EXIT_OK, EXIT_REFUSED, EXIT_SUBMIT_FAILED, EXIT_NOT_NULL, EXIT_WATCH_TIMEOUT = (
    0,
    2,
    3,
    4,
    5,
)


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
    """Storage indices of 116's mechanisms that hold at least one timelocked commit."""
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
    """116's epoch consensus and the validator-permit holders, read at `block_hash`."""
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


async def make_plan(substrate, netuid, *, allow_pending=False):
    """Every refusal rule, in order, with nothing signed. Returns what a submission would carry.
    With `allow_pending` (the watcher) a pending commit is reported in `pending`, not refused; the
    best head is read too, and `pending` holds what either head shows."""
    if netuid != NETUID:
        raise Refused("NETUID_NOT_116", f"this script switches netuid {NETUID} only")
    genesis = await substrate.block_hash(0)
    if str(genesis).lower() != FINNEY_GENESIS:
        raise Refused("NOT_THE_PINNED_FINNEY_GENESIS", str(genesis))
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
        if allow_pending:
            best = await substrate.raw.get_chain_head()
            pending = sorted(
                set(pending)
                | set(await pending_commit_indices(substrate, netuid, best))
            )
        elif pending:
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
        "pending": pending,
        "already_null": state["epoch_consensus"] == "Null",
    }


def _print_plan(plan, out):
    print(f"genesis            {plan['genesis']} (pinned finney)", file=out)
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
    if plan["pending"]:
        print(f"pending commits    at storage indices {plan['pending']}", file=out)
    else:
        print("pending commits    none (checked 16 mechanism indices)", file=out)


def open_wallet(name, path):
    """The SDK wallet; its coldkey is decrypted (and the password prompted) only when asked for."""
    import bittensor as bt

    return bt.Wallet(name=name, **({} if path is None else {"path": str(path)}))


def _stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


async def wait_for_empty(substrate, netuid, args, out, *, sleep, clock):
    """The first plan with no pending commit at either head (or already Null), else None at the deadline."""
    deadline = clock() + 60 * args.watch_minutes
    seen = None
    while True:
        plan = await make_plan(substrate, netuid, allow_pending=True)
        if plan["already_null"] or not plan["pending"]:
            print(
                f"{_stamp()} EMPTY MOMENT: no pending commit at either head", file=out
            )
            return plan
        if plan["pending"] != seen:
            seen = plan["pending"]
            print(f"{_stamp()} waiting: pending at storage indices {seen}", file=out)
        if clock() >= deadline:
            return None
        await sleep(args.poll_seconds)


async def submit_once(substrate, plan, keypair, out):
    """None when included without an error, else the chain's error text."""
    result = await substrate.submit(
        plan["call"], keypair, wait_for_inclusion=True, wait_for_finalization=True
    )
    error = getattr(result, "error", None)
    if error:
        return str(error)
    print(
        f"included           extrinsic {getattr(result, 'extrinsic_id', None)}",
        file=out,
    )
    print(f"                   block {getattr(result, 'block_hash', None)}", file=out)
    return None


async def read_back(substrate, netuid, out):
    head = await substrate.raw.get_chain_finalised_head()
    after = await read_state(substrate, netuid, head)
    print(f"READ-BACK epoch consensus = {after['epoch_consensus']}", file=out)
    holders = "; ".join(
        f"UID {h['uid']} {h['hotkey']}" for h in after["permit_holders"]
    )
    print(f"READ-BACK permit holders  = {holders}", file=out)
    return EXIT_OK if after["epoch_consensus"] == "Null" else EXIT_NOT_NULL


async def run_switch(
    args,
    substrate,
    *,
    wallet_factory=open_wallet,
    ask=input,
    out=sys.stdout,
    sleep=asyncio.sleep,
    clock=time.monotonic,
):
    watching = args.watch_minutes > 0
    if not 0 <= args.watch_minutes <= MAX_WATCH_MINUTES:
        raise Refused("WATCH_MINUTES_OUT_OF_RANGE", f"0..{MAX_WATCH_MINUTES}")
    if not 1 <= args.max_attempts <= 5 or not 2 <= args.poll_seconds <= 60:
        raise Refused("WATCH_LIMITS_OUT_OF_RANGE", "max-attempts 1..5, poll 2..60 s")
    plan = await make_plan(substrate, args.netuid, allow_pending=watching)
    _print_plan(plan, out)
    if plan["already_null"]:
        print("epoch consensus is already Null: nothing to submit", file=out)
        return EXIT_OK
    if not args.submit:
        if watching:
            found = await wait_for_empty(
                substrate, args.netuid, args, out, sleep=sleep, clock=clock
            )
            if found is None:
                print("WATCH ENDED: no empty moment before the deadline", file=out)
                return EXIT_WATCH_TIMEOUT
            print("DRY WATCH: a submission would go now; nothing signed", file=out)
            return EXIT_OK
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
    wallet = wallet_factory(args.wallet_name, args.wallet_path)
    owner = wallet.coldkeypub.ss58_address
    if owner != plan["owner"]:
        raise Refused(
            "WALLET_IS_NOT_THE_SUBNET_OWNER", f"wallet {owner} != owner {plan['owner']}"
        )
    # the password prompt is the SDK's: `wallet.coldkey` decrypts the key file on access, once
    keypair = wallet.coldkey
    attempts = 0
    while True:
        if watching:
            plan = await wait_for_empty(
                substrate, args.netuid, args, out, sleep=sleep, clock=clock
            )
            if plan is None:
                print("WATCH ENDED: no empty moment before the deadline", file=out)
                return EXIT_WATCH_TIMEOUT
        else:
            # the last look before signing: every rule again against the newest finalized head
            plan = await make_plan(substrate, args.netuid)
        if plan["already_null"]:
            print("epoch consensus became Null meanwhile: nothing to submit", file=out)
            return EXIT_OK
        if plan["owner"] != owner:
            raise Refused("SUBNET_OWNER_CHANGED", f"{plan['owner']} != {owner}")
        attempts += 1
        error = await submit_once(substrate, plan, keypair, out)
        if error is None:
            return await read_back(substrate, args.netuid, out)
        print(f"{_stamp()} SUBMISSION {attempts} FAILED: {error}", file=out)
        if not watching or "InvalidValue" not in error or attempts >= args.max_attempts:
            return EXIT_SUBMIT_FAILED


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
        raise Refused("WEIGHTS_SIGNER_IS_NOT_UID_0_HOTKEY", f"{wrong}")
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
        help="a finney RPC (public entrypoint or the own node); the genesis is pinned anyway",
    )
    common.add_argument("--netuid", type=int, default=NETUID, help="refused unless 116")
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
    switch.add_argument(
        "--watch-minutes",
        type=int,
        default=0,
        help=f"wait up to this long (1..{MAX_WATCH_MINUTES}) for a moment with no pending commit",
    )
    switch.add_argument(
        "--poll-seconds", type=int, default=6, help="watch re-read interval (2..60)"
    )
    switch.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="watch: at most this many submissions (1..5)",
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
    sleep=asyncio.sleep,
    clock=time.monotonic,
):
    args = build_parser().parse_args(argv)
    substrate = await connect(args.endpoint)
    try:
        if args.command == "check-weights":
            return await run_check_weights(args, substrate, out=out)
        return await run_switch(
            args,
            substrate,
            wallet_factory=wallet_factory,
            ask=ask,
            out=out,
            sleep=sleep,
            clock=clock,
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
