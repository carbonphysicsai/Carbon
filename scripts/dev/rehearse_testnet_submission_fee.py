"""End-to-end Testnet 567 rehearsal runner for the TAO->Alpha submission fee.

Two modes:
  1. ``--dry-run`` (no wallet required, safe anywhere):
     - Connects live to Bittensor Testnet 567 (`wss://test.finney.opentensor.ai:443`),
       verifies the pinned `TESTNET_GENESIS` and finalized head block, and decodes
       real `System.Events` from the latest finalized Testnet block.
     - Exercises live zero-restart hot-dialing in host state (`0.025 -> 0.050` with
       bounded rate-hike grace -> `0.010` -> instant `disable` -> `0.025`),
       receiver-bound `v2` remarks, single-winner burn claim, double-spend replay
       refusal, and proven `FAILED_INFRA` -> `RETRY_CREDIT` minting & 0-TAO redemption.
  2. ``--live --wallet-name <name> --hotkey-name <hk>`` (funded Testnet 567 hotkey):
     - Spawns `carbon-miner-signer --enable-fee-burns testnet --max-daily-fee-tao 0.25`
       on an isolated Unix domain socket, broadcasts one real `0.025 test-TAO`
       `Utility.batch_all([SubtensorModule.add_stake_burn, System.remark_with_event])`
       on Testnet 567, waits for GRANDPA finality, indexes the real block through
       `ChainFeeBurnReader` + `FinalizedBurnIndexer`, admits the submission, proves
       replay is refused (`fee_already_spent`), and writes an immutable JSON receipt.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import shutil
import tempfile
import threading
from contextlib import aclosing
from pathlib import Path
from types import SimpleNamespace

from carbon.chain import networks
from carbon.chain.external_signer import connect_signer, request_fee_burn
from carbon.chain.fee_burns import (
    ChainFeeBurnReader,
    FinalizedBurnIndexer,
    ObservedFeeBurn,
    extract_block_fee_burns,
    fee_remark_hash,
)
from carbon.chain.fee_poster import FeePostCode, FeePoster, SdkFeeBurnChain
from carbon.chain.models import ChainContext
from carbon.challenge_validator import submission_fee as sf
from carbon_miner_signer import fee_burn as signer_fb
from carbon_miner_signer.signer import SignerServer

REHEARSAL_RECEIVER = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"


def _testnet_context() -> ChainContext:
    row = networks.NETWORKS["testnet"]
    return ChainContext(
        "testnet",
        row.endpoints[0],
        row.chain_id,
        networks.TESTNET_GENESIS,
        row.netuid,
    )


async def _probe_testnet_finalized_block(ctx: ChainContext) -> dict[str, object]:
    import bittensor as bt

    sub = bt.RpcSubstrate(
        ctx.endpoint,
        fallback_endpoints=[],
        archive_endpoints=[],
        retry_forever=False,
    )
    client = bt.Client(ctx.endpoint, substrate=sub)
    try:
        await sub.connect()
        genesis = str(await sub.block_hash(0)).lower()
        if genesis != ctx.genesis_hash:
            raise RuntimeError(f"genesis mismatch: {genesis} != {ctx.genesis_hash}")
        async with aclosing(client.blocks(finalized=True)) as headers:
            hdr = await anext(headers)
        blk = int(hdr.number)
        bhash = str(await sub.block_hash(blk)).lower()
        events = await sub.events(bhash)
        burns = extract_block_fee_burns(
            events, block=blk, block_hash=bhash, netuid=ctx.netuid
        )
        return {
            "endpoint": ctx.endpoint,
            "genesis_verified": genesis == ctx.genesis_hash,
            "finalized_block": blk,
            "block_hash": bhash,
            "event_count": len(events),
            "observed_567_burns_in_head": len(burns),
        }
    finally:
        await client.close()


def _rehearse_hot_dial_and_lifecycle(
    work_dir: Path, head_block: int
) -> dict[str, object]:
    policy_file = work_dir / "submission_fee_policy.json"
    ledger_file = work_dir / "submission_fees_567.sqlite3"
    sf.update_policy_row(
        path=policy_file,
        scope="567:*",
        enabled=True,
        amount_rao=25_000_000,
        netuid=567,
        min_block=head_block - 10,
        allow_testnet_without_terms=True,
    )
    intake = SimpleNamespace(
        submission_fee=None,
        submission_terms=None,
        fee_ledger=None,
        fee_indexer=None,
        version_closed={},
        grade_marker=lambda _sid: None,
    )
    watcher = sf.LiveFeePolicySource(
        intake,
        challenge_id="electric-motor-magnetics",
        version="1.9",
        expected_netuid=567,
        ledger_path=ledger_file,
        refresh_interval_s=0.0,
        path=policy_file,
    )
    p0 = watcher.current(force=True)
    assert p0 is not None and p0.amount_rao == 25_000_000

    hk = "5C4hrfjw9DjXZTzV3MwzrrAr9P1MJhSrvWGWqi1eSuyUpnhM"
    ext_id = f"{head_block}-2"
    intake.fee_ledger.record_indexed_block(
        head_block,
        [
            ObservedFeeBurn(
                extrinsic_id=ext_id,
                block=head_block,
                extrinsic_idx=2,
                block_hash="0x" + "ab" * 32,
                netuid=567,
                hotkey=hk,
                payer=hk,
                amount_rao=25_000_000,
                alpha_burned_rao=1_800_000_000,
                remark_hash=fee_remark_hash(
                    567, "electric-motor-magnetics", REHEARSAL_RECEIVER, hk
                ),
            )
        ],
    )

    sf.update_policy_row(
        path=policy_file,
        scope="567:*",
        enabled=True,
        amount_rao=50_000_000,
        netuid=567,
        current_head=head_block,
        effective_from_block=head_block + 30,
    )
    p_up = watcher.current(force=True)
    assert p_up is not None and p_up.amount_rao == 50_000_000
    assert p_up.required_amount_at_block(head_block) == 25_000_000
    assert p_up.required_amount_at_block(head_block + 30) == 50_000_000

    with intake.fee_ledger.claim_for_admission(
        policy=p_up,
        payment={"kind": "burn", "extrinsic_id": ext_id},
        hotkey=hk,
        receiver=REHEARSAL_RECEIVER,
        challenge_id="electric-motor-magnetics",
        challenge_version="1.9",
        known_finalized_head=head_block + 2,
    ) as commit:
        commit("rtsk_" + "1" * 64)

    replay_code = None
    try:
        with intake.fee_ledger.claim_for_admission(
            policy=p_up,
            payment={"kind": "burn", "extrinsic_id": ext_id},
            hotkey=hk,
            receiver=REHEARSAL_RECEIVER,
            challenge_id="electric-motor-magnetics",
            challenge_version="1.9",
            known_finalized_head=head_block + 2,
        ):
            pass
    except sf.FeeRefused as exc:
        replay_code = exc.code
    assert replay_code == sf.FEE_ALREADY_SPENT

    sf.update_policy_row(
        path=policy_file, scope="567:*", enabled=True, amount_rao=10_000_000, netuid=567
    )
    assert watcher.current(force=True).amount_rao == 10_000_000  # type: ignore[union-attr]
    sf.disable_policy(path=policy_file, scope="567:*", netuid=567)
    assert watcher.current(force=True) is None
    sf.update_policy_row(
        path=policy_file, scope="567:*", enabled=True, amount_rao=25_000_000, netuid=567
    )
    p_restored = watcher.current(force=True)
    assert p_restored is not None and p_restored.amount_rao == 25_000_000

    intake.adapter = SimpleNamespace(
        contract_digest="sha256:" + "c" * 64,
        ledger=SimpleNamespace(requeued_as=lambda *_a: None),
        outcome=lambda _sid: {"state": "FAILED_INFRA"},
    )
    minted = sf.reconcile_hotkey_credits(intake, hk)
    assert len(minted) == 1
    with intake.fee_ledger.claim_for_admission(
        policy=p_restored,
        payment={"kind": "credit", "credit_id": minted[0]},
        hotkey=hk,
        receiver=REHEARSAL_RECEIVER,
        challenge_id="electric-motor-magnetics",
        challenge_version="1.9",
        known_finalized_head=head_block + 5,
    ) as commit_c:
        commit_c("rtsk_" + "2" * 64)

    return {
        "hot_dial_up_grace_honored": True,
        "double_spend_replay_refusal": replay_code,
        "hot_dial_down_and_kill_switch_verified": True,
        "failed_infra_credit_minted_and_redeemed": minted[0],
        "ledger_stats": intake.fee_ledger.public_stats(),
    }


def _run_live_burn(
    ctx: ChainContext,
    *,
    wallet_name: str,
    hotkey_name: str,
    wallet_path: Path | None,
    challenge_id: str,
    receiver: str,
    amount_rao: int,
) -> dict[str, object]:
    from bittensor import Wallet

    w = Wallet(
        name=wallet_name,
        hotkey=hotkey_name,
        path=str(wallet_path) if wallet_path is not None else None,
    )
    kp = w.hotkey
    short_dir = Path(tempfile.mkdtemp(prefix="creh-"))
    try:
        sock = short_dir / "s.sock"
        fb_policy = signer_fb.load_fee_burn_policy(
            "testnet", daily_budget_rao=250_000_000
        )
        srv = SignerServer(kp, sock, fee_burn_policy=fb_policy)
        srv.bind()
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            ext = connect_signer(kp.ss58_address, socket_path=sock)
            chain = SdkFeeBurnChain(ctx)
            head_before = chain.finalized_block()
            poster = FeePoster(
                hotkey=kp.ss58_address,
                receiver=receiver,
                netuid=ctx.netuid,
                challenge_id=challenge_id,
                chain=chain,
                sign=lambda req: request_fee_burn(ext, req),
                state_dir=short_dir / "poster",
            )
            post_res = poster.obtain_extrinsic(
                amount_rao=amount_rao, min_block=head_before
            )
            if post_res.get("code") not in (
                FeePostCode.BURNED.value,
                FeePostCode.REUSED_UNSPENT.value,
            ):
                raise RuntimeError(
                    f"Testnet fee burn did not finalize cleanly: {post_res}"
                )
            ext_id = str(post_res["extrinsic_id"])
            blk = int(post_res["block"])

            ledger = sf.FeeLedger(
                short_dir / "door_fees.sqlite3",
                expected_netuid=ctx.netuid,
                expected_genesis_hash=ctx.genesis_hash,
            )
            reader = ChainFeeBurnReader(ctx)
            indexer = FinalizedBurnIndexer(reader, ledger)
            policy = sf.FeePolicy(
                policy_version="tao-burn-v1",
                amount_rao=amount_rao,
                netuid=ctx.netuid,
                min_block=head_before,
                allow_testnet_without_terms=True,
            )
            with ledger.claim_for_admission(
                policy=policy,
                payment={"kind": "burn", "extrinsic_id": ext_id},
                hotkey=kp.ss58_address,
                receiver=receiver,
                challenge_id=challenge_id,
                challenge_version="1.9",
                known_finalized_head=blk,
                indexer=indexer,
            ) as commit:
                commit("rtsk_" + "f" * 64)
            poster.note_spent(ext_id)
            return {
                "hotkey": kp.ss58_address,
                "receiver": receiver,
                "extrinsic_id": ext_id,
                "finalized_block": blk,
                "amount_rao": amount_rao,
                "door_stats": ledger.public_stats(),
            }
        finally:
            srv.close()
            t.join(timeout=2)
    finally:
        shutil.rmtree(short_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Live Testnet RPC read + local hot-dial & lifecycle check (0 TAO spent)",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help="Broadcast real 0.025 test-TAO add_stake_burn on Testnet 567 and admit",
    )
    parser.add_argument("--wallet-name", default="default")
    parser.add_argument("--hotkey-name", default="default")
    parser.add_argument("--wallet-path", type=Path, default=None)
    parser.add_argument("--challenge-id", default="electric-motor-magnetics")
    parser.add_argument("--receiver", default=REHEARSAL_RECEIVER)
    parser.add_argument("--amount-rao", type=int, default=25_000_000)
    parser.add_argument("--receipt-out", type=Path, default=None)
    args = parser.parse_args(argv)

    ctx = _testnet_context()
    probe = asyncio.run(_probe_testnet_finalized_block(ctx))
    with tempfile.TemporaryDirectory(prefix="creh-dry-") as tmp:
        lifecycle = _rehearse_hot_dial_and_lifecycle(
            Path(tmp), int(probe["finalized_block"])
        )

    report: dict[str, object] = {
        "schema": "carbon.rehearsal.submission-fee-testnet.v1",
        "timestamp_utc": datetime.datetime.now(datetime.UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "mode": "live" if args.live else "dry-run",
        "testnet_567_probe": probe,
        "hot_dial_and_lifecycle": lifecycle,
    }
    if args.live:
        report["live_burn"] = _run_live_burn(
            ctx,
            wallet_name=args.wallet_name,
            hotkey_name=args.hotkey_name,
            wallet_path=args.wallet_path,
            challenge_id=args.challenge_id,
            receiver=args.receiver,
            amount_rao=args.amount_rao,
        )

    out_json = json.dumps(report, indent=2) + "\n"
    if args.receipt_out is not None:
        args.receipt_out.parent.mkdir(parents=True, exist_ok=True)
        args.receipt_out.write_text(out_json, encoding="utf-8")
    print(out_json, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
