"""A reported pool total is projected onto the miner's registered Ladder grid.

The public handoff's 0.234018 total is used only as a scalar fixture. The
equal A/D legs below are synthetic and do not reproduce the private model's
legs. No receiver, signature, worker or private exam is exercised here.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.challenge_validator import direct_intake
from carbon.challenge_validator.ladder_store import LadderStore
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.registry.model import ChallengeKey
from carbon.scoring import grade_feedback


@pytest.mark.parametrize(
    ("total", "expected"),
    [(0.234018, 0.22), (0.239999, 0.22), (0.24, 0.24)],
)
def test_pool_total_reaches_the_miner_on_the_ladder_grid(tmp_path, total, expected):
    root = tmp_path / "synthetic-receiver"
    root.mkdir(mode=0o700)
    ledger = AttemptLedger(root / "attempts.sqlite3")
    store = LadderStore(ledger)
    challenge = ChallengeKey("electric-motor-magnetics", "1.5")
    exam = "sha256:" + "e" * 64
    owner = "synthetic-ladder-owner"
    gates = ("native_motor_valid", "complete_fixed_coverage")
    graded = {
        "artifact_digest": "sha256:" + "a" * 64,
        "status": "SCORED_DEVELOPMENT_CANDIDATE",
        "score": total,
        "legs": {"A": total, "D": total},
        "gates": {name: "PASS" for name in gates},
    }
    document = store.record(
        owner,
        challenge,
        exam,
        graded,
        exam_version="motor-pool-sealed-v1",
        gates=gates,
        rebuild_noise=None,
        recipe_digest="sha256:" + "d" * 64,
        epoch=7,
    )
    intake = object.__new__(direct_intake.DirectRecipeIntake)
    intake.challenge = challenge
    intake.adapter = SimpleNamespace(
        ledger=ledger,
        discovery=SimpleNamespace(
            evaluation_pack_snapshot=SimpleNamespace(manifest_digest=exam)
        ),
    )
    response = intake._feedback(owner)
    assert response.status == 200
    assert response.body["best"] == response.body["latest"] == document
    assert document["status"] == "IMPROVED"
    assert document["total"] == expected
    assert set(document) == grade_feedback.FIELDS_V3
    assert graded["score"] == total
    assert "score" not in document and "legs" not in document
