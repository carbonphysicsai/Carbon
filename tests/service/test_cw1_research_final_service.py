"""Real numerical fresh-profile source path with an explicitly synthetic chain.

Fixed engineering recipes and keys exercise composition only. They are not real
agent inference, public-testnet activity, or the owner-authorized campaign.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

from bittensor.keyfiles import Keypair

from carbon.chain import ChainContext, MetagraphSnapshot, Participant
from carbon.chain.sdk import BittensorReader
from carbon.development_comparison.acceptance import resolve_acceptance
from carbon.development_session import research_campaign
from carbon.development_session.research_campaign import final_epoch, frozen_seeds
from carbon.development_session.research_data import PublicReferenceData
from carbon.development_session.research_generation import generate_roles
from carbon.development_session.research_ledger import (
    CEILINGS,
    ELAPSED_SECONDS,
    VERSION,
    CampaignLedger,
)
from carbon.reconstruction.worker.docker_runtime import load_image_identity


def test_real_fresh_final_sources_compare_and_resume_without_redispatch(
    tmp_path, monkeypatch
):
    ledger = CampaignLedger(tmp_path / "engineering-fresh-final")
    owner = "synthetic-engineering-owner"
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": CEILINGS,
            "elapsed_seconds": ELAPSED_SECONDS,
            **{
                name: owner
                for name in (
                    "campaign_id",
                    "implementation",
                    "objective",
                    "sampling",
                    "control",
                    "selection",
                    "replica_policy",
                    "provider",
                    "owner",
                )
            },
        }
    )
    manifest = Path(os.environ["CARBON_C03_IMAGE_MANIFEST"])
    image = load_image_identity(manifest)
    miner = Keypair.create_from_uri("//Alice")
    publisher = Keypair.create_from_uri("//Bob")
    context = ChainContext(
        "testnet", "ws://127.0.0.1:1", "synthetic-d4", "0x" + "2" * 64, 567
    )
    sequence = 100

    async def capture(self, requested):
        nonlocal sequence
        sequence += 1
        assert requested == context
        return MetagraphSnapshot(
            context,
            sequence,
            "0x" + f"{sequence:064x}",
            time.time_ns() // 1_000_000,
            (
                Participant(0, publisher.ss58_address, "synthetic-owner", 1),
                Participant(1, miner.ss58_address, "synthetic-miner", 2),
            ),
        )

    monkeypatch.setattr(BittensorReader, "capture", capture)
    strategy = {
        "schema_version": "1.0",
        "challenge_id": "burgers-dynamics-v1",
        "backbone": "fno",
        "parameters": {
            "steps": 2,
            "width": 4,
            "depth": 1,
            "n_modes": 4,
            "enforce_mean": True,
        },
    }
    monkeypatch.setattr(research_campaign, "CONTROL", strategy)
    previous = os.umask(0o077)
    try:
        seeds = frozen_seeds(ledger.root)
        roles = generate_roles(ledger, owner=owner, image=image)
        data = PublicReferenceData(
            ledger=ledger, owner=owner, image=image, role_root=roles
        )
        args = SimpleNamespace(
            image_manifest=manifest,
            quarantine_journal=ledger.root / "quarantine.sqlite3",
        )
        config = SimpleNamespace(
            context=context, publisher_hotkey=publisher.ss58_address
        )

        async def run():
            return await final_epoch(
                args,
                ledger,
                owner,
                1,
                strategy,
                seeds,
                roles,
                data,
                image,
                miner,
                config,
            )

        feedback, ref = asyncio.run(run())
        result = resolve_acceptance(ref)
        assert result["schema"].endswith(".v2") and result["prospective"]
        assert (
            not result["official_eligible"]
            and not result["network_eligible"]
            and not result["paying"]
        )
        assert result["baseline"]["authenticated_hotkey"] == miner.ss58_address
        assert len(result["measurements"]["sources"]) == 2
        assert all(len(rows) == 72 for rows in result["measurements"]["sources"])
        assert len(result["measurements"]["reference_checks"]) == 24
        before = ledger.status(owner=owner)["used"]
        assert before["provider_attempts"] == before["research_trials"] == 0
        assert before["final_replicas"] == 6
        assert (
            before["reference_invocations"] == before["reference_trajectories"] == 144
        )
        assert asyncio.run(run()) == (feedback, ref)
        assert ledger.status(owner=owner)["used"] == before
        rendered = json.dumps(feedback)
        for private in (
            str(ledger.root),
            "case_digest",
            "solution_path",
            "seed",
            "private-role",
        ):
            assert private not in rendered
    finally:
        os.umask(previous)
