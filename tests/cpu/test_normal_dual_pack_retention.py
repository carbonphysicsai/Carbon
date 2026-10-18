"""Normal private routing with a distinct inert Challenge; no model verdict."""

from __future__ import annotations

import base64
import json
import math
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from test_private_dual_evaluation_evidence import inert_dual_graph_case

from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.direct_intake import DirectRecipeIntake
from carbon.challenge_validator.evaluation_pack import SCHEMA, prepare_pack
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.registry.model import ChallengeKey
from carbon.research import DirectTaskStateV3
from carbon.scoring import bundle_benchmark_core, dual_score
from carbon.scoring import private_evaluation_source as source
from carbon.scoring.engine import ScoreEngine


def _raw(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _line(value):
    return _raw(value) + b"\n"


def _fixture(tmp_path, monkeypatch, *, gate_minimum=0.0):
    case = inert_dual_graph_case(tmp_path / "original-case")
    case["references"][0]["outputs"] = [0.5]
    public = tmp_path / "public"
    private = tmp_path / "private"
    draft = tmp_path / "draft"
    for path in (public, private, draft):
        path.mkdir(mode=0o700)
    producer = retention._sha(b"inert-normal-routing-producer-only")
    definitions = {
        "accuracy_definition": {
            "scope": "INERT_TEST_ONLY",
            "producer_digest": producer,
            "metric": "fixture_fidelity",
        },
        "important_limit_definition": {
            "scope": "INERT_TEST_ONLY",
            "minimum_fixture_output": gate_minimum,
        },
        "design_objective": {
            "scope": "INERT_TEST_ONLY",
            "objective": "select the sole finite reference action",
        },
    }
    public_bytes = {
        "construction_kit": case["originals"]["stage/construction-kit.json"],
        "interface": b"inert-dual-fixture-interface",
        "train": case["originals"]["stage/train.npz"],
        "physics_contract": _raw(case["job"]["physics_contract"]),
        **{name: _raw(value) for name, value in definitions.items()},
    }
    for name, body in public_bytes.items():
        (public / (name + ".bin")).write_bytes(body)
    basis = {
        "schema": source.DUAL_MEASUREMENT_CONTRACT_SCHEMA,
        "producer_digest": producer,
        **{
            name + "_sha256": retention._sha(public_bytes[name]) for name in definitions
        },
    }
    components = {
        name: {
            "components": [
                {
                    "metric": metric,
                    "unit": "1",
                    "transform": "unit_benefit",
                    "scale": None,
                    "weight": 1.0,
                }
            ],
            "minimum": None,
        }
        for name, metric in (("A", "fixture_fidelity"), ("D", "fixture_pick"))
    }
    pack = dual_score.register_pack(
        {
            "schema": dual_score.PACK_SCHEMA,
            "scope": case["registration"]["scope"],
            "challenge": case["entry"]["challenge"],
            "physics_contract_digest": case["result"]["physics_contract"][
                "definition_digest"
            ],
            "measurement_contract_digest": retention._sha(_line(basis)),
            "hard_gates": ["toy_gate"],
            "legs": components,
            "value_weight": 0.5,
            "combination": "weighted_arithmetic_mean",
            "decision_policy": {
                "VERIFIED_FEASIBLE": {"eligible": True, "maximum_D": 1.0},
                "MISSED_OPPORTUNITY": {"eligible": False, "maximum_D": 0.0},
                "NONE_FEASIBLE": {"eligible": False, "maximum_D": 0.0},
            },
        }
    )
    registration = {
        "schema": "carbon.challenge-evaluation-source-registration.v1",
        "evaluation_version": "inert-normal-routing-v1",
        "trusted_job": case["job"],
        "benchmark_registration": case["registration"],
    }
    private_bytes = {
        "case_bank": case["ordered_query_bytes"][0],
        "reference_rows": _raw(case["references"]),
        "solver_evidence": _raw(case["registration"]["reference"]),
        "score_pack": _raw(pack),
        "source_registration": _raw(registration),
    }
    for name, body in private_bytes.items():
        (private / (name + ".bin")).write_bytes(body)
    manifest = {
        "schema": SCHEMA,
        "challenge": {
            "id": case["entry"]["challenge"],
            "version": case["entry"]["challenge_version"],
        },
        "pack_version": "inert-normal-routing-only",
        "public": {name: {"path": name + ".bin"} for name in public_bytes},
        "private": {name: {"path": name + ".bin"} for name in private_bytes},
    }
    (draft / "pack.json").write_bytes(_raw(manifest))
    sealed = prepare_pack(
        draft,
        "pack.json",
        public_root=public,
        private_root=private,
        challenge_id=case["entry"]["challenge"],
        challenge_version=case["entry"]["challenge_version"],
    )
    # The normal path consumes the sealed snapshot, never the mutable draft.
    selected = sealed.snapshot
    task_id = "rtsk_" + "a" * 64
    db_path = tmp_path / "campaign.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE campaign (id INTEGER PRIMARY KEY, manifest TEXT)")
        db.execute(
            "INSERT INTO campaign VALUES (1, ?)",
            (
                json.dumps(
                    {
                        "campaign_id": "inert-normal-campaign",
                        "receiver_binding": {
                            "evaluation_pack_digest": selected.manifest_digest
                        },
                    }
                ),
            ),
        )

    class Ledger:
        @contextmanager
        def db(self):
            with sqlite3.connect(db_path) as db:
                yield db

    key = ChallengeKey(case["entry"]["challenge"], case["entry"]["challenge_version"])
    discovery = SimpleNamespace(
        info=SimpleNamespace(challenge_key=key),
        evaluation_pack_snapshot=selected,
        evaluation_pack_digest=selected.manifest_digest,
        evaluation_pack_public_root=public,
        evaluation_pack_private_root=private,
        _checked=lambda _key: (None, None),
        _material={},
    )
    worker = json.loads(case["originals"]["stage/worker-evidence.json"])
    task = SimpleNamespace(
        state=DirectTaskStateV3.SUCCEEDED,
        terminal_receipt=SimpleNamespace(
            state_digest=case["entry"]["state_digest"],
            predictions_digest=case["entry"]["prediction_digest"],
        ),
    )
    provider = SimpleNamespace(
        evaluation_pack_digest=selected.manifest_digest,
        ledger=Ledger(),
        _requests={
            task_id: SimpleNamespace(
                recipe=json.loads(case["originals"]["stage/recipe.json"])
            )
        },
        get_research_result=lambda _request: SimpleNamespace(task=task),
        private_attempt=lambda _task_id: worker,
    )
    adapter = object.__new__(LeanRecipeAdapter)
    adapter.discovery = discovery
    adapter.challenge_id, adapter.challenge_version = key.challenge_id, key.version
    monkeypatch.setattr(
        LeanRecipeAdapter, "owner", lambda _self, _task: "fixture-owner"
    )
    monkeypatch.setattr(LeanRecipeAdapter, "_provider", lambda _self, _owner: provider)
    roles = {
        "recipe.json": "stage/recipe.json",
        "construction-kit.json": "stage/construction-kit.json",
        "train.npz": "stage/train.npz",
        "fixture.npz": "stage/example.npz",
        "inputs.npz": "infer/inputs.npz",
        "state.npz": "build/output/state.npz",
        "predictions.json": "infer/output/predictions.json",
        "source-envelope.json": "stage/source-envelope.json",
        "image.json": "stage/image.json",
        "allowlist.json": "stage/allowlist.json",
        "build-receipt.json": "build/output/receipt.json",
        "inference-receipt.json": "infer/output/receipt.json",
        "worker-evidence.json": "stage/worker-evidence.json",
    }
    artifacts = {name: case["originals"][path] for name, path in roles.items()}
    artifacts["task-receipt.json"] = (
        b"inert fixture terminal receipt; never network evidence"
    )
    monkeypatch.setattr(retention, "_collect_graph_artifacts", lambda *_args: artifacts)
    intake = object.__new__(DirectRecipeIntake)
    intake.adapter = adapter
    artifact_root, entries = tmp_path / "bank-artifacts", tmp_path / "bank-entries"
    artifact_root.mkdir(mode=0o700)
    entries.mkdir(mode=0o700)

    def retain():
        return intake.retain_result(
            task_id, artifact_directory=artifact_root, entry_directory=entries
        )

    return SimpleNamespace(
        case=case,
        selected=selected,
        public=public,
        private=private,
        pack=pack,
        producer=producer,
        retain=retain,
        adapter=adapter,
        artifacts=artifacts,
        task_id=task_id,
        produced=[],
        artifact_root=artifact_root,
    )


def _producer(fixture, *, wrong_challenge=False):
    def produce(**arguments):
        assert arguments["entry"]["challenge"] == "inert-dual-software-fixture"
        originals = arguments["graph_originals"]
        worker = json.loads(originals["worker_evidence_raw"])
        predictions = json.loads(base64.b64decode(worker["predictions_raw_base64"]))
        value = predictions[0][0][0][0]
        limits = fixture.selected.read_json_role(
            fixture.public, "public", "important_limit_definition", max_bytes=65536
        )
        passed = math.isfinite(value) and value >= limits["minimum_fixture_output"]
        inference = {
            "recipe_digest": arguments["entry"]["recipe_digest"],
            "state_digest": arguments["entry"]["state_digest"],
            "predictions_digest": worker["predictions_digest"],
            "predictions": predictions,
            "worker_operation": worker["inference_operation"],
            "receipt": worker["inference_receipt"],
            **originals,
        }
        measured = bundle_benchmark_core.measurement_from_saved_inference(
            arguments["entry"],
            arguments["registration"],
            inference,
            gates={"toy_gate": passed},
        )
        target = arguments["references"][0]["outputs"][0]
        evidence = json.loads(arguments["evaluation_source_receipt_raw"])
        benchmark = {
            "schema": dual_score.INPUT_SCHEMA,
            "scope": fixture.pack["scope"],
            "challenge": (
                "wrong-fixture" if wrong_challenge else arguments["entry"]["challenge"]
            ),
            "physics_contract_digest": fixture.pack["physics_contract_digest"],
            "measurement_contract_digest": fixture.pack["measurement_contract_digest"],
            "population_role": "P",
            "common_mask_digest": retention._sha(_line(evidence["cases"])),
            "models": [
                {
                    "artifact_digest": arguments["entry"]["entry_id"],
                    "gates": {"toy_gate": "PASS" if passed else "FAIL"},
                    "measurements": {
                        "fixture_fidelity": {
                            "status": "RESOLVED",
                            "value": 1 / (1 + abs(value - target)),
                            "unit": "1",
                        },
                        "fixture_pick": {
                            "status": "RESOLVED",
                            "value": float(math.isfinite(target) and target >= 0),
                            "unit": "1",
                        },
                    },
                    "decision_outcome": "VERIFIED_FEASIBLE",
                }
            ],
        }
        fixture.produced.append(benchmark)
        return measured, benchmark, fixture.producer

    return produce


@pytest.mark.parametrize(
    "minimum, expected",
    [(0.0, "SCORED_DEVELOPMENT_CANDIDATE"), (1.0, "MANDATORY_GATE_FAILED")],
)
def test_normal_retention_routes_trusted_fixture_to_same_core(
    tmp_path, monkeypatch, minimum, expected
):
    fixture = _fixture(tmp_path, monkeypatch, gate_minimum=minimum)
    monkeypatch.setattr(source, "produce_dual_benchmark_input", _producer(fixture))
    result = fixture.retain()
    assert result["status"] == "CREATED"
    assert (
        result["score_state"] == "NOT_COMPUTED" and result["official_eligible"] is False
    )
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY"
    binding = json.loads(result["private_evaluation_path"].read_bytes())
    assert binding["scoring"] == ScoreEngine.score_dual_benchmark_v4(
        fixture.produced[-1], fixture.pack
    )
    assert binding["model_p"]["score_status"] == expected
    if minimum:
        assert binding["model_p"]["total_score"] is None
    assert binding["official_score"] is False and binding["official_eligible"] is False
    assert result["private_evaluation_path"].parent != result["artifact_path"]
    original_entry = result["entry_path"].read_bytes()
    assert fixture.retain()["status"] == "ALREADY_PRESENT_IDENTICAL"
    assert result["entry_path"].read_bytes() == original_entry


def test_missing_producer_does_not_invalidate_retained_model(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, monkeypatch)
    result = fixture.retain()
    assert result["status"] == "CREATED" and result["score_state"] == "NOT_COMPUTED"
    assert result["private_evaluation_state"] == "UNAVAILABLE"
    assert (
        result["private_evaluation_reason"] == "dual_measurement_producer_unavailable"
    )


@pytest.mark.parametrize("tamper", ["reference", "wrong_challenge"])
def test_normal_retention_refuses_tampered_or_cross_challenge_evaluation(
    tmp_path, monkeypatch, tamper
):
    fixture = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        source,
        "produce_dual_benchmark_input",
        _producer(fixture, wrong_challenge=tamper == "wrong_challenge"),
    )
    if tamper == "reference":
        (fixture.private / "reference_rows.bin").write_bytes(b"[]")
    result = fixture.retain()
    assert result["status"] == "CREATED" and result["official_eligible"] is False
    assert result["private_evaluation_state"] == "UNAVAILABLE"
    assert "private_evaluation_path" not in result


def test_unverified_bundle_dual_evidence_stays_unavailable(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, monkeypatch)
    result = {
        "evaluation_pack_digest": fixture.selected.manifest_digest,
        "score_state": "NOT_COMPUTED",
        "official_eligible": False,
    }
    actual = retention._retain_selected_pack_evaluation(
        fixture.adapter, fixture.task_id, result, {}
    )
    assert actual["private_evaluation_state"] == "UNAVAILABLE"
    assert actual["private_evaluation_reason"] == "dual_model_originals_unavailable"
    assert (
        actual["score_state"] == "NOT_COMPUTED" and actual["official_eligible"] is False
    )


def test_legacy_pack_does_not_enter_dual_dispatch():
    snapshot = SimpleNamespace(
        read_json_role=lambda *_args, **_kwargs: {
            "schema": "carbon.scoring.solver-benchmark-pack.v3"
        }
    )
    adapter = SimpleNamespace(
        discovery=SimpleNamespace(
            evaluation_pack_snapshot=snapshot, evaluation_pack_private_root=None
        )
    )
    retained = {
        "evaluation_pack_digest": "sha256:" + "c" * 64,
        "score_state": "NOT_COMPUTED",
    }
    assert (
        retention._retain_selected_pack_evaluation(adapter, "unused", retained, {})
        is retained
    )
