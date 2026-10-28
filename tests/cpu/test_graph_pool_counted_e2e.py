"""Graph custody -> counted pool grading -> ExamCap -> KOTH filing.

This uses the real Motor 1.5 sealed-pool fixture in plain and validator-copy
delivery modes, real v5 GRAPH custody, source registration, dual producer,
score engine, evidence binding, ExamCap, Ladder and PoolStore orchestration.
Only graph worker originals and repeat/single-call execution are synthetic.
No worker, solver, graph training, network or containment claim is made here.
The registered missing KOTH inputs remain missing: no fixture earns a crown,
LIVE eligibility, official qualification, weights or settlement authority.

The fresh-inference outer regrade runner is covered separately; this test
connects its graph custody output to the actual counted grading core instead
of stubbing that core or manufacturing a private database outcome.
"""

# ruff: noqa: F811 (the imported case fixture is received by tests)
from __future__ import annotations

import base64
import copy
import json
from types import SimpleNamespace

import pytest
from test_physical_dual_pack_end_to_end import IMAGE, _npz, _pair
from test_pool_dual_e2e import MOTOR, VERSION, case  # noqa: F401
from test_public_bundle_model_custody import _json, _sha

from carbon.battery.pool_store import PoolStore, StateError
from carbon.challenge_kit import physical_material
from carbon.challenge_validator import AttemptLedger
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.bank_promotion import BankPromotion
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.development_session import bundle_construction_worker, paired_inference
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.development_session.research_ledger import CampaignLedger
from carbon.level4 import staging
from carbon.reconstruction.worker.model import WorkerImageIdentity
from carbon.registry.model import ChallengeKey
from scripts.dev.score_lab import public_unbound_custody as custody

OWNER = "synthetic-graph-pool-owner"
TASK = "rtsk_" + "4" * 64
CONTRACT = "sha256:" + "c" * 64


def _graph_originals(case, outputs):
    """Original-byte fixture at the graph worker boundary, never a model claim."""
    material = physical_material.bundle_material(MOTOR, VERSION)
    kit = material["construction_kit"]
    document = _json({"schema": "toy-level4-document"})
    envelope = staging.envelope(
        _json({"schema": "toy-level4-manifest", "documents": []}),
        {_sha(document): document},
    )
    recipe = {
        "schema": "carbon.construction-recipe.v1",
        "challenge": kit,
        "source": {"kind": "graph", "submission_digest": envelope["submission"]},
        "procedure": {
            "entrypoint": None,
            "configuration": {},
            "train_use": {},
            "initial_state": None,
        },
        "output": {
            "format": "carbon.numeric-graph.v1",
            "interface_digest": kit["interface_digest"],
        },
    }
    graph = _json({"entry": "main", "graphs": {"main": {"inputs": [], "outputs": []}}})
    recipe_raw = _json(recipe)
    header = {
        "schema": custody.GRAPH_SOURCE_STATE_SCHEMA,
        "recipe_digest": _sha(recipe_raw),
        "submission_digest": envelope["submission"],
        "train_digest": kit["train_digest"],
        "interface_digest": kit["interface_digest"],
        "graph_digest": _sha(graph),
        "allowlist_digest": _sha(material["allowlist_bytes"]),
        "parameter_count": 0,
    }
    header_raw = _json(header)
    state = _npz(
        __header__=("|u1", header_raw, (len(header_raw),)),
        graph=("|u1", graph, (len(graph),)),
    )
    predictions = _json(outputs)
    build = {
        "schema": "carbon.development.graph-build.v1",
        "recipe_digest": _sha(recipe_raw),
        "submission_digest": envelope["submission"],
        "train_digest": kit["train_digest"],
        "state_digest": _sha(state),
        "allowlist_digest": header["allowlist_digest"],
        "framework": "jax",
        "fit": {"synthetic_fixture_only": True},
    }
    inferred = {
        "schema": "carbon.development.bundle-inference.v1",
        "recipe_digest": _sha(recipe_raw),
        "state_digest": _sha(state),
        "inputs_digest": _sha(case["case_bank"]),
        "predictions_digest": _sha(predictions),
    }
    worker = {
        "schema": "carbon.direct-private-attempt.graph.v1",
        "image_id": IMAGE,
        "parent_image_id": IMAGE,
        "inference_image_id": IMAGE,
        "build_operation": "operation-" + "b" * 64,
        "inference_operation": "operation-" + "a" * 64,
        "build_controls_digest": _sha(b"synthetic-build-controls"),
        "inference_controls_digest": _sha(b"synthetic-inference-controls"),
        "state_digest": _sha(state),
        "predictions_digest": _sha(predictions),
        "build_receipt": build,
        "inference_receipt": inferred,
        "predictions_raw_base64": base64.b64encode(predictions).decode("ascii"),
        "submission_digest": envelope["submission"],
    }
    artifacts = {
        "recipe.json": recipe_raw,
        "construction-kit.json": _json(kit),
        "train.npz": material["train"],
        "fixture.npz": material["train"],
        "inputs.npz": case["case_bank"],
        "state.npz": state,
        "predictions.json": predictions,
        "source-envelope.json": _json(envelope),
        "image.json": _json(
            dict.fromkeys(WorkerImageIdentity.__dataclass_fields__, IMAGE)
        ),
        "allowlist.json": material["allowlist_bytes"],
        "build-receipt.json": _json(build),
        "inference-receipt.json": _json(inferred),
        "worker-evidence.json": _json(worker),
        "task-receipt.json": b"synthetic graph worker terminal; never network evidence",
    }
    return material, recipe, artifacts, worker


def _setup(case, tmp_path, monkeypatch, *, candidate_failure=False):
    outputs = copy.deepcopy(case["outputs"])
    if candidate_failure:
        row = next(
            i for i, r in enumerate(case["rows"]) if r["cohort"] == "pool_design"
        )
        outputs[row] = [-1.0] * len(outputs[row])
    material, recipe, artifacts, worker = _graph_originals(case, outputs)
    base, entries = tmp_path / "graph-artifacts", tmp_path / "graph-entries"
    base.mkdir(mode=0o700)
    entries.mkdir(mode=0o700)
    retained = retention._retain_graph_artifacts(
        artifacts, TASK, artifact_directory=base, entry_directory=entries
    )
    assert retained["official_eligible"] is False
    assert retained["score_state"] == "NOT_COMPUTED"
    retained["evaluation_pack_digest"] = case["snapshot"].manifest_digest
    ledger_root = tmp_path / "receiver-ledger"
    ledger_root.mkdir(mode=0o700)
    ledger = AttemptLedger(ledger_root / "attempts.sqlite3")
    # Use the same API as receiver admission, rather than insert private SQL rows.
    ledger.record(
        SimpleNamespace(
            hotkey=OWNER,
            receipt={
                "sequence": 1,
                "digest": "synthetic-signed-receipt",
                "block": 360 * 7,
            },
            contract_digest=CONTRACT,
        ),
        kind="OUTCOME",
        submission_id=TASK,
    )
    ledger.record_recipe_task_intent(CONTRACT, TASK, OWNER, _sha(b"synthetic-request"))
    campaign = CampaignLedger(tmp_path / "worker-ledger")
    provider = SimpleNamespace(
        ledger=campaign,
        inference_image=WorkerImageIdentity(*([IMAGE] * 8)),
        inference_accelerator=None,
    )
    adapter = object.__new__(LeanRecipeAdapter)
    adapter.challenge_id, adapter.challenge_version = MOTOR, VERSION
    adapter.contract_digest, adapter.ledger = CONTRACT, ledger
    adapter.copy_hotkey = case["copy_hotkey"]
    adapter.speed_sample_key = bytes(range(32))  # synthetic test-only sampling key
    adapter.owner = lambda _task: OWNER
    adapter._provider = lambda _owner: provider
    adapter.discovery = SimpleNamespace(
        info=SimpleNamespace(challenge_key=ChallengeKey(MOTOR, VERSION)),
        _material=material,
        evaluation_pack_snapshot=case["snapshot"],
        evaluation_pack_digest=case["snapshot"].manifest_digest,
        evaluation_pack_public_root=case["root"],
        evaluation_pack_private_root=case["root"],
        evaluation_pack_sealed=False,  # fixture did not arrive through answer-key custody
        graph_adapter_for=lambda _key: "electric-motor-magnetics-public-jax-graph-v2",
    )
    calls = []

    def repeat_worker(_ledger, **kwargs):
        assert kwargs["expected_state_digest"] == _sha(artifacts["state.npz"])
        assert kwargs["inputs"].shape == case["bank"]["inputs"].shape
        calls.append("pair")
        return SimpleNamespace(
            evidence=json.loads(
                _pair(worker["inference_receipt"], [outputs, outputs])
            )
        )

    def single_worker(_ledger, **kwargs):
        assert kwargs["state_digest"] == _sha(artifacts["state.npz"])
        assert kwargs["inputs"].shape == case["bank"]["inputs"].shape
        indices = kwargs["single_call"]["indices"]
        calls.append("single")
        return SimpleNamespace(
            predictions=[outputs[i] for i in indices],
            receipt={
                "single_call": {
                    "call_s": [0.02] * len(indices),
                    "warmup_digest": _sha(b"public-warmup"),
                }
            },
            worker_operation="operation-" + "9" * 64,
        )

    monkeypatch.setattr(paired_inference, "infer_frozen_pair", repeat_worker)
    monkeypatch.setattr(bundle_construction_worker, "_infer_state", single_worker)
    return SimpleNamespace(
        adapter=adapter,
        retained=retained,
        artifacts=artifacts,
        worker=worker,
        calls=calls,
        regrade=retention._Regrade(
            OWNER,
            ConstructionRecipe.from_dict(recipe),
            TASK,
            retained["entry_id"],
            counted=True,
        ),
        store=PoolStore(tmp_path / "pool.sqlite", clock=lambda: 123.0),
    )


def _grade(fixture):
    return retention._retain_selected_pack_evaluation(
        fixture.adapter,
        TASK,
        fixture.retained,
        fixture.artifacts,
        fixture.worker,
        fixture.regrade,
        pool_store=fixture.store,
    )


def _cap_rows(fixture):
    with fixture.adapter.ledger._db() as db:
        return db.execute(
            "SELECT submission_id, kind, state, status, hotkey, epoch FROM exam_graded ORDER BY id"
        ).fetchall()


def test_graph_custody_pool_grade_is_counted_and_filed_without_a_crown(
    case, tmp_path, monkeypatch
):
    fixture = _setup(case, tmp_path, monkeypatch)
    result = _grade(fixture)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", result
    assert fixture.calls == ["pair", "single"]
    assert _cap_rows(fixture) == [
        (TASK, "GRADED", "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE", OWNER, 7)
    ]
    assert result["ladder_feedback_state"] == "RECORDED"
    assert result["koth_comparison"]["outcome"] == "UNAVAILABLE"
    assert fixture.store.incumbent() is None
    # A real v4 sidecar, filed under the origin submission, not a manufactured king row.
    key = result["koth_comparison"]["evaluation_key"]
    pin = json.loads(result["private_evaluation_path"].read_bytes())[
        "source_receipt_sha256"
    ]
    pair = BankPromotion(
        fixture.store, registered_source_receipt_sha256=pin
    ).private_pair(TASK, key)
    assert pair["candidate"]["submission_id"] == TASK
    assert fixture.store.submission(TASK)["state"] == "RECONSTRUCTED"
    assert result["official_eligible"] is False
    # Retry reads create-only evidence and cannot run another worker or consume another slot.
    again = _grade(fixture)
    assert again["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", again
    assert fixture.calls == ["pair", "single"]
    assert len(_cap_rows(fixture)) == 1


def test_graph_pool_physics_failure_counts_as_a_candidate_result(
    case, tmp_path, monkeypatch
):
    fixture = _setup(case, tmp_path, monkeypatch, candidate_failure=True)
    result = _grade(fixture)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", result
    assert _cap_rows(fixture)[0][2:4] == ("COUNTED", "MANDATORY_GATE_FAILED")
    assert fixture.store.incumbent() is None
    assert "evaluation_key" in result["koth_comparison"]


def test_graph_original_mismatch_is_unavailable_and_releases_the_slot(
    case, tmp_path, monkeypatch
):
    fixture = _setup(case, tmp_path, monkeypatch)
    worker = json.loads(fixture.artifacts["worker-evidence.json"])
    worker["predictions_digest"] = _sha(b"different worker original")
    fixture.artifacts["worker-evidence.json"] = _json(worker)
    result = _grade(fixture)
    assert result["private_evaluation_state"] == "UNAVAILABLE"
    assert result["private_evaluation_reason"]
    assert _cap_rows(fixture)[0][2] == "RELEASED"
    assert fixture.store.incumbent() is None
    with pytest.raises(StateError, match="unknown_submission"):
        fixture.store.submission(TASK)
