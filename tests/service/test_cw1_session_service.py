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
from types import SimpleNamespace

import pytest
from bittensor.keyfiles import Keypair

from carbon import audit
from carbon.chain import ChainContext, MetagraphSnapshot, Participant
from carbon.chain.sdk import BittensorReader
from carbon.development_session import data as session_data
from carbon.development_session.data import prepare
from carbon.development_session.service import LocalMinerConnection, scaffold
from carbon.evaluation.enums import ReferenceFailureReason, ReferenceRunOutcome
from tests.cpu._signer_harness import in_thread_signer


def test_reference_failure_retains_private_typed_result_without_redispatch(
    tmp_path, monkeypatch
):
    root = tmp_path / "synthetic-session"
    calls = []
    request_digest = "sha256:" + "a" * 64
    case = SimpleNamespace(coordinates=SimpleNamespace(role="TRAIN"))
    manifest = {"cases": [{"name": "train-00"}]}

    def freeze(root, image_manifest):
        root.mkdir(mode=0o700, exist_ok=True)
        return manifest

    result = SimpleNamespace(
        result=SimpleNamespace(
            outcome=ReferenceRunOutcome.NUMERICAL_FAILURE,
            failure_reason=ReferenceFailureReason.NUMERICAL_NONCONVERGENCE,
        ),
        resources={
            "memory": {
                "peak_bytes": 4096,
                "events": {"oom": 0, "oom_kill": 0, "secret": "excluded"},
            },
            "pids": {"peak": 2},
            "secret": "excluded",
        },
    )

    class Budget:
        def __init__(self, path):
            pass

        def run_worker(self, digest, execute):
            calls.append(digest)
            return execute()

    monkeypatch.setattr(session_data, "freeze", freeze)
    monkeypatch.setattr(session_data, "frozen_cases", lambda root: (case,))
    monkeypatch.setattr(session_data, "load_image_identity", lambda path: object())
    monkeypatch.setattr(
        session_data, "DevelopmentWorkerProfile", lambda *args: object()
    )
    monkeypatch.setattr(
        session_data,
        "IsolatedBurgersReferenceController",
        lambda **kw: SimpleNamespace(execute=lambda request: result),
    )
    monkeypatch.setattr(session_data, "SessionBudget", Budget)
    monkeypatch.setattr(
        session_data,
        "build_reference_request",
        lambda *args, **kw: SimpleNamespace(request_digest=request_digest),
    )
    monkeypatch.setattr(session_data, "requested_times", lambda *args: ())
    monkeypatch.setattr(
        session_data, "runtime_environment_digest", lambda: "sha256:" + "b" * 64
    )

    for _ in range(2):
        with pytest.raises(ValueError, match="reference failure; retain run and stop"):
            session_data.prepare(root, tmp_path / "image.json")

    assert calls == [request_digest]
    path = root / "train-00-reference-result.json"
    record = json.loads(path.read_bytes())
    assert record == {
        "request_digest": request_digest,
        "outcome": "NUMERICAL_FAILURE",
        "failure_reason": "NUMERICAL_NONCONVERGENCE",
        "candidate_judged": False,
        "resources": {
            "memory_peak_bytes": 4096,
            "memory_oom_events": 0,
            "memory_oom_kill_events": 0,
            "pids_peak": 2,
        },
    }
    assert path.stat().st_mode & 0o777 == 0o600
    assert b"excluded" not in path.read_bytes()


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
    # Carbon holds no key: the miner's own signer signs each request.
    signing = in_thread_signer(miner)
    signer = signing.__enter__()
    previous = os.umask(0o077)
    try:
        prepare(root, image)
        connection = LocalMinerConnection(
            root, image, context, publisher.ss58_address, signer
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
        from carbon.development_testnet.execution import load_source_handoff
        from carbon.development_testnet.operator import TESTNET_GENESIS

        source = load_source_handoff(root / f"source-{sid}.json")
        assert source.transport_context == context
        assert source.transport_context.genesis_hash != TESTNET_GENESIS
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
        signing.__exit__(None, None, None)
