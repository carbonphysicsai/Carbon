"""Motor's dual path end to end, from committed sources to a v4 binding.

DEVELOPMENT only, exposed development bank. The pack is Data Collection's
``physical_pack`` with this producer's documents; the model is a retained
bundle in the shape retention keeps for a JAX export under the per-case judge:
the graded per-case receipt (v1, role ``inference_receipt``) and a separate
batched cold timed query (v2, ``timed-query-receipt.json``, an original file,
not a role) that alone carries timing and shapes. The predictions are the
learned-krr-v1 baseline rebuilt from public TRAIN, so the graded legs must
equal the recorded baseline legs. Platform-shaped pair records are fixture
envelopes around those same predictions; no worker or solver runs here.
"""

from __future__ import annotations

import json
from copy import deepcopy

import pytest
from test_inference_pair_evidence import encode, fixture, original
from test_public_bundle_model_custody import _json, _npz, _sha

from carbon.challenge_kit import physical_pack, physical_public_train
from carbon.challenge_validator.evaluation_pack import parse_pack, prepare_pack
from carbon.motor import recipes
from carbon.motor.challenge import PublicMaterial
from carbon.scoring import bundle_benchmark_core as bundle
from carbon.scoring import motor_dual_pack as pack
from carbon.scoring import private_evaluation_evidence as evidence
from carbon.scoring import private_evaluation_source as source
from carbon.scoring.engine import ScoreEngine
from scripts.dev.score_lab import public_unbound_custody as custody
from scripts.dev.score_lab import public_unbound_entry as unbound_entry

BASELINE_A = 0.28108361796711556
BASELINE_D = 0.3419193228890681
GRADED_OPERATION = "operation-" + "a" * 64
IMAGE = _sha(b"fixture-motor-inference-image")


def _enveloped(public):
    """The pack's physics role in its ``{version, definition}`` envelope, as
    Data Collection's packs-01 (226659b7) writes it; identity once that lands."""
    physics = json.loads(public["physics_contract"])
    if set(physics) == {"version", "definition"}:
        return public
    envelope = {
        "version": "motor-applied-physics-contract-20261018",
        "definition": physics,
    }
    raw = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
    return {**public, "physics_contract": raw}


def _write_pack(root, bank, public):
    physical_pack.write_public_pack(
        root, pack.CHALLENGE, pack.VERSION, exposed_development_bank=True
    )
    documents = pack.pack_documents(
        bank=bank,
        physics=json.loads(public["physics_contract"]),
        interface_raw=public["interface"],
        train_raw=public["train"],
        limits_sha256=_sha(public["important_limit_definition"]),
        objective_sha256=_sha(public["design_objective"]),
    )
    draft_path = root / "evaluation-pack.json"
    draft = json.loads(draft_path.read_bytes())
    (root / draft["public"]["physics_contract"]["path"]).write_bytes(
        public["physics_contract"]
    )
    for role, body in documents.items():
        scope = "public" if role == "accuracy_definition" else "private"
        name = f"{scope}/{role}.json"
        (root / name).write_bytes(body)
        draft[scope][role] = {"path": name}
    draft_path.write_bytes(_json(draft))
    prepared = prepare_pack(
        root,
        "evaluation-pack.json",
        public_root=root,
        private_root=root,
        challenge_id=pack.CHALLENGE,
        challenge_version=pack.VERSION,
    )
    snapshot = parse_pack(
        prepared.sealed_bytes,
        expected_digest=prepared.snapshot.manifest_digest,
        challenge_id=pack.CHALLENGE,
        challenge_version=pack.VERSION,
    )
    return snapshot, documents


def _retain_bundle(tmp, *, public, case_bank, predictions_raw):
    """Bundle custody as retention keeps a measured JAX export."""
    root = tmp / "task"
    root.mkdir()
    interface = _sha(public["interface"])
    bundle_digest = _sha(b"fixture-motor-bundle")
    recipe = {
        "schema": "carbon.construction-recipe.v1",
        "challenge": {
            "id": pack.CHALLENGE,
            "version": pack.VERSION,
            "train_digest": _sha(public["train"]),
            "interface_digest": interface,
            "construction_limits_digest": _sha(b"fixture-motor-limits"),
        },
        "source": {
            "kind": "bundle",
            "bundle_ref": {
                "schema": "carbon.library-bundle-ref.v1",
                "bundle_digest": bundle_digest,
                "language": "python",
                "runtime_profile_id": "fixture-only",
                "environment_digest": _sha(b"fixture-environment"),
            },
        },
        "procedure": {
            "entrypoint": {"module": "fixture", "name": "build"},
            "configuration": {},
            "train_use": {},
            "initial_state": None,
        },
        "output": {"format": "carbon.numeric-graph.v1", "interface_digest": interface},
    }
    graph = _json({"entry": "main", "graphs": {"main": {"inputs": [], "outputs": []}}})
    header = {
        "schema": custody.BUNDLE_STATE_SCHEMA,
        "recipe_digest": _sha(_json(recipe)),
        "bundle_digest": bundle_digest,
        "train_digest": _sha(public["train"]),
        "interface_digest": interface,
        "graph_digest": _sha(graph),
        "allowlist_digest": _sha(b"fixture-allowlist"),
        "parameter_count": 0,
    }
    state = _npz(
        __header__=("|u1", _json(header), (len(_json(header)),)),
        graph=("|u1", graph, (len(graph),)),
    )
    graded = {
        "schema": "carbon.development.bundle-inference.v1",
        "recipe_digest": _sha(_json(recipe)),
        "state_digest": _sha(state),
        "inputs_digest": _sha(case_bank),
        "predictions_digest": _sha(predictions_raw),
    }
    timed = {
        **graded,
        "schema": "carbon.development.bundle-inference.v2",
        "measurement": {
            "scope": bundle.TIMED_SCOPE,
            "timing_s": {
                "preprocess": 0.01,
                "export": 0.2,
                "inference": 0.05,
                "postprocess": 0.01,
            },
            "input_shape": [90, 8],
            "input_dtype": "float64",
            "output_shape": [90, 60],
            "output_dtype": "float64",
        },
    }
    artifacts = {
        "recipe.json": _json(recipe),
        "train.npz": public["train"],
        "inputs.npz": case_bank,
        "state.npz": state,
        "predictions.json": predictions_raw,
        "source.tar.gz": b"fixture source bytes; never executed",
        "environment.json": _json({"profile": "fixture"}),
        "image.json": _json({"image": "fixture"}),
        "inference-receipt.json": encode(graded),
        "timed-query-receipt.json": encode(timed),
    }
    roles = {
        "recipe": ("recipe.json", "json"),
        "train": ("train.npz", "numeric_npz"),
        "inputs": ("inputs.npz", "numeric_npz"),
        "state": ("state.npz", "bundle_graph_npz"),
        "predictions": ("predictions.json", "json"),
        "source": ("source.tar.gz", "raw_bytes"),
        "environment": ("environment.json", "raw_bytes"),
        "image": ("image.json", "json"),
        "inference_receipt": ("inference-receipt.json", "json"),
    }
    for name, body in artifacts.items():
        (root / name).write_bytes(body)
    manifest_path = tmp / "roles.json"
    manifest_path.write_bytes(
        _json(
            {
                "schema": custody.BUNDLE_ROLE_SCHEMA_V2,
                "scope": custody.BUNDLE_SCOPE,
                "source_schema": custody.BUNDLE_STATE_SCHEMA,
                "roles": {
                    role: {"file": name, "codec": codec}
                    for role, (name, codec) in roles.items()
                },
                "retained_files": {
                    name: _sha(body) for name, body in artifacts.items()
                },
                "physics_contract": None,
            }
        )
    )
    custody_raw = _json(custody.prepare_custody_v5(root, manifest_path))
    receipt_path = tmp / "custody.json"
    receipt_path.write_bytes(custody_raw)
    entries = tmp / "entries"
    entries.mkdir()
    entry = unbound_entry.create_entry_v5(root, manifest_path, receipt_path, entries)
    return entry["entry"], custody_raw, artifacts, timed


def _pair(receipt, outputs):
    """Two fresh Platform-shaped repeats of the graded model and inputs."""
    packet, _ = fixture()
    for field in ("recipe_digest", "state_digest", "inputs_digest"):
        packet[field] = receipt[field]
    packet["inference_image_id"] = IMAGE
    packet["logical_prediction_rows_per_operation"] = 90
    packet["logical_prediction_row_attempts"] = 180
    for name, repeat in (("primary", outputs[0]), ("repeat", outputs[1])):
        phase = packet[name]
        prediction_raw = encode(repeat)
        phase_receipt = deepcopy(receipt)
        phase_receipt["predictions_digest"] = _sha(prediction_raw)
        receipt_raw = encode(phase_receipt)
        phase["originals"] = {
            "predictions.json": original(prediction_raw),
            "receipt.json": original(receipt_raw),
        }
        phase["accounting"]["worker_result"]["files"] = {
            "predictions.json": _sha(prediction_raw),
            "receipt.json": _sha(receipt_raw),
        }
    return encode(packet)


@pytest.fixture(scope="module")
def motor(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("motor-e2e")
    bank = physical_pack.development_bank(pack.CHALLENGE, pack.VERSION)
    public = _enveloped(physical_pack.public_roles(pack.CHALLENGE, pack.VERSION))
    snapshot, documents = _write_pack(tmp / "pack", bank, public)
    names = physical_public_train.numeric_interface_document(pack.CHALLENGE)[
        "input_names"
    ]
    model = recipes.build(
        "kernel_ridge",
        {"length": 4.0, "ridge": 1e-4},
        PublicMaterial.load(physical_pack._REPOSITORY).train,
    )
    predictions = [
        [
            float(v)
            for v in model.predict(dict(zip(names, map(float, row))))["torque_nm"]
        ]
        for row in bank["inputs"]
    ]
    predictions_raw = json.dumps(predictions, allow_nan=False, separators=(",", ":"))
    case_bank = (tmp / "pack/private/case_bank.npz").read_bytes()
    entry, custody_raw, artifacts, timed = _retain_bundle(
        tmp,
        public=public,
        case_bank=case_bank,
        predictions_raw=predictions_raw.encode(),
    )
    registration_doc = json.loads(documents["source_registration"])
    # Platform's pair runs the same batched cold query form as the timed one.
    pair_raw = _pair(timed, [predictions, predictions])
    originals = {
        "inference_receipt_raw": artifacts["inference-receipt.json"],
        "predictions_raw": artifacts["predictions.json"],
        "bundle_evidence_raw": source._canonical(
            {
                "schema": source.BUNDLE_EVIDENCE_SCHEMA,
                "inference_operation": GRADED_OPERATION,
                "inference_image_id": IMAGE,
                "state_digest": entry["state_digest"],
                "predictions_digest": entry["prediction_digest"],
            }
        ),
        "timed_query": {
            "receipt_raw": artifacts["timed-query-receipt.json"],
            "registered_sha256": _sha(artifacts["timed-query-receipt.json"]),
        },
        "inference_pair_raw": pair_raw,
        "inference_pair_sha256": _sha(pair_raw),
    }
    return {
        "root": tmp / "pack",
        "snapshot": snapshot,
        "entry": entry,
        "custody_raw": custody_raw,
        "job": registration_doc["trusted_job"],
        "registration": registration_doc["benchmark_registration"],
        "version": registration_doc["evaluation_version"],
        "references": json.loads(documents["reference_rows"]),
        "score_pack": json.loads(documents["score_pack"]),
        "case_bank": case_bank,
        "originals": originals,
        "predictions": predictions,
    }


def _produce(case, originals=None):
    prepared_source = source.build_pack_source_receipt(
        selected_pack=case["snapshot"],
        entry=case["entry"],
        trusted_job=case["job"],
        registration=case["registration"],
        references=case["references"],
        ordered_query_bytes=[case["case_bank"]],
        evaluation_version=case["version"],
    )
    measured = source.produce_registered_dual_measurement(
        selected_pack=case["snapshot"],
        public_root=case["root"],
        private_root=case["root"],
        entry=case["entry"],
        trusted_job=case["job"],
        registration=case["registration"],
        references=case["references"],
        graph_originals=originals or case["originals"],
        evaluation_source_receipt_raw=prepared_source.raw,
    )
    return prepared_source, measured


def _bind(case, prepared_source, measured, scoring):
    return evidence.bind_private_evaluation_evidence(
        entry=case["entry"],
        custody_receipt_raw=case["custody_raw"],
        trusted_job=case["job"],
        registration=case["registration"],
        references=case["references"],
        measured_model=measured.measured_model,
        score_pack=case["score_pack"],
        graph_originals=case["originals"],
        expected_result_digest=evidence._sha(evidence._canonical(scoring)),
        ordered_query_bytes=[case["case_bank"]],
        evaluation_source_receipt_raw=prepared_source.raw,
        registered_source_receipt_sha256=prepared_source.sha256,
        expected_evaluation_pack_digest=case["snapshot"].manifest_digest,
        dual_measurement_receipt_raw=measured.raw,
        registered_dual_measurement_sha256=measured.sha256,
        selected_evaluation_pack=case["snapshot"],
    )


def test_a_retained_bundle_scores_the_recorded_baseline_and_binds_v4(motor):
    prepared_source, measured = _produce(motor)
    benchmark = json.loads(measured.raw)["benchmark"]
    legs = benchmark["models"][0]["measurements"]
    assert legs["robust_fidelity_benefit"]["value"] == pytest.approx(
        BASELINE_A, rel=0, abs=1e-12
    )
    assert legs["verified_value_benefit"]["value"] == pytest.approx(
        BASELINE_D, rel=0, abs=1e-12
    )
    assert benchmark["models"][0]["gates"] == {
        "native_motor_valid": "PASS",
        "complete_fixed_coverage": "PASS",
    }
    scoring = ScoreEngine.score_dual_benchmark_v4(benchmark, motor["score_pack"])
    bound = _bind(motor, prepared_source, measured, scoring)
    assert bound["schema"] == evidence.PAIRED_SIDECAR_SCHEMA
    assert bound["scoring"] == scoring
    assert bound["inference_pair_sha256"] == motor["originals"]["inference_pair_sha256"]
    assert bound["official_eligible"] is bound["official_score"] is False
    assert motor["entry"]["score_state"] == "NOT_COMPUTED"


def test_a_repeat_beyond_motors_rule_fails_its_gate_not_the_run(motor):
    drifted = deepcopy(motor["predictions"])
    drifted[0] = [t + 1e-3 for t in drifted[0]]
    timed = json.loads(motor["originals"]["timed_query"]["receipt_raw"])
    pair_raw = _pair(timed, [motor["predictions"], drifted])
    originals = {
        **motor["originals"],
        "inference_pair_raw": pair_raw,
        "inference_pair_sha256": _sha(pair_raw),
    }
    _, measured = _produce(motor, originals)
    gates = json.loads(measured.raw)["benchmark"]["models"][0]["gates"]
    assert gates["native_motor_valid"] == "FAIL"


def test_unretained_bundle_originals_are_refused(motor):
    timed = json.loads(motor["originals"]["timed_query"]["receipt_raw"])
    faster = {
        **timed,
        "measurement": {
            **timed["measurement"],
            "timing_s": {
                "preprocess": 0.0,
                "export": 0.0,
                "inference": 1e-6,
                "postprocess": 0.0,
            },
        },
    }
    for key, body in (
        ("inference_receipt_raw", b'{"not":"retained"}\n'),
        ("predictions_raw", b"[[0.0]]"),
        (
            "timed_query",
            {"receipt_raw": encode(faster), "registered_sha256": _sha(encode(faster))},
        ),
    ):
        with pytest.raises(source.PrivateEvaluationSourceRefused):
            _produce(motor, {**motor["originals"], key: body})
    # Without its timed query an unmeasured per-case receipt has no shapes.
    untimed = {k: v for k, v in motor["originals"].items() if k != "timed_query"}
    with pytest.raises(source.PrivateEvaluationSourceRefused):
        _produce(motor, untimed)
    reused = source._canonical(
        {
            **json.loads(motor["originals"]["bundle_evidence_raw"]),
            "inference_operation": json.loads(motor["originals"]["inference_pair_raw"])[
                "primary"
            ]["worker_operation"],
        }
    )
    with pytest.raises(
        source.PrivateEvaluationSourceRefused, match="dual_repeat_not_independent"
    ):
        _produce(motor, {**motor["originals"], "bundle_evidence_raw": reused})


def test_a_pinned_measurement_must_be_what_the_retained_originals_reduce_to(motor):
    """A consistent, newly pinned receipt cannot carry a faster timing than the
    retained timed query: the binder recomputes a bundle's measured model."""
    prepared_source, measured = _produce(motor)
    benchmark = json.loads(measured.raw)["benchmark"]
    faster = deepcopy(measured.measured_model)
    faster["cases"][0]["timing_s"]["inference"] = 1e-6
    forged = source.build_dual_measurement_receipt(
        selected_pack=motor["snapshot"],
        public_root=motor["root"],
        private_root=motor["root"],
        entry=motor["entry"],
        measured_model=faster,
        graph_originals=motor["originals"],
        evaluation_source_receipt_raw=prepared_source.raw,
        benchmark=benchmark,
        producer_digest=pack.producer_digest(),
    )
    scoring = ScoreEngine.score_dual_benchmark_v4(benchmark, motor["score_pack"])
    with pytest.raises(
        evidence.PrivateEvaluationEvidenceRefused,
        match="model_query_originals_unavailable",
    ):
        _bind(motor, prepared_source, forged, scoring)
