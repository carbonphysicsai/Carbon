"""Actual isolated v445 chain integration; never silently substitutes a fake."""

import asyncio
import os
import subprocess
from dataclasses import asdict, replace
from pathlib import Path

import pytest


@pytest.mark.skipif(
    os.environ.get("CARBON_REQUIRE_LOCALNET") != "1",
    reason="explicit disposable runtime lane",
)
def test_pinned_localnet_submission_reward_publication_and_recovery(tmp_path):
    from net5_fixture_support import Exam

    from carbon.chain import ChainFailure, ReadOnlyChainAdapter
    from carbon.chain.auth import BittensorHotkeyVerifier, BittensorMessageSigner
    from carbon.chain.localnet import LocalnetSession, miner_burned_q32, write_evidence
    from carbon.chain.publication import PublicationFailure
    from carbon.chain.publisher import LocalnetPublisher
    from carbon.chain.sdk import BittensorReader
    from carbon.chain.sdk_weights import BittensorPublicationBackend
    from carbon.rewards.core import Q12, DevelopmentTerms, WinnerStatus
    from carbon.rewards.intents import LocalnetIntentIssuer
    from carbon.rewards.ledger import FixtureRewardLedger
    from carbon.transport.store import ReceiptJournal

    mode = os.environ.get("CARBON_LOCALNET_MODE", "full")
    assert mode in ("full", "operator")
    private = os.environ.get("CARBON_LOCALNET_STATE")
    if private:
        tmp_path = Path(private).absolute()
        assert (
            not tmp_path.exists()
        ), "Never overwrite or blindly replay an existing localnet session"
        tmp_path.mkdir(parents=True, mode=0o700)
    directory = Path(os.environ["CARBON_LOCALNET_EVIDENCE"])
    report = {
        "schema": "carbon.net5.runtime.evidence.v1",
        "maturity": "SYNTHETIC_ONLY",
        "execution_scope": (
            "NET6_ALL_BURN_OPERATIONS" if mode == "operator" else "NET5_FULL"
        ),
        "runtime_profile": os.environ.get("CARBON_LOCALNET_PROFILE", "fast"),
        "g2": "NOT_READY",
        "treasury": None,
        "stages": [],
        "epochs": [],
        "dispatches": [],
    }

    def record(stage):
        report["stages"].append(stage)
        write_evidence(directory / "integration.json", report)
        print("NET-5: " + stage, flush=True)

    async def exercise():
        import bittensor as bt

        session = LocalnetSession(os.environ["CARBON_LOCALNET_CONTAINER"], directory)
        backend = None
        try:
            await session.start()
            block_time = float(session.profile["nominal_block_seconds"])
            record("isolated-genesis-verified-before-keys")
            await session.configure()
            record("disposable-subnet-and-publisher-configured")
            context, roles = session.context, session.roles
            backend = BittensorPublicationBackend(
                context, roles["publisher"].ss58_address, roles["publisher"]
            )
            await backend.start()
            reader = ReadOnlyChainAdapter(context, BittensorReader())
            # Endpoint/genesis disagreement is rejected before any publisher dispatch.
            bad = ReadOnlyChainAdapter(
                replace(context, genesis_hash="0x" + "f" * 64), BittensorReader()
            )
            with pytest.raises(ChainFailure):
                await bad.observe(minimum_finalized_block=0)
            record("genesis-mismatch-rejected")
            receipts = ReceiptJournal(tmp_path / "receipts.sqlite", context)
            exams = [
                Exam(
                    tmp_path / (suffix or "a"),
                    receipts,
                    reader,
                    roles["publisher"].ss58_address,
                    BittensorHotkeyVerifier(),
                    suffix,
                )
                for suffix in (None, "b", "c")
            ]
            ledger = FixtureRewardLedger(
                receipts, reader, tuple(e.journal for e in exams)
            )

            def signer(role):
                bound = BittensorMessageSigner(roles[role])
                return lambda body, now, _: bound.sign(
                    body, receiver=roles["publisher"].ss58_address, nonce_ns=now
                )

            baselines = []
            for exam in exams:
                for variant in range(20):
                    ref = await exam.commit(variant, signer("publisher"))
                    accepted = exam.evaluate(ref)
                    if accepted is not None:
                        baselines.append((ref, accepted))
                        break
                else:
                    pytest.fail(
                        "No admissible synthetic baseline within the fixed 20-attempt budget"
                    )
            observed = await reader.observe(minimum_finalized_block=0)
            opens = observed.timestamp_ms + 30000
            for exam, (ref, accepted) in zip(exams, baselines):
                terms = DevelopmentTerms(
                    exam.journal.context.identity,
                    ref.identity,
                    accepted.score_hex,
                    "1",
                    opens,
                    opens + 3600000,
                    opens + 3600000,
                    ((opens, Q12 // 3),),
                )
                await ledger.register(
                    terms, exam.pack, exam.profile.challenge_key.challenge_id
                )
            from carbon.chain.localnet import inspect_isolation
            from carbon.chain.operations import config_document
            from carbon.chain.operator_store import exclusive_json

            proof = inspect_isolation(session.container)
            os.chmod(receipts.path, 0o600)
            exclusive_json(
                tmp_path / "operator.json",
                config_document(
                    receipts,
                    session.container,
                    roles["publisher"].ss58_address,
                    tuple(e.journal.context for e in exams),
                    proof["endpoints"],
                    proof["container"],
                ),
            )
            record("three-pinned-fixture-baselines-and-public-coefficients-registered")
            for _ in range(45):
                if (
                    await reader.observe(minimum_finalized_block=0)
                ).timestamp_ms >= opens:
                    break
                await asyncio.sleep(1)
            else:
                pytest.fail("Finalized opening time did not advance")
            issuer = LocalnetIntentIssuer(ledger)
            publisher = LocalnetPublisher(issuer, backend)

            async def publish(label):
                ref = await issuer.issue(label)
                row = await publisher.publish(ref)
                for _ in range(4 * 12 + 1):
                    if row["state"] in (
                        "ROW_VERIFIED",
                        "CHAIN_REJECTED",
                        "FAILED_BEFORE_SIGNING",
                        "EXPOSURE_CHANGED",
                    ):
                        break
                    await asyncio.sleep(max(0.25, block_time / 4))
                    row = await publisher.reconcile(ref.digest)
                report["dispatches"].append(row)
                write_evidence(directory / "integration.json", report)
                assert row["state"] == "ROW_VERIFIED", row["tracking"]
                assert row["tracking"]["tx_hash"] and row["tracking"]["finalized_block"]
                assert await publisher.publish(ref) == row  # No second transaction.
                return ref, row

            async def epoch(label):
                start = await session.sub.query(
                    "SubtensorModule", "SubnetEpochIndex", [2]
                )
                # Two 20-block epochs plus a 12-block finality/read slack. Poll at
                # quarter-block cadence, with a finite four-polls-per-block ceiling.
                for _ in range(4 * (2 * 20 + 12) + 1):
                    snap, caps = await backend.observe()
                    block_hash = snap.block_hash
                    value = await session.sub.query(
                        "SubtensorModule",
                        "SubnetEpochIndex",
                        [2],
                        block_hash=block_hash,
                    )
                    if value >= start + 2:
                        break
                    await asyncio.sleep(max(0.25, block_time / 4))
                else:
                    pytest.fail("No complete finalized epochs observed")
                fields = (
                    "MinerBurned",
                    "SubnetAlphaIn",
                    "SubnetAlphaOut",
                    "SubnetAlphaInEmission",
                    "SubnetAlphaOutEmission",
                    "Incentive",
                    "Dividends",
                    "Emission",
                    "PendingServerEmission",
                    "PendingValidatorEmission",
                    "PendingOwnerCut",
                )
                values = await asyncio.gather(
                    *(
                        session.sub.query(
                            "SubtensorModule", field, [2], block_hash=block_hash
                        )
                        for field in fields
                    )
                )
                sample = {
                    "label": label,
                    "block": snap.finalized_block,
                    "hash": block_hash,
                    "epoch": value,
                    "capabilities": asdict(caps),
                    "observations": dict(zip(fields, values)),
                }
                report["epochs"].append(sample)
                write_evidence(directory / "integration.json", report)
                assert caps.burn_mode == "Burn"
                sample["miner_burned_q32"] = miner_burned_q32(values[0])
                assert (
                    sample["miner_burned_q32"] > 0
                ), "No miner burn observed in finalized epoch"
                write_evidence(directory / "integration.json", report)
                return sample

            async def recover(ref, paid, label):
                nonlocal ledger, issuer, publisher
                # Restart every application journal/projection owner, keeping actual chain state.
                restarted_receipts = ReceiptJournal(receipts.path, context)
                from carbon.candidates.store import CandidateJournal

                journals = tuple(
                    CandidateJournal(
                        restarted_receipts, e.journal.context, e.journal.limits
                    )
                    for e in exams
                )
                ledger = FixtureRewardLedger(restarted_receipts, reader, journals)
                issuer = LocalnetIntentIssuer(ledger)
                publisher = LocalnetPublisher(issuer, backend)
                assert await publisher.publish(ref) == paid
                record("restart-and-exact-dispatch-replay-no-resend")

                # Actual provider outage: pause only this harness-owned pinned container.
                await asyncio.to_thread(
                    subprocess.run,
                    ["docker", "pause", session.container],
                    check=True,
                    capture_output=True,
                    timeout=15,
                )
                try:
                    with pytest.raises((TimeoutError, PublicationFailure)):
                        await asyncio.wait_for(backend.observe(), 2)
                    assert publisher.exposure()["stored_weights_may_remain_effective"]
                finally:
                    await asyncio.to_thread(
                        subprocess.run,
                        ["docker", "unpause", session.container],
                        check=True,
                        capture_output=True,
                        timeout=15,
                    )
                await backend.close()
                await backend.start()
                _, _recovered = await publish(label)
                record("actual-provider-outage-and-publication-recovery")

            initial_ref, initial = await publish("three-challenges-no-winner")
            assert initial["document"]["plan"]["q12"] == [
                [initial["document"]["plan"]["burn_uid"], Q12]
            ]
            await epoch("no-winner-all-burn")
            record("actual-all-burn-inclusion-finality-row-and-epochs")

            await recover(initial_ref, initial, "all-burn-publication-recovery")
            if mode == "operator":
                from carbon.chain.operations import (
                    load_config,
                    restored_publisher,
                    supervise,
                    verified_key,
                )
                from carbon.chain.operator_store import backup, journal_view, restore

                before_restart, _before_caps = await backend.observe()
                before_row = await backend.weight_row(
                    before_restart,
                    before_restart.resolve(roles["publisher"].ss58_address).uid,
                )
                await backend.close()
                await asyncio.to_thread(
                    subprocess.run,
                    ["docker", "restart", "--time", "35", session.container],
                    check=True,
                    capture_output=True,
                    timeout=55,
                )
                for attempt in range(4 * 12 + 1):
                    try:
                        after_restart, after_caps = await asyncio.wait_for(
                            backend.observe(), 3
                        )
                        after_caps.validate(
                            after_restart, roles["publisher"].ss58_address
                        )
                        break
                    except (TimeoutError, ChainFailure, PublicationFailure):
                        await backend.close()
                        if attempt == 29:
                            raise
                        await asyncio.sleep(max(0.25, block_time / 4))
                assert after_restart.finalized_block >= before_restart.finalized_block
                assert (
                    await backend.weight_row(
                        after_restart,
                        after_restart.resolve(roles["publisher"].ss58_address).uid,
                    )
                    == before_row
                )
                report["node_restart"] = {
                    "before_finalized_block": before_restart.finalized_block,
                    "after_finalized_block": after_restart.finalized_block,
                    "stored_row_preserved": True,
                    "same_container": inspect_isolation(session.container)["container"],
                }
                record("actual-node-restart-retains-finalized-chain-and-weight-row")

                async def verify_operator():
                    assert (
                        inspect_isolation(session.container)["container"]
                        == proof["container"]
                    )

                # Exercise external throwaway key loading and restored consumers against the real chain.
                config = load_config(tmp_path / "operator.json")
                config.key_file.write_text("//Alice_hk")
                config.key_file.chmod(0o600)
                backend.wallet = None
                backend.wallet = await verified_key(config, backend, verify_operator)
                publisher = restored_publisher(config, backend, reader)
                status = await supervise(
                    publisher,
                    asyncio.Event(),
                    verify_operator,
                    interval_seconds=1,
                    max_ticks=2,
                )
                assert status["last_dispatch_state"] == "ROW_VERIFIED"
                assert (
                    status["stored_weights_may_remain_effective"]
                    and not status["shutdown_clears_weights"]
                )
                bundle = tmp_path / "operator-backup"
                backup(receipts.path, bundle)
                restored = tmp_path / "restored.sqlite"
                restore(bundle, restored, context)
                with journal_view(receipts.path) as a, journal_view(restored) as b:
                    assert tuple(a.iterdump()) == tuple(b.iterdump())
                report["operator_health"] = status
                report["operator_backup_restore"] = "ALL_LOGICAL_TABLES_EQUAL"
                report["unobserved"] = [
                    "shielded miner registration",
                    "shared winner chain effects",
                    "recycled UID chain effects",
                ]
                record("actual-all-burn-operator-heartbeat-shutdown-and-backup-restore")
                return  # Explicit operator-only scope; G2 remains NOT_READY.
            await session.register_miners()
            record("shielded-miner-registration-finalized")
            winners = []
            for exam, (_, baseline) in zip(exams[::2], baselines[::2]):
                for variant in range(20, 60):
                    ref = await exam.commit(variant, signer("miner"))
                    batch = await ledger.open_batch(
                        exam.journal.context.identity,
                        f"{exam.profile.challenge_key.challenge_id}-{variant}",
                    )
                    accepted = exam.evaluate(ref)
                    state = await ledger.close_batch(batch)
                    if accepted is not None and float.fromhex(
                        state.record_hex
                    ) > float.fromhex(baseline.score_hex):
                        winners.append((ref, variant))
                        break
                else:
                    pytest.fail(
                        "No synthetic improvement in the fixed 40-attempt budget; no thresholds changed"
                    )
            target = ledger.resolve_projection(await ledger.project())
            assert len(target["targets"]["challenges"]) == 3
            assert len(target["targets"]["winners"]) == 1
            assert 0 < target["targets"]["burn"] < Q12
            report["shared_winner_target"] = target
            ref, paid = await publish("shared-winner-plus-burn")
            await epoch("shared-winner-plus-burn")
            record("three-challenge-shared-winner-complete-vector-observed")
            copied = await exams[0].commit(winners[0][1], signer("challenger"))
            assert copied == winners[0][0]
            before = ledger.resolve_projection(await ledger.project())["states"]
            assert exams[0].evaluate(copied).candidate == copied
            assert ledger.resolve_projection(await ledger.project())["states"] == before
            record("copied-artifact-wallet-change-has-no-new-credit")

            await recover(ref, paid, "winner-publication-recovery")
            old = await reader.observe(minimum_finalized_block=0)
            await session.execute(
                "replace-miner-hotkey",
                bt.SwapHotkey(
                    new_hotkey_ss58=roles["replacement"].ss58_address,
                    hotkey_ss58=roles["miner"].ss58_address,
                    netuid=2,
                ),
                "miner",
            )
            current = await reader.observe(minimum_finalized_block=old.finalized_block)
            assert current.resolve(roles["miner"].ss58_address) is None
            replacement = current.resolve(roles["replacement"].ss58_address)
            assert replacement.uid == old.resolve(roles["miner"].ss58_address).uid
            refreshed = ledger.resolve_projection(await ledger.project())
            assert refreshed["targets"]["burn"] == Q12
            _, _all_burn = await publish("identity-replacement-burn")
            await epoch("identity-replacement-all-burn")
            record("actual-recycled-uid-does-not-inherit-winner-target")
            for candidate_ref, _ in winners:
                ledger.hold(candidate_ref, WinnerStatus.CONTESTED, "synthetic-contest")
            report["public_scorecard"] = await ledger.release_scorecard(
                exams[0].journal.context.identity, winners[0][0]
            )
            assert report["public_scorecard"]["maturity"] == "SYNTHETIC_ONLY"
            report["stopped_publisher_exposure"] = publisher.exposure()
            report["g2"] = "NET5_RUNTIME_EVIDENCE_COLLECTED_NET6_PENDING"
            report["limitations"] = [
                "Synthetic exam only; no C1 scientific evidence or security qualification.",
                "Plain weights measured. Isolated runtime has no external drand beacon proof.",
                "Owner cuts and validator dividends remain separate from burned miner incentives.",
                "Yuma/stake/emission feedback can differ from application targets; inspect epoch samples.",
                "Withholding/drip-feeding/coordinated timing are not proven strategy-proof.",
                "Expiry/shutdown leaves stored chain weights effective until updated.",
            ]
            record("bounded-runtime-evidence-collected")
        except Exception as error:
            report["failure_type"] = type(error).__name__
            # Closed application errors are safe; raw SDK/pytest/private reprs are excluded.
            report["failure_code"] = (
                str(error)
                if type(error) is PublicationFailure
                else "SEE_PRIVATE_OPERATOR_DIAGNOSTIC"
            )
            write_evidence(directory / "integration.json", report)
            raise
        finally:
            if backend is not None:
                await backend.close()
            await session.close()

    asyncio.run(exercise())
