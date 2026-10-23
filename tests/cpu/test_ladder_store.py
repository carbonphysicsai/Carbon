"""Each miner's best private-exam Ladder document, stored and served
(OWNER-GRADE-FEEDBACK-LADDER-01, serving lane).

Claims: per (hotkey, Challenge, exam pack) the store keeps two documents
exactly as the builder emits them, the best (last IMPROVED) and the latest
(any status); results that do not improve never move the best, and a gate
failure reaches the miner as the latest with its registered gate names;
another hotkey or another exam pack never sees either; the intake serves only
the signed caller's own documents and keeps the `tools` list deployed clients
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


def _record(store, graded, hotkey="5Miner", exam=EXAM, noise=None):
    return store.record(
        hotkey,
        MOTOR,
        exam,
        graded,
        exam_version="motor-exam-1",
        gates=GATES,
        rebuild_noise=noise,
    )


def _noise(value):
    # The KOTH comparator's registration shape (KOTH-TAKEOVER-RULE-01 §1).
    return {"value": value, "measurement_digest": "sha256:" + "9" * 64}


def test_a_registered_rebuild_noise_above_eta_widens_the_step(store, tmp_path):
    coarse = _record(store, _scored(0.63, 0.33, 0.93), noise=_noise(0.05))
    assert coarse["total"] == 0.6 and "A" not in coarse
    # 0.64 clears eta (0.60 + 0.02) but not the registered 0.05 step.
    assert (
        _record(store, _scored(0.64, 0.34, 0.94), noise=_noise(0.05))["status"]
        == "NO_IMPROVEMENT"
    )
    assert (
        _record(store, _scored(0.66, 0.36, 0.96), noise=_noise(0.05))["status"]
        == "IMPROVED"
    )
    # The same results under no registration step at eta.
    root = tmp_path / "eta"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    eta = LadderStore(AttemptLedger(root / "attempts.sqlite3"))
    fine = _record(eta, _scored(0.63, 0.33, 0.93))
    assert fine["total"] == 0.62 and "D" not in fine
    assert _record(eta, _scored(0.64, 0.34, 0.94))["status"] == "IMPROVED"


def test_a_noise_below_eta_keeps_eta_and_a_malformed_one_is_refused(store):
    fine = _record(store, _scored(0.63, 0.33, 0.93), noise=_noise(0.001))
    assert fine["total"] == 0.62
    for bad in ({"value": 0.05}, {**_noise(0.05), "host": "x"}, 0.05):
        with pytest.raises(LadderStoreRefused) as refused:
            _record(store, _scored(0.7, 0.4, 0.9), noise=bad)
        assert refused.value.code == "ladder_rebuild_noise"


def test_record_cannot_leave_out_the_rebuild_noise(store):
    with pytest.raises(TypeError):
        store.record(
            "5Miner",
            MOTOR,
            EXAM,
            _scored(0.6, 0.3, 0.9),
            exam_version="motor-exam-1",
            gates=GATES,
        )


def test_only_the_latest_best_document_is_kept_exactly_as_the_builder_emits_it(store):
    assert store.served("5Miner", MOTOR, EXAM) == {"best": None, "latest": None}
    first = _record(store, _scored(0.60, 0.30, 0.90))
    assert first["status"] == "IMPROVED"
    assert store.served("5Miner", MOTOR, EXAM) == {"best": first, "latest": first}
    # Under one step: shown as NO_IMPROVEMENT, and the best does not move.
    near = _record(store, _scored(0.61, 0.31, 0.91))
    assert near["status"] == "NO_IMPROVEMENT"
    assert store.served("5Miner", MOTOR, EXAM) == {"best": first, "latest": near}
    better = _record(store, _scored(0.70, 0.35, 0.95))
    assert better["status"] == "IMPROVED"
    served = store.served("5Miner", MOTOR, EXAM)
    assert served == {"best": better, "latest": better}
    assert set(served["best"]) == gf.FIELDS


def test_a_gate_failure_after_an_improvement_is_served_as_the_latest(store):
    best = _record(store, _scored(0.60, 0.30, 0.90))
    failed = _record(
        store,
        {
            **_scored(0.90, 0.45, 0.99),
            "status": "MANDATORY_GATE_FAILED",
            "gates": {GATES[0]: "FAIL", GATES[1]: "PASS"},
        },
    )
    served = store.served("5Miner", MOTOR, EXAM)
    # The best keeps its values; the latest names the registered failed gate.
    assert served["best"] == best
    assert served["latest"] == failed
    assert served["latest"]["status"] == "GATE_FAILED"
    assert served["latest"]["gate_names"] == [GATES[0]]
    assert [served["latest"][k] for k in ("total",)] == [best[k] for k in ("total",)]


def test_a_first_result_that_does_not_count_leaves_no_best(store):
    shown = _record(store, {"status": "INDETERMINATE_EVIDENCE"})
    assert shown["status"] == "NOT_SCORED"
    assert store.served("5Miner", MOTOR, EXAM) == {"best": None, "latest": shown}


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
        shown = _record(store, graded)
        assert store.served("5Miner", MOTOR, EXAM) == {"best": best, "latest": shown}


def test_another_hotkey_or_exam_pack_never_sees_the_document(store):
    _record(store, _scored(0.60, 0.30, 0.90))
    nothing = {"best": None, "latest": None}
    assert store.served("5Other", MOTOR, EXAM) == nothing
    assert store.served("5Miner", MOTOR, "sha256:" + "f" * 64) == nothing
    other = ChallengeKey("chip-cold-plate", "1.0")
    assert store.served("5Miner", other, EXAM) == nothing


@pytest.mark.parametrize(
    "column, change",
    [
        ("best", {"per_case": [0.1]}),
        ("latest", {"per_case": [0.1]}),
        ("best", {"status": "GATE_FAILED"}),
        ("latest", {"status": "MANDATORY_GATE_FAILED"}),
    ],
)
def test_a_stored_row_with_anything_but_the_allow_list_is_refused(
    store, column, change
):
    _record(store, _scored(0.60, 0.30, 0.90))
    with store.ledger._db() as db:
        (raw,) = db.execute(f"SELECT {column} FROM ladder_feedback_v2").fetchone()
        tampered = {**json.loads(raw), **change}
        db.execute(f"UPDATE ladder_feedback_v2 SET {column}=?", (json.dumps(tampered),))
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
    latest = _record(store, _scored(0.61, 0.31, 0.91))
    answer = _intake(store)._feedback("5Miner")
    assert answer.status == 200
    assert answer.body == {
        "schema": direct_intake.FEEDBACK_REPLY_SCHEMA,
        "challenge": {"id": MOTOR.challenge_id, "version": MOTOR.version},
        "best": best,
        "latest": latest,
    }
    for body in (
        _intake(store)._feedback("5Other").body,
        _intake(store, exam=None)._feedback("5Miner").body,
    ):
        assert (body["best"], body["latest"]) == (None, None)


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
            rebuild_noise=None,
        )
    )
    with pytest.raises(LadderStoreRefused):
        checked({**doc, **extra})
    with pytest.raises(LadderStoreRefused):
        checked({**doc, **extra}, latest=True)


def test_a_latest_document_takes_any_builder_status_and_nothing_else():
    doc = gf.ladder_feedback(
        {"status": "FAILED_INFRA"},
        best=None,
        exam_version="motor-exam-1",
        gate_registry=GATES,
        rebuild_noise=None,
    )
    assert checked(doc, latest=True)["status"] == "NOT_SCORED"
    with pytest.raises(LadderStoreRefused):
        checked(doc)
    with pytest.raises(LadderStoreRefused):
        checked({**doc, "status": "FAILED_INFRA"}, latest=True)


def _client_read(monkeypatch, reply):
    from carbon.chain.models import ChainContext
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.development_session.construction_recipe import ConstructionRecipe
    from carbon.reconstruction.served_recipe_contract import registered

    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)
    kit = bundle_material_v5()["construction_kit"]
    recipe = ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": kit,
            "source": {"kind": "graph", "submission_digest": "sha256:" + "a" * 64},
            "procedure": {
                "entrypoint": None,
                "configuration": {},
                "train_use": {"cases": "all"},
                "initial_state": None,
            },
            "output": {
                "format": "carbon.numeric-graph.v1",
                "interface_digest": kit["interface_digest"],
            },
        }
    )
    contract = registered("synthetic-linear-field-2d", "1.3").digest
    context = ChainContext(
        "testnet", "wss://chain.example", "fixture", "0x" + "1" * 64, 567
    )
    facts = {
        "schema": client.PUBLIC_SCHEMA,
        "network": context.network,
        "genesis": context.genesis_hash,
        "netuid": context.netuid,
        "challenge": {"id": "synthetic-linear-field-2d", "version": "1.3"},
        "receiver": "validator-pinned",
        "snapshot": {"id": "snapshot-1"},
        "discovery_path": client.INFO_PATH,
        "path": client.SUBMIT_PATH,
        "tools": [client.SUBMIT_TOOL, client.STATUS_TOOL],
        "served_contracts": [{"level": 0, "digest": contract}],
        "score_pack": None,
        "qualification": False,
        "reward": False,
        "exam_feedback": client.FEEDBACK_FACTS,
    }
    sent = []

    def send(url, body, headers):
        sent.append(json.loads(body))
        return 200, {
            "schema": client.FEEDBACK_REPLY_SCHEMA,
            "challenge": {"id": "synthetic-linear-field-2d", "version": "1.3"},
            **reply,
        }

    result = client.read_exam_feedback(
        "http://127.0.0.1:9080",
        "external-signer",
        recipe=recipe,
        contract_digest=contract,
        receiver="validator-pinned",
        context=context,
        read=lambda url: facts,
        send=send,
    )
    assert [call["tool"] for call in sent] == [client.FEEDBACK_TOOL]
    assert all(call["fields"] == {} for call in sent)
    return result


def test_the_client_reads_back_the_best_and_a_gate_failed_latest(monkeypatch):
    best = gf.ladder_feedback(
        _scored(0.6, 0.3, 0.9),
        best=None,
        exam_version="e1",
        gate_registry=GATES,
        rebuild_noise=None,
    )
    latest = gf.ladder_feedback(
        {
            **_scored(0.9, 0.4, 0.9),
            "status": "MANDATORY_GATE_FAILED",
            "gates": {GATES[0]: "FAIL", GATES[1]: "PASS"},
        },
        best=best,
        exam_version="e1",
        gate_registry=GATES,
        rebuild_noise=None,
    )
    read = _client_read(monkeypatch, {"best": best, "latest": latest})
    assert read == {"best": best, "latest": latest}
    assert _client_read(monkeypatch, {"best": None, "latest": None}) == {
        "best": None,
        "latest": None,
    }
    for reply in (
        {"best": latest, "latest": latest},
        {"best": best, "latest": {**latest, "per_case": [0.1]}},
        {"document": best},
    ):
        with pytest.raises(client.DirectIntakeRefusal) as refused:
            _client_read(monkeypatch, reply)
        assert refused.value.code == "exam_feedback_reply_invalid"


def _hook(store):
    from carbon.challenge_validator import lean_recipe_retention as retention

    adapter = SimpleNamespace(
        ledger=store.ledger,
        owner=lambda submission_id: "5Miner",
        discovery=SimpleNamespace(info=SimpleNamespace(challenge_key=MOTOR)),
    )
    return retention._record_ladder(
        adapter,
        "submission-1",
        exam_key=EXAM,
        exam_version="motor-exam-1",
        gates=GATES,
        graded=_scored(0.63, 0.33, 0.93),
    )


def test_the_retention_hook_steps_at_eta_while_the_registry_is_empty(store):
    # Retention never unbinds on a ladder failure, so it reports a state; a
    # signature drift between hook and store would read UNAVAILABLE here.
    from carbon.challenge_validator import koth_registry

    assert koth_registry.rebuild_noise(MOTOR.challenge_id) is None
    assert _hook(store) == "RECORDED"
    assert store.served("5Miner", MOTOR, EXAM)["best"]["total"] == 0.62


def test_the_retention_hook_reads_the_koth_registry(store, monkeypatch):
    from carbon.challenge_validator import koth_registry

    asked = []

    def registered(challenge_id, **_):
        asked.append(challenge_id)
        return _noise(0.05)

    monkeypatch.setattr(koth_registry, "rebuild_noise", registered)
    assert _hook(store) == "RECORDED"
    assert asked == [MOTOR.challenge_id]
    assert store.served("5Miner", MOTOR, EXAM)["best"]["total"] == 0.6


def test_an_invalid_registry_records_nothing(store, monkeypatch):
    from carbon.challenge_validator import koth_registry

    def invalid(challenge_id, **_):
        raise koth_registry.RegistryInvalid("koth_registry_invalid")

    monkeypatch.setattr(koth_registry, "rebuild_noise", invalid)
    assert _hook(store).startswith("UNAVAILABLE")
    assert store.served("5Miner", MOTOR, EXAM) == {"best": None, "latest": None}


def test_a_stored_v1_document_that_showed_a_and_d_is_not_served(store):
    """OWNER-FULL-EXAM-BANK-01: the miner sees the total alone. A v1 document is
    dropped, never served, and the miner's next grade starts the v2 ladder."""
    import json

    _record(store, _scored(0.60, 0.30, 0.90))
    v1 = {
        "schema": gf.SCHEMA_V1,
        "exam_version": "motor-exam-1",
        "status": "IMPROVED",
        "total": 0.6,
        "A": 0.3,
        "D": 0.9,
        "gate_names": [],
    }
    raw = json.dumps(v1, sort_keys=True)
    with store.ledger._db() as db:
        db.execute("UPDATE ladder_feedback_v2 SET best=?, latest=?", (raw, raw))
    assert store.served("5Miner", MOTOR, EXAM) == {"best": None, "latest": None}
    fresh = _record(store, _scored(0.61, 0.31, 0.91))
    assert fresh["status"] == "IMPROVED" and "A" not in fresh and "D" not in fresh
    assert set(store.served("5Miner", MOTOR, EXAM)["best"]) == gf.FIELDS
