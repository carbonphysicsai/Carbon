"""Graph custody -> counted pool grading -> ExamCap -> KOTH filing.

This uses the real Motor 1.5 sealed-pool fixture in plain and validator-copy
delivery modes, real v5 GRAPH custody, source registration, dual producer,
score engine, evidence binding, ExamCap, Ladder and PoolStore orchestration.
Only graph worker originals and inference/repeat/single-call execution are synthetic.
No worker, solver, graph training, network or containment claim is made here.
The registered missing KOTH inputs remain missing: no fixture earns a crown,
LIVE eligibility, official qualification, weights or settlement authority.

The counted entrypoint and source-free regrade orchestration run as well, with
synthetic worker outputs. Scoring, custody and database state transitions are
never stubbed or manufactured.
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
from carbon.development_session.research_ledger import VERSION as CAMPAIGN_SCHEMA
from carbon.development_session.research_ledger import CampaignLedger
from carbon.level4 import staging
from carbon.reconstruction.worker.model import WorkerImageIdentity
from carbon.registry.model import ChallengeKey
from scripts.dev.score_lab import public_unbound_custody as custody

OWNER = "synthetic-graph-pool-owner"
TASK = "rtsk_" + "4" * 64
CONTRACT = "sha256:" + "c" * 64


def _graph_originals(case, outputs, *, ensemble=False):
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
    fit = {"synthetic_fixture_only": True}
    if ensemble:
        from test_graph_state_custody import producer_fixture

        producer = producer_fixture(key=(MOTOR, VERSION))
        material = producer["material"]
        recipe = producer["recipe"].to_dict()
        recipe_raw = producer["recipe"].canonical_bytes
        envelope, state, fit = producer["source"], producer["state"], producer["fit"]
    predictions = _json(outputs)
    build = {
        "schema": "carbon.development.graph-build.v1",
        "recipe_digest": _sha(recipe_raw),
        "submission_digest": envelope["submission"],
        "train_digest": kit["train_digest"],
        "state_digest": _sha(state),
        "allowlist_digest": header["allowlist_digest"],
        "framework": "jax",
        "fit": fit,
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
    if ensemble:
        timed = {
            **inferred,
            "schema": "carbon.development.bundle-inference.v2",
            "measurement": {
                "scope": "COLD_SINGLE_WORKER_QUERY_INCLUDES_GRAPH_LOAD_AND_JAX_COMPILE",
                "timing_s": dict.fromkeys(
                    ("preprocess", "inference", "postprocess", "export"), 0.1
                ),
                "input_shape": list(case["bank"]["inputs"].shape),
                "input_dtype": str(case["bank"]["inputs"].dtype),
                "output_shape": [len(outputs), len(outputs[0])],
                "output_dtype": "float64",
            },
        }
        worker.update(
            build_device="GPU",  # synthetic declaration; never execution evidence
            build_image_id=_sha(b"synthetic-separate-gpu-build-image"),
            timed_operation="operation-" + "c" * 64,
            timed_controls_digest=_sha(b"synthetic-timed-controls"),
            timed_receipt=timed,
        )
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
        **({"timed-query-receipt.json": _json(timed)} if ensemble else {}),
    }
    return material, recipe, artifacts, worker


def _setup(case, tmp_path, monkeypatch, *, candidate_failure=False, ensemble=False):
    outputs = copy.deepcopy(case["outputs"])
    if candidate_failure:
        row = next(
            i for i, r in enumerate(case["rows"]) if r["cohort"] == "pool_design"
        )
        outputs[row] = [-1.0] * len(outputs[row])
    material, recipe, artifacts, worker = _graph_originals(
        case, outputs, ensemble=ensemble
    )
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
    campaign.freeze(
        {
            "schema": CAMPAIGN_SCHEMA,
            "ceilings": {},
            "elapsed_seconds": None,
            "campaign_id": "synthetic-graph-pool-counted",
            "implementation": "fixture",
            "objective": "fixture",
            "sampling": "fixture",
            "control": "none",
            "selection": "none",
            "replica_policy": "fixture",
            "provider": "none",
            "owner": OWNER,
            "receiver_binding": {
                "evaluation_pack_digest": case["snapshot"].manifest_digest
            },
        }
    )
    provider = SimpleNamespace(
        ledger=campaign,
        inference_image=WorkerImageIdentity(*([IMAGE] * 8)),
        inference_accelerator=None,
        evaluation_pack_digest=case["snapshot"].manifest_digest,
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
        _checked=lambda _key: (None, None),
    )
    calls = []

    def repeat_worker(_ledger, **kwargs):
        assert kwargs["expected_state_digest"] == _sha(artifacts["state.npz"])
        assert kwargs["inputs"].shape == case["bank"]["inputs"].shape
        calls.append("pair")
        return SimpleNamespace(
            evidence=json.loads(_pair(worker["inference_receipt"], [outputs, outputs]))
        )

    def single_worker(_ledger, **kwargs):
        assert kwargs["state_digest"] == _sha(artifacts["state.npz"])
        assert kwargs["inputs"].shape == case["bank"]["inputs"].shape
        if "single_call" not in kwargs:
            # A fresh source-free bank inference. The real caller snapshots and
            # authenticates these originals, and regenerates graph evidence.
            calls.append("bank")
            operation = "operation-" + "c" * 64
            snapshot = campaign.root / operation / "snapshot"
            snapshot.mkdir(parents=True)
            raw = artifacts["predictions.json"]
            receipt = {
                **worker["inference_receipt"],
                "inputs_digest": _sha(
                    bundle_construction_worker._tensors(inputs=kwargs["inputs"])
                ),
            }
            (snapshot / "predictions.json").write_bytes(raw)
            (snapshot / "receipt.json").write_bytes(_json(receipt))
            return SimpleNamespace(
                receipt=receipt,
                predictions=outputs,
                predictions_digest=_sha(raw),
                worker_operation=operation,
            )
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
        base=base,
        entries=entries,
        regrade=retention._Regrade(
            OWNER,
            ConstructionRecipe.from_dict(recipe),
            TASK,
            retained["entry_id"],
            counted=True,
        ),
        store=PoolStore(tmp_path / "pool.sqlite", clock=lambda: 123.0),
    )


def _grade(fixture, *, counted=False):
    if counted:
        return retention._counted_bank_grade(
            fixture.adapter,
            TASK,
            fixture.retained,
            artifact_directory=fixture.base,
            entry_directory=fixture.entries,
            pool_store=fixture.store,
            runner=object(),  # existing fixture runner hook; never a live worker
        )
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
    assert "lineage.json" not in fixture.artifacts
    result = _grade(fixture, counted=True)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", result
    assert fixture.calls == ["bank", "pair", "single"]
    assert result["entry_id"] == fixture.retained["entry_id"]
    assert result["bank_grade_entry_id"] != result["entry_id"]
    regrade_roots = [
        p
        for p in fixture.base.iterdir()
        if p.is_dir() and p.name != TASK and not p.name.endswith(".evaluation")
    ]
    assert len(regrade_roots) == 1
    assert not (regrade_roots[0] / "lineage.json").exists()
    evaluation = fixture.base / (regrade_roots[0].name + ".evaluation")
    provenance = json.loads((evaluation / "regrade-provenance.json").read_bytes())
    assert provenance["kind"] == "COUNTED_GRADE"
    assert provenance["origin_task_id"] == TASK
    assert _cap_rows(fixture) == [
        (TASK, "GRADED", "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE", OWNER, 7)
    ]
    assert result["ladder_feedback_state"] == "RECORDED"
    assert result["koth_comparison"]["outcome"] == "UNAVAILABLE"
    assert fixture.store.incumbent() is None
    # A real v4 sidecar, filed under the origin submission, not a manufactured king row.
    key = result["koth_comparison"]["evaluation_key"]
    pin = json.loads((evaluation / "private-evaluation-binding.json").read_bytes())[
        "source_receipt_sha256"
    ]
    pair = BankPromotion(
        fixture.store, registered_source_receipt_sha256=pin
    ).private_pair(TASK, key)
    assert pair["candidate"]["submission_id"] == TASK
    assert fixture.store.submission(TASK)["state"] == "RECONSTRUCTED"
    assert result["official_eligible"] is False
    # Retry reads create-only evidence and cannot run another worker or consume another slot.
    again = _grade(fixture, counted=True)
    assert again["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", again
    assert fixture.calls == ["bank", "pair", "single"]
    assert len(_cap_rows(fixture)) == 1


def test_graph_pool_physics_failure_counts_as_a_candidate_result(
    case, tmp_path, monkeypatch
):
    fixture = _setup(case, tmp_path, monkeypatch, candidate_failure=True)
    result = _grade(fixture, counted=True)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", result
    assert _cap_rows(fixture)[0][2:4] == ("COUNTED", "MANDATORY_GATE_FAILED")
    assert fixture.store.incumbent() is None
    assert "evaluation_key" in result["koth_comparison"]


def test_actual_ensemble_freeze_reaches_counted_grade_with_separate_build_identity(
    case, tmp_path, monkeypatch
):
    fixture = _setup(case, tmp_path, monkeypatch, ensemble=True)
    manifest = json.loads((fixture.base / (TASK + ".roles.json")).read_bytes())
    assert manifest["source_schema"] == custody.GRAPH_ENSEMBLE_STATE_SCHEMA
    saved = json.loads(fixture.retained["entry_path"].read_bytes())
    assert saved["source_kind"] == "graph"
    assert saved["source_schema"] == custody.GRAPH_ENSEMBLE_STATE_SCHEMA
    assert fixture.worker["build_image_id"] != fixture.worker["inference_image_id"]
    original_state = fixture.artifacts["state.npz"]
    result = _grade(fixture, counted=True)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", result
    assert fixture.calls == ["bank", "pair", "single"]
    assert _cap_rows(fixture) == [
        (TASK, "GRADED", "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE", OWNER, 7)
    ]
    assert fixture.artifacts["state.npz"] == original_state
    assert (
        fixture.retained["artifact_path"] / "state.npz"
    ).read_bytes() == original_state
    assert result["koth_comparison"]["outcome"] == "UNAVAILABLE"
    assert fixture.store.incumbent() is None
    assert result["official_eligible"] is False
    regrades = [
        path
        for path in fixture.base.iterdir()
        if path.is_dir() and path.name != TASK and not path.name.endswith(".evaluation")
    ]
    assert len(regrades) == 1
    bank_worker = json.loads((regrades[0] / "worker-evidence.json").read_bytes())
    assert not {
        "timed_operation",
        "timed_receipt",
        "timed_controls_digest",
    } & bank_worker.keys()
    assert bank_worker["build_image_id"] == fixture.worker["build_image_id"]
    assert bank_worker["build_receipt"] == fixture.worker["build_receipt"]
    origin = json.loads(
        (fixture.retained["artifact_path"] / "worker-evidence.json").read_bytes()
    )
    assert origin["timed_controls_digest"] == fixture.worker["timed_controls_digest"]


@pytest.mark.parametrize(
    "mutation",
    [
        "fit_members",
        "fit_steps",
        "fit_overflow",
        "missing_gpu_image",
        "unknown_device",
        "wrong_inference_image",
        "bad_timed_controls",
    ],
)
def test_actual_ensemble_receipt_contract_refuses_malformed_declarations(
    case, tmp_path, mutation
):
    _material, _recipe, artifacts, worker = _graph_originals(
        case, copy.deepcopy(case["outputs"]), ensemble=True
    )
    if mutation.startswith("fit_"):
        fit = worker["build_receipt"]["fit"]
        if mutation == "fit_members":
            fit["members"] += 1
        elif mutation == "fit_steps":
            fit["steps"] = ["1", "1"]
        else:
            fit["member_losses"][0] = 10**400
        artifacts["build-receipt.json"] = _json(worker["build_receipt"])
    elif mutation == "missing_gpu_image":
        del worker["build_image_id"]
    elif mutation == "unknown_device":
        worker["build_device"] = "unknown"
    elif mutation == "wrong_inference_image":
        worker["inference_image_id"] = worker["build_image_id"]
    else:
        worker["timed_controls_digest"] = "unbound-controls"
    artifacts["worker-evidence.json"] = _json(worker)
    base, entries = tmp_path / "artifacts", tmp_path / "entries"
    base.mkdir(mode=0o700)
    entries.mkdir(mode=0o700)
    with pytest.raises(
        retention.RetentionUnavailable, match="operator_bank_custody_unavailable"
    ):
        retention._retain_graph_artifacts(
            artifacts, TASK, artifact_directory=base, entry_directory=entries
        )
    assert list(entries.iterdir()) == []


@pytest.mark.parametrize("mode", ["pool", "real_timed", "fixture_timed"])
def test_regrade_controls_name_only_the_new_timed_operation(mode, monkeypatch):
    from carbon.development_session import (
        direct_graph_construction_worker as graph_worker,
    )

    # Synthetic control-helper wiring only; no private worker or grade runs.
    origin = {
        "timed_operation": "operation-" + "0" * 64,
        "timed_receipt": {"synthetic": "origin timed query"},
        "timed_controls_digest": _sha(b"origin timed controls"),
        "build_device": "GPU",
        "build_image_id": _sha(b"origin build image"),
        "build_receipt": {"synthetic": "origin build receipt"},
    }
    graded = SimpleNamespace(
        worker_operation="operation-" + "1" * 64,
        predictions_digest=_sha(b"new synthetic predictions"),
    )
    timed = SimpleNamespace(worker_operation="operation-" + "2" * 64)
    calls = []
    ledger = object()

    def controls(observed_ledger, **kwargs):
        assert observed_ledger is ledger
        assert kwargs["owner"] == OWNER
        assert kwargs["provenance"] == graph_worker.INFERENCE_PROVENANCE
        calls.append((kwargs["identity"], kwargs["operation"]))
        return _sha(kwargs["operation"].encode())

    monkeypatch.setattr(
        bundle_construction_worker, "_private_controls_digest", controls
    )
    evidence = json.loads(
        retention._graph_regrade_worker_evidence(
            _json(origin),
            provider=SimpleNamespace(ledger=ledger),
            owner=OWNER,
            identity="new-graded-identity",
            runner=object() if mode == "fixture_timed" else None,
            graded=graded,
            receipt_raw=_json({"synthetic": "new graded receipt"}),
            predictions=b"new synthetic predictions",
            timed_result=None if mode == "pool" else timed,
            timed_raw=None if mode == "pool" else _json({"synthetic": "new timed receipt"}),
            timed_identity="new-timed-identity",
        )
    )
    assert evidence["build_image_id"] == origin["build_image_id"]
    assert evidence["build_receipt"] == origin["build_receipt"]
    if mode == "pool":
        assert not {
            "timed_operation",
            "timed_receipt",
            "timed_controls_digest",
        } & evidence.keys()
        assert calls == [("new-graded-identity", graded.worker_operation)]
    else:
        assert evidence["timed_operation"] == timed.worker_operation
        if mode == "real_timed":
            assert evidence["timed_controls_digest"] == _sha(
                timed.worker_operation.encode()
            )
            assert evidence["timed_controls_digest"] != origin["timed_controls_digest"]
            assert calls == [
                ("new-graded-identity", graded.worker_operation),
                ("new-timed-identity", timed.worker_operation),
            ]
        else:
            assert "timed_controls_digest" not in evidence
            assert calls == []


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
