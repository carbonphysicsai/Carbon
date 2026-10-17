"""The lean direct path cannot turn research evidence into chain authority.

All chain identities, receipts, and publication backends here are local test
doubles. No SDK connection, wallet, signer, or public network is used.
"""

import asyncio
import dataclasses
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "cpu"))

from test_direct_v3_durable_tasks import _fixture as direct_fixture
from test_net2_transport import NOW, gateway, headers, snapshot, wire
from test_reward_testnet_winner_publication import (
    BATTERY,
    POLICY,
    composed,
)
from carbon import research
from carbon.chain import Participant
from carbon.rewards import testnet_winner_publication as publication
from carbon.rewards import winner_decay, winner_eligibility
from carbon.rewards.core import Q12
from carbon.scoring.solver_benchmark_v3 import register_pack
from carbon.transport.models import TransportFailure, digest
from scripts.dev.score_lab import solver_benchmark as benchmark


TOY_PHYSICS = {
    "version": "toy-physics-v1",
    "definition": {
        "scope": "toy-field",
        "governing_relation": "toy linear field",
        "assumptions": ["synthetic only"],
        "initial_conditions": {"field": 1},
        "boundary_conditions": {"field": 3},
        "constraints": {"field": "finite"},
        "output_units": {"field": "toy-unit"},
        "reference_applicability": "toy-claim",
        "acceptance_rules": {"physics": "toy boolean fixture"},
    },
}
TOY_PHYSICS_ID = benchmark.physics_contract_identity(TOY_PHYSICS)


def benchmark_fixture():
    """Keep the exact synthetic P/Q benchmark shape local to this boundary test."""
    registration = benchmark.register(
        {
            "schema": benchmark.SCHEMA,
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": "toy-field",
            "job_digest": "sha256:toy-job",
            "train_digest": "sha256:toy-train",
            "physics_contract": TOY_PHYSICS,
            "output": {
                "quantity": "field",
                "unit": "toy-unit",
                "size": 2,
                "metric": "mean_absolute_error",
            },
            "reference": {
                "solver_digest": "sha256:toy-solver",
                "fidelity_digest": "sha256:toy-fidelity",
                "applicability_digest": "sha256:toy-claim",
            },
            "cases": [
                {"id": "p1", "role": "P", "weight": 1},
                {"id": "p2", "role": "P", "weight": 2},
                {"id": "q1", "role": "Q", "weight": 1},
            ],
            "mandatory_gates": ["physics"],
            "timing_profile": {
                "basis": "ready_input_to_comparable_output",
                "model_device": "toy-cpu",
                "solver_device": "toy-cpu",
                "batch_size": 1,
            },
        }
    )
    references = [
        {
            "id": cid,
            "status": "RESOLVED",
            "outputs": [1.0, 3.0],
            "elapsed_s": 10.0,
            "source": "MEASURED_SOLVER_RUN",
            "solver_digest": "sha256:toy-solver",
            "fidelity_digest": "sha256:toy-fidelity",
            "applicability_digest": "sha256:toy-claim",
            "physics_contract_digest": TOY_PHYSICS_ID["definition_digest"],
            "peak_memory_bytes": 1024,
        }
        for cid in ("p1", "p2", "q1")
    ]

    def model(name, prediction, seconds, gate=True):
        return {
            "artifact_digest": name,
            "job_digest": "sha256:toy-job",
            "train_digest": "sha256:toy-train",
            "physics_contract_digest": TOY_PHYSICS_ID["definition_digest"],
            "build_seconds": 60.0,
            "cases": [
                {
                    "id": cid,
                    "status": "OK",
                    "source": "MEASURED_INFERENCE_RUN",
                    "outputs": list(prediction),
                    "gates": {"physics": gate},
                    "timing_s": {
                        "preprocess": 0.1,
                        "export": 0.1,
                        "inference": seconds - 0.3,
                        "postprocess": 0.1,
                    },
                    "peak_memory_bytes": 128,
                }
                for cid in ("p1", "p2", "q1")
            ],
        }

    return registration, references, model


def test_direct_result_transport_stays_bound_to_signed_registration(tmp_path):
    gate = gateway(tmp_path)
    body = wire(
        tool=research.RESEARCH_NAMESPACE,
        fields={"call_base64": "Zml4dHVyZQ=="},
    )
    received = asyncio.run(gate.receive(body, headers(body)))
    assert received.call.tool == research.RESEARCH_NAMESPACE
    assert gate.journal.resolve(received.receipt.ref).body_digest == digest(body)
    first_requester = received.requester

    # A recycled UID cannot inherit the signed request or its requester ID.
    prior = snapshot()
    gate.adapter.state = dataclasses.replace(
        prior,
        finalized_block=11,
        participants=(
            prior.participants[0],
            Participant(1, "new-miner", "new-cold", 11),
        ),
    )
    with pytest.raises(TransportFailure, match="CONTEXT"):
        asyncio.run(gate.receive(body, headers(body, NOW + 1)))
    new_body = wire(
        gate.adapter.state,
        request="direct-result-new-registration",
        tool=research.RESEARCH_NAMESPACE,
        fields={"call_base64": "Zml4dHVyZQ=="},
    )
    new = asyncio.run(
        gate.receive(new_body, headers(new_body, NOW + 2, hotkey="new-miner"))
    )
    assert new.requester != first_requester
    assert new.receipt.uid == 1


def test_stored_direct_result_cannot_become_winner_intent(tmp_path, monkeypatch):
    request, provider, _ = direct_fixture(tmp_path / "direct", monkeypatch)
    tasks = provider()
    try:
        started = tasks.start_research_task(request)
        result = tasks.get_research_result(
            research.DirectGetTaskRequestV3(request.challenge_key, started.task.task_id)
        )
        raw = dataclasses.asdict(result)
    finally:
        tasks.close()

    issuer, backend, _ = composed(tmp_path, source=lambda: raw)
    with pytest.raises(
        publication.WinnerPublicationRefused, match="WINNER_SOURCE_UNAVAILABLE"
    ):
        issuer.issue(backend.state)
    assert issuer.ledger.records(BATTERY) == []
    with issuer.receipts.transaction() as db:
        assert db.execute(
            "SELECT count(*) FROM testnet_winner_intent_v1"
        ).fetchone() == (0,)
    assert backend.executions == backend.signed == 0


def test_raw_score_and_development_source_cannot_set_weights(tmp_path):
    raw_score = {
        "model_id": "stored-model",
        "hotkey": "miner-hotkey",
        "kind": "SCORED",
        "score": 1_000_000.0,
    }
    record = winner_eligibility.WinnerLedger(tmp_path / "winners.jsonl").observe(
        POLICY,
        BATTERY,
        raw_score,
        {"miner-hotkey": "miner-coldkey"},
        20 * winner_decay.DAY_MS,
    )
    assert record["eligible"] is False
    payable = winner_eligibility.payable(record, {"miner-hotkey"})
    assert payable is None
    targets = winner_decay.epoch_targets(
        POLICY, {BATTERY: payable}, 20 * winner_decay.DAY_MS
    )
    assert targets["burn"] == Q12
    with pytest.raises(
        publication.WinnerPublicationRefused,
        match="DEVELOPMENT_DEPLOYMENT_NEVER_SETS_WEIGHTS",
    ):
        publication.check_weight_source(SimpleNamespace(development_only=True))


def test_complete_development_benchmark_cannot_become_winner_or_weight(tmp_path):
    registration, references, model = benchmark_fixture()
    pack = register_pack(
        {
            "schema": "carbon.scoring.solver-benchmark-pack.v3",
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": "toy-field",
            "benchmark_registration_digest": registration["registration_digest"],
            "physics_contract": TOY_PHYSICS_ID,
            "output": {
                "quantity": "field",
                "unit": "toy-unit",
                "metric": "mean_absolute_error",
            },
            "hard_gates": ["physics"],
            "accuracy_ceiling": 0.25,
            "performance_objective": "maximize_paired_speedup",
        }
    )
    complete = benchmark.compare(
        registration,
        references,
        [model("fast-and-accurate", [1.0, 3.0], 1.0)],
        score_pack=pack,
    )
    scored = complete["scoring"]
    assert complete["models"][0]["by_role"]["P"]["status"] == "MEASURED_DEVELOPMENT"
    assert complete["models"][0]["by_role"]["Q"]["attempted"] == 1
    assert scored["schema"] == "carbon.scoring.solver-benchmark-score.v3"
    assert scored["status"] == "DEVELOPMENT_ONLY"
    assert scored["ranking"] == ["fast-and-accurate"]
    assert scored["models"][0]["status"] == "SCORED_DEVELOPMENT"
    assert scored["models"][0]["performance_score"] == pytest.approx(10.0)

    current = {"value": complete}
    issuer, backend, _ = composed(tmp_path, source=lambda: current["value"])
    for value in (complete, scored):
        current["value"] = value
        with pytest.raises(
            publication.WinnerPublicationRefused, match="WINNER_SOURCE_UNAVAILABLE"
        ):
            issuer.issue(backend.state)
        assert issuer.ledger.records(BATTERY) == []
        with issuer.receipts.transaction() as db:
            assert db.execute(
                "SELECT count(*) FROM testnet_winner_intent_v1"
            ).fetchone() == (0,)
        assert backend.executions == backend.signed == 0

    with pytest.raises(
        publication.WinnerPublicationRefused,
        match="DEVELOPMENT_DEPLOYMENT_NEVER_SETS_WEIGHTS",
    ):
        publication.check_weight_source(
            SimpleNamespace(development_only=True, benchmark=complete)
        )
