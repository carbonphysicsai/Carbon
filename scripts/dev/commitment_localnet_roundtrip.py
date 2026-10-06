"""Localnet round trip for a miner's strategy commitment (COMMITMENT-POSTER-01).

OPT-IN. It needs a running local subtensor that the executor started, with its
RPC on a loopback address. It never starts a chain, never touches a public
network and uses only public development URIs (``//Alice``, ``//Bob``), never a
wallet file. It refuses an endpoint whose genesis is testnet's or mainnet's.

What it proves and measures, for ``carbon_miner_signer/commitment_record.json``:

1. The SDK's composition of ``Commitments.set_commitment`` on the running
   runtime: the pallet index, the call index and the ``Raw71`` tag, read from
   the call bytes the SDK composes.
2. The signed-extension order (``payload_json["signedExtensions"]``), and that
   the signer's own reconstruction of the payload equals the SDK's: the
   signature the signer returns verifies over the SDK's prepared payload.
3. A real post through the real signer (in-thread, holding ``//Bob``) and the
   real Launchpad poster: broadcast once, finality, and the digest read back
   through ``ChainCommitmentReader`` as the exact 71-character string.
4. The fee: the SDK's estimate, the pallet's deposit, and the fee actually
   paid. D3's ceiling is 2 x (measured fee + deposit).
5. Replay: resubmitting the same signed extrinsic is rejected by the chain.
6. D4: a second commit in the same tempo is refused by the signer's ledger.

The signer asks on THIS terminal. The executor types the digest's last 8
characters, exactly as a miner would; nothing scripts the confirmation.

Usage (see .agent/tickets/COMMITMENT-POSTER-01_miner_commitment.md):

    CARBON_COMMITMENT_LOCALNET=1 .venv/bin/python \\
        scripts/dev/commitment_localnet_roundtrip.py \\
        --endpoint ws://127.0.0.1:9944 --setup --out .carbon-artifacts/commitment
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

TESTNET_GENESIS = "0x8f9cf856bf558a14440e75569c9e58594757048d7b3a84b5d25f6bd978263105"
FINNEY_GENESIS = "0x2f0555cc76fc2840a25a6ea3b9637146806f1f44b090c175ffde2a7e5ab36c03"
NETUID = 2  # the first subnet a fresh localnet creates (carbon/chain/localnet.py)


def _digest(label):
    return "sha256:" + hashlib.sha256(label.encode()).hexdigest()


async def _genesis(endpoint):
    import bittensor as bt

    substrate = bt.RpcSubstrate(
        endpoint, fallback_endpoints=[], archive_endpoints=[], retry_forever=False
    )
    try:
        await substrate.connect()
        return await substrate.block_hash(0)
    finally:
        await substrate.close()


async def _setup(endpoint, genesis):
    """Create netuid 2 with //Alice and register //Bob on it, as the
    disposable harness does (carbon/chain/localnet.py create_subnet,
    register_miners). Only on a fresh development chain."""
    import bittensor as bt
    from bittensor.keyfiles import Keypair
    from bittensor.settings import MEV_SHIELD_ERA_PERIOD

    from carbon.chain.localnet import root_setting
    from carbon.chain.models import hash256

    alice = Keypair.create_from_uri("//Alice")
    publisher = Keypair.create_from_uri("//Alice_hk")
    bob = Keypair.create_from_uri("//Bob")
    substrate = bt.RpcSubstrate(
        endpoint, fallback_endpoints=[], archive_endpoints=[], retry_forever=False
    )
    client = bt.Client(
        endpoint, substrate=substrate, policy=bt.Policy(allowed_netuids=[NETUID])
    )

    async def verify():
        if hash256(await substrate.block_hash(0)) != genesis:
            raise SystemExit("the endpoint's genesis changed during setup")

    async def run(label, intent, signer):
        print("setup:", label, flush=True)
        if intent.mev_shield_required:
            result = await client.submit_shielded(
                intent,
                signer,
                period=MEV_SHIELD_ERA_PERIOD,
                wait_for_inclusion=True,
                wait_for_finalization=True,
            )
        else:
            result = await client.execute(
                intent,
                signer,
                retries=0,
                wait_for_inclusion=True,
                wait_for_finalization=True,
            )
        if not result.success:
            raise SystemExit(f"setup step {label} failed: {result.message}")

    try:
        await substrate.connect()
        await verify()
        for action in ("start_delay", "admin_window", "owner_rate"):
            await run(action, root_setting(action, verify), alice)
        await run(
            "create-subnet",
            bt.RegisterSubnet(hotkey_ss58=publisher.ss58_address),
            alice,
        )
        owner = await substrate.query("SubtensorModule", "SubnetOwner", [NETUID])
        if owner != alice.ss58_address:
            raise SystemExit("netuid 2 is not the subnet this setup created")
        await run("registration", root_setting("registration", verify), alice)
        await run(
            "register-miner",
            bt.BurnedRegister(netuid=NETUID, hotkey_ss58=bob.ss58_address),
            bob,
        )
    finally:
        await client.close()


def _candidate_record(observed, genesis, measured_fee, deposit):
    from carbon_miner_signer import commitment as cm

    record = json.loads(cm.RECORD_PATH.read_text(encoding="utf-8"))
    record["call"]["call_index"] = observed["call_index"]
    record["call"]["data_tag"] = observed["data_tag"]
    record["extensions"] = observed["extensions"]
    record["zero_sized_extensions"] = [
        name for name in observed["extensions"] if name not in cm.STANDARD_EXTENSIONS
    ]
    record["fee"].update(
        measured_fee_rao=measured_fee,
        measured_deposit_rao=deposit,
        ceiling_rao=record["fee"]["multiplier"] * (measured_fee + deposit),
    )
    local = dict(record, network=dict(record["network"], name="localnet"))
    local["network"].update(genesis_hash=genesis, netuid=NETUID)
    return record, local


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--setup", action="store_true")
    parser.add_argument("--hotkey-uri", default="//Bob")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if os.environ.get("CARBON_COMMITMENT_LOCALNET") != "1":
        raise SystemExit("opt-in: set CARBON_COMMITMENT_LOCALNET=1 on a local chain")
    if not args.hotkey_uri.startswith("//"):
        raise SystemExit("only a public development URI is accepted")

    from bittensor.keyfiles import Keypair

    from carbon.chain.commitment_poster import (
        ERA_PERIOD,
        CommitmentPoster,
        SdkCommitmentChain,
    )
    from carbon.chain.external_signer import connect_signer, request_commitment
    from carbon.chain.models import ChainContext, hash256
    from carbon_miner_signer import SignerServer
    from carbon_miner_signer import commitment as cm

    genesis = hash256(asyncio.run(_genesis(args.endpoint)))
    if genesis in (TESTNET_GENESIS, FINNEY_GENESIS):
        raise SystemExit("refused: this endpoint is a public network")
    # ChainContext refuses a "localnet" endpoint that is not loopback.
    context = ChainContext("localnet", args.endpoint, "disposable", genesis, NETUID)
    if args.setup:
        asyncio.run(_setup(args.endpoint, genesis))
    hotkey = Keypair.create_from_uri(args.hotkey_uri)
    chain = SdkCommitmentChain(context)
    digest = _digest("carbon-commitment-localnet:" + genesis)

    # 1-2: what the SDK composes and prepares on this runtime.
    prepared = chain.prepare(hotkey.ss58_address, NETUID, digest, ERA_PERIOD)
    unsigned = prepared["unsigned"]
    call = bytes.fromhex(unsigned["call_data"][2:])
    expected_tail = NETUID.to_bytes(2, "little") + cm.compact(1)
    if call[2:5] != expected_tail or call[6:] != digest.encode("ascii"):
        raise SystemExit("the SDK composed an unexpected call: 0x" + call.hex())
    observed = {
        "pallet_index": call[0],
        "call_index": call[1],
        "data_tag": call[5],
        "extensions": list(unsigned["payload_json"].get("signedExtensions", [])),
        "call_hex": "0x" + call.hex(),
    }
    if observed["pallet_index"] != 18:
        raise SystemExit("the Commitments pallet index is not the SDK's 18")
    fee = chain.estimate(hotkey.ss58_address, NETUID, digest)
    if fee is None:
        raise SystemExit("the fee or deposit could not be read")
    record, local = _candidate_record(
        observed, genesis, fee["partial_fee_rao"], fee["deposit_rao"]
    )
    policy, missing = cm.load_policy(local)
    if policy is None:
        raise SystemExit("candidate record incomplete: " + ", ".join(missing))

    # 3: a real post through the real signer and the real poster.
    captured = {}
    with tempfile.TemporaryDirectory(prefix="cc-", dir="/tmp") as directory:
        log = io.StringIO()
        server = SignerServer(
            hotkey, Path(directory) / "s.sock", log=log, commit_policy=policy
        ).bind()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            signer = connect_signer(hotkey.ss58_address, socket_path=server.socket_path)

            def sign(request):
                answer = request_commitment(signer, request)
                captured["answer"] = answer
                return answer

            original_prepare = chain.prepare

            def prepare(*a):
                captured["prepared"] = original_prepare(*a)
                return captured["prepared"]

            chain.prepare = prepare
            poster = CommitmentPoster(
                hotkey=hotkey.ss58_address,
                chain=chain,
                sign=sign,
                state_dir=Path(directory) / "state",
                netuid=NETUID,
            )
            print("\nThe signer will ask on this terminal. Check it, then type.")
            outcome = poster.post(digest)
            if outcome["code"] != "commitment_committed":
                raise SystemExit("round trip failed: " + json.dumps(outcome))
            read_back = chain.read(hotkey.ss58_address)
            # 5: the same signed extrinsic again.
            replay = chain.broadcast(
                captured["prepared"], captured["answer"]["signature"]
            )
            # 6: a different digest in the same tempo is refused by the ledger.
            second = poster.post(
                _digest("carbon-commitment-localnet-second:" + genesis)
            )
        finally:
            server.close()
            thread.join(timeout=5)
    paid = outcome.get("fee_rao")
    measured = paid if type(paid) is int else fee["partial_fee_rao"]
    record, _ = _candidate_record(observed, genesis, measured, fee["deposit_rao"])
    record["fee"]["status"] = "MEASURED_PENDING_OWNER_RECORD"
    record["fee"]["measurement"] = {
        "network": "localnet",
        "genesis_hash": genesis,
        "estimated_partial_fee_rao": fee["partial_fee_rao"],
        "paid_fee_rao": paid,
        "deposit_rao": fee["deposit_rao"],
        "block": outcome.get("block"),
    }
    evidence = {
        "schema": "carbon.commitment-localnet-roundtrip.v1",
        "observed": observed,
        "outcome": outcome,
        "read_back": read_back,
        "read_back_is_digest": read_back is not None and read_back["digest"] == digest,
        "replay_outcome": replay.get("outcome"),
        "replay_rejected": replay.get("outcome") != "FINALIZED",
        "second_in_tempo": second.get("code"),
        "second_refused_by_ledger": "ALREADY_COMMITTED_THIS_TEMPO"
        in str(second.get("code")),
        "record": record,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "commitment-roundtrip.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    ok = (
        evidence["read_back_is_digest"]
        and evidence["replay_rejected"]
        and evidence["second_refused_by_ledger"]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
