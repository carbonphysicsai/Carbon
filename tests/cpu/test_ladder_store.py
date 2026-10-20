"""Each miner's best private-exam Ladder document, stored and served
(OWNER-GRADE-FEEDBACK-LADDER-01, serving lane).

Claims: per (hotkey, Challenge, exam pack) only the latest best document is
kept, exactly as the builder emits it; results that do not improve never move
it; another hotkey or another exam pack never sees it; the intake serves only
the signed caller's own document and keeps the `tools` list deployed clients
pin; the client accepts back only the builder's allow-listed fields.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import direct_intake
from carbon.challenge_validator.ladder_store import (
    LadderStore,
    LadderStoreRefused,
    checked,
)
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.development_session import direct_submission as client
from carbon.registry.model import ChallengeKey
from carbon.scoring import grade_feedback as gf

MOTOR = ChallengeKey("electric-motor-magnetics", "1.0")
GATES = ("native_motor_valid", "complete_fixed_coverage")
EXAM = "sha256:" + "e" * 64


def _scored(total, a, d):
    return {
        "artifact_digest": "sha256:" + "a" * 64,
        "status": "SCORED_DEVELOPMENT_CANDIDATE",
        "score": total,
        "legs": {"A": a, "D": d},
        "gates": {g: "PASS" for g in GATES},
        "components": {"robust_fidelity_benefit": a},
    }


@pytest.fixture
def store(tmp_path):
    root = tmp_path / "receiver"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    return LadderStore(AttemptLedger(root / "attempts.sqlite3"))


def _record(store, graded, hotkey="5Miner", exam=EXAM):
    return store.record(
        hotkey, MOTOR, exam, graded, exam_version="motor-exam-1", gates=GATES
    )


def test_only_the_latest_best_document_is_kept_exactly_as_the_builder_emits_it(store):
    assert store.served("5Miner", MOTOR, EXAM) is None
    first = _record(store, _scored(0.60, 0.30, 0.90))
    assert first["status"] == "IMPROVED"
    assert store.served("5Miner", MOTOR, EXAM) == first
    # Under one step: shown as NO_IMPROVEMENT, and the best does not move.
    near = _record(store, _scored(0.61, 0.31, 0.91))
    assert near["status"] == "NO_IMPROVEMENT"
    assert store.served("5Miner", MOTOR, EXAM) == first
    better = _record(store, _scored(0.70, 0.35, 0.95))
    assert better["status"] == "IMPROVED"
    served = store.served("5Miner", MOTOR, EXAM)
    assert served == better and set(served) == gf.FIELDS


def test_results_that_do_not_count_never_move_the_best(store):
    best = _record(store, _scored(0.60, 0.30, 0.90))
    for graded in (
        {"status": "INDETERMINATE_EVIDENCE"},
        {"status": "FAILED_INFRA"},
        {
            **_scored(0.10, 0.0, 0.0),
            "status": "MANDATORY_GATE_FAILED",
            "gates": {GATES[0]: "FAIL", GATES[1]: "PASS"},
        },
    ):
        _record(store, graded)
        assert store.served("5Miner", MOTOR, EXAM) == best


def test_another_hotkey_or_exam_pack_never_sees_the_document(store):
    _record(store, _scored(0.60, 0.30, 0.90))
    assert store.served("5Other", MOTOR, EXAM) is None
    assert store.served("5Miner", MOTOR, "sha256:" + "f" * 64) is None
    other = ChallengeKey("chip-cold-plate", "1.0")
    assert store.served("5Miner", other, EXAM) is None


def test_a_stored_row_with_anything_but_the_allow_list_is_refused(store):
    _record(store, _scored(0.60, 0.30, 0.90))
    with store.ledger._db() as db:
        (raw,) = db.execute("SELECT document FROM ladder_best").fetchone()
        tampered = {**json.loads(raw), "per_case": [0.1]}
        db.execute("UPDATE ladder_best SET document=?", (json.dumps(tampered),))
    with pytest.raises(LadderStoreRefused) as refused:
        store.served("5Miner", MOTOR, EXAM)
    assert refused.value.code == "ladder_document"


def _intake(store, exam=EXAM):
    adapter = SimpleNamespace(
        ledger=store.ledger,
        discovery=SimpleNamespace(
            evaluation_pack_snapshot=SimpleNamespace(manifest_digest=exam)
        ),
    )
    intake = object.__new__(direct_intake.DirectRecipeIntake)
    intake.adapter, intake.challenge = adapter, MOTOR
    return intake


def test_the_intake_serves_only_the_signed_callers_own_document(store):
    best = _record(store, _scored(0.60, 0.30, 0.90))
    answer = _intake(store)._feedback("5Miner")
    assert answer.status == 200
    assert answer.body == {
        "schema": direct_intake.FEEDBACK_REPLY_SCHEMA,
        "challenge": {"id": MOTOR.challenge_id, "version": MOTOR.version},
        "document": best,
    }
    assert _intake(store)._feedback("5Other").body["document"] is None
    assert _intake(store, exam=None)._feedback("5Miner").body["document"] is None


def test_the_public_facts_advertise_the_read_and_keep_the_pinned_tools_list():
    # Deployed clients pin `tools` exactly; the read has its own facts entry.
    assert client.FEEDBACK_FACTS["tool"] == direct_intake.FEEDBACK_TOOL
    assert client.FEEDBACK_FACTS["reply_schema"] == direct_intake.FEEDBACK_REPLY_SCHEMA
    source = Path(direct_intake.__file__).read_text(encoding="utf-8")
    assert '"tools": [SUBMIT_TOOL, STATUS_TOOL, RESEARCH_NAMESPACE]' in source


@pytest.mark.parametrize(
    "extra",
    [{"per_case": [0.1]}, {"artifact_digest": "sha256:" + "a" * 64}],
)
def test_the_client_refuses_any_field_beyond_the_builders(extra):
    doc = checked(
        gf.ladder_feedback(
            _scored(0.6, 0.3, 0.9),
            best=None,
            exam_version="motor-exam-1",
            gate_registry=GATES,
        )
    )
    with pytest.raises(LadderStoreRefused):
        checked({**doc, **extra})
