"""Full numerical composition regression, without provider calls or chain writes.

Only chain observation is synthetic. Fixed test keys and a false genesis cannot
represent registration on the public testnet. Numerical execution is real but
is engineering evidence, never a model-backed result or qualification.
"""

import asyncio
import json
import os
import time
from pathlib import Path

from bittensor.keyfiles import Keypair

from carbon import audit
from carbon.chain import ChainContext, MetagraphSnapshot, Participant
from carbon.chain.sdk import BittensorReader
from carbon.development_session.data import prepare
from carbon.development_session.service import LocalMinerConnection, scaffold


def test_authenticated_session_under_private_umask_reaches_signed_feedback(
    tmp_path, monkeypatch
):
    image = Path(os.environ["CARBON_C03_IMAGE_MANIFEST"])
    root = tmp_path / "synthetic-session"
    miner = Keypair.create_from_uri("//Alice")
    publisher = Keypair.create_from_uri("//Bob")
    context = ChainContext(
        "testnet", "ws://127.0.0.1:1", "synthetic-cw1", "0x" + "1" * 64, 567
    )

    sequence = 10

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
    previous = os.umask(0o077)
    try:
        prepare(root, image)
        connection = LocalMinerConnection(
            root, image, context, publisher.ss58_address, miner
        )
        base = {"challenge_id": "burgers-dynamics-v1", "challenge_version": "1.0"}
        strategy = scaffold()
        strategy["parameters"]["steps"] = 48
        discovery = asyncio.run(connection.call("get_challenge_info", base))
        assert discovery["effectively_live"] is False
        assert asyncio.run(connection.call("dry_validate", {"strategy": strategy}))[
            "valid"
        ]
        submitted = asyncio.run(
            connection.call("submit", {**base, "strategy": strategy})
        )
        sid = submitted["submission_id"]
        assert submitted["status"] == "COMPLETE_UNRESOLVED"
        feedback = asyncio.run(
            connection.call("get_submission_result", {"submission_id": sid})
        )
        assert feedback["status"] == "COMPLETE_UNRESOLVED"
        assert feedback["feedback"]["score"] is None
        assert not any(feedback["feedback"]["eligibility"].values())
        for cohort in feedback["feedback"]["cohorts"].values():
            assert cohort["parents"] == 12 and cohort["replicas"] == 3
        complete, _ = connection.completed[sid]
        _, state = connection.ledger.resolve(
            complete.ledger_reference, verified_at_micros=time.time_ns() // 1000
        )
        assert state is audit.ReceiptLifecycleState.ACTIVE
        assert (root / f"source-{sid}.json").is_file()
        attempt = root / "evaluations" / sid
        dossier = json.loads((attempt / "dossier.json").read_bytes())
        assert dossier["training_runs"] == 3
        assert dossier["training_steps"] == 144
        assert len(dossier["measurements"]) == 72
        for index in range(3):
            prediction = attempt / f"prediction-{index}"
            assert prediction.stat().st_mode & 0o777 == 0o700
            assert (prediction / "input").stat().st_mode & 0o777 == 0o755
            assert (prediction / "prediction.json").is_file()
        # Same strategy cannot retrain or duplicate its signed source.
        before = connection.budget.summary()
        assert (
            asyncio.run(connection.call("submit", {**base, "strategy": strategy}))
            == submitted
        )
        assert connection.budget.summary() == before
        rendered = json.dumps(feedback)
        for private in (
            str(root),
            "private-generation",
            "seed",
            "solution_path",
            "case_digest",
        ):
            assert private not in rendered
    finally:
        os.umask(previous)
