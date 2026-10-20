"""Each physical Challenge's dual path end to end, sources to a v4 binding.

DEVELOPMENT only, exposed development bank; Motor and Cooling run the same
path. The pack is Data Collection's ``physical_pack`` with this producer's
documents, written by the executor's ``write_development_pack``; the model is a
retained
bundle in the shape retention keeps for a JAX export under the per-case judge:
the graded per-case receipt (v1, role ``inference_receipt``) and a separate
batched cold timed query (v2, ``timed-query-receipt.json``, an original file,
not a role) that alone carries timing and shapes. The predictions are the
learned-krr-v1 baseline rebuilt from public TRAIN, so the graded legs must
equal each Challenge's recorded baseline legs. Platform-shaped pair records are fixture
envelopes around those same predictions; no worker or solver runs here.
"""

from __future__ import annotations

import json
from copy import deepcopy

import pytest
from test_inference_pair_evidence import encode, fixture, original
from test_public_bundle_model_custody import _json, _npz, _sha

from carbon.challenge_kit import physical_pack
from carbon.challenge_validator.evaluation_pack import parse_pack, prepare_pack
from carbon.scoring import bundle_benchmark_core as bundle
from carbon.scoring import cooling_dual_pack as cooling
from carbon.scoring import f08_dual_pack as f08
from carbon.scoring import motor_dual_pack as motor
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import private_evaluation_evidence as evidence
from carbon.scoring import private_evaluation_source as source
from carbon.scoring.engine import ScoreEngine
from scripts.dev.score_lab import public_unbound_custody as custody
from scripts.dev.score_lab import public_unbound_entry as unbound_entry

#: adapter, the gate the paired repeat fails. The producer path must reproduce
#: the baseline's own same-platform measurement exactly (no tolerance).
CHALLENGES = {
    "motor": (motor, "native_motor_valid"),
    "cooling": (cooling, "native_cold_plate"),
    "f08": (f08, "paired_repeat"),
    "f08-1.1": (f08.adapter(version="1.1"), "paired_repeat"),
}
GRADED_OPERATION = "operation-" + "a" * 64
IMAGE = _sha(b"fixture-motor-inference-image")


def _public(adapter):
    """The pack's public roles. A generated physics contract (Cooling) joins
    them as Data Collection's ``physical_pack`` will carry it."""
    public = physical_pack.public_roles(adapter.CHALLENGE, adapter.VERSION)
    generated = adapter.physics_contract()
    if generated is not None and "physics_contract" not in public:
        raw = json.dumps(generated, sort_keys=True, separators=(",", ":")).encode()
        public = {**public, "physics_contract": raw}
    return public


def _write_pack(adapter, root, public, **options):
    """The pack exactly as ``write_development_pack`` writes it (the executor's
    command), sealed as the receiver seals it."""
    with pytest.MonkeyPatch.context() as patch:
        if physical_pack.physics_contract(adapter.CHALLENGE, adapter.VERSION) is None:
            # Until physical_pack carries the generated Cooling contract.
            patch.setattr(
                physical_pack,
                "physics_contract",
                lambda *_: json.loads(public["physics_contract"]),
            )
            patch.setattr(physical_pack, "public_roles", lambda *_: public)
        manifest = adapter.write_development_pack(
            root, **{"inference_image_id": IMAGE, **options}
        )
    assert manifest == root / physical.MANIFEST_NAME
    prepared = prepare_pack(
        root,
        physical.MANIFEST_NAME,
        public_root=root,
        private_root=root,
        challenge_id=adapter.CHALLENGE,
        challenge_version=adapter.VERSION,
    )
    snapshot = parse_pack(
        prepared.sealed_bytes,
        expected_digest=prepared.snapshot.manifest_digest,
        challenge_id=adapter.CHALLENGE,
        challenge_version=adapter.VERSION,
    )
    draft = json.loads(manifest.read_bytes())
    documents = {
        role: (root / draft[scope][role]["path"]).read_bytes()
        for scope, role in (
            ("public", "accuracy_definition"),
            ("private", "reference_rows"),
            ("private", "score_pack"),
            ("private", "source_registration"),
        )
    }
    return snapshot, documents


def _retain_bundle(adapter, tmp, *, public, case_bank, predictions_raw, shapes):
    """Bundle custody as retention keeps a measured JAX export."""
    root = tmp / "task"
    root.mkdir()
    interface = _sha(public["interface"])
    bundle_digest = _sha(b"fixture-motor-bundle")
    recipe = {
        "schema": "carbon.construction-recipe.v1",
        "challenge": {
            "id": adapter.CHALLENGE,
            "version": adapter.VERSION,
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
            "input_shape": shapes[0],
            "input_dtype": "float64",
            "output_shape": shapes[1],
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
    packet["logical_prediction_rows_per_operation"] = len(outputs[0])
    packet["logical_prediction_row_attempts"] = 2 * len(outputs[0])
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


def _baseline(name, bank, public, names):
    if name == "motor":
        return motor.baseline_outputs(
            [dict(zip(names, map(float, row))) for row in bank["inputs"]]
        )
    if name.startswith("f08"):
        return f08._baseline_outputs(
            physical.bank_rows(bank, names), public["train"], names
        )
    return cooling._baseline_outputs(
        physical.bank_rows(bank, names),
        cooling._train_records(public["train"], names),
    )


@pytest.fixture(scope="module", params=sorted(CHALLENGES))
def case(request, tmp_path_factory):
    adapter, native_gate = CHALLENGES[request.param]
    tmp = tmp_path_factory.mktemp(request.param + "-e2e")
    bank = physical_pack.development_bank(adapter.CHALLENGE, adapter.VERSION)
    public = _public(adapter)
    snapshot, documents = _write_pack(adapter, tmp / "pack", public)
    names = physical.input_names(adapter)
    predictions = _baseline(request.param, bank, public, names)
    # The same baseline measured directly on this platform: the producer path
    # must reproduce it exactly.
    direct = adapter.measure(
        bank_rows=physical.bank_rows(bank, names),
        outputs=predictions,
        repeats=[predictions, predictions],
        definition=json.loads(documents["accuracy_definition"]),
        limits=json.loads(public["important_limit_definition"]),
        objective=json.loads(public["design_objective"]),
        train_raw=public["train"],
        names=names,
    )
    predictions_raw = json.dumps(predictions, allow_nan=False, separators=(",", ":"))
    case_bank = (tmp / "pack/private/case_bank.npz").read_bytes()
    entry, custody_raw, artifacts, _timed = _retain_bundle(
        adapter,
        tmp,
        public=public,
        case_bank=case_bank,
        predictions_raw=predictions_raw.encode(),
        shapes=(list(bank["inputs"].shape), list(bank["references"].shape)),
    )
    registration_doc = json.loads(documents["source_registration"])
    # The pair repeats the identical graded per-case procedure (v1 receipts).
    graded = json.loads(artifacts["inference-receipt.json"])
    pair_raw = _pair(graded, [predictions, predictions])
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
        "adapter": adapter,
        "public": public,
        "native_gate": native_gate,
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
        "direct": direct,
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


def test_a_retained_bundle_scores_the_recorded_baseline_and_binds_v4(case):
    prepared_source, measured = _produce(case)
    benchmark = json.loads(measured.raw)["benchmark"]
    legs = benchmark["models"][0]["measurements"]
    assert legs["robust_fidelity_benefit"]["value"] == case["direct"]["A"]
    assert legs["verified_value_benefit"]["value"] == case["direct"]["D"]
    gates = benchmark["models"][0]["gates"]
    assert sorted(gates) == sorted(case["score_pack"]["hard_gates"])
    assert set(gates.values()) == {"PASS"}
    scoring = ScoreEngine.score_dual_benchmark_v4(benchmark, case["score_pack"])
    bound = _bind(case, prepared_source, measured, scoring)
    assert bound["schema"] == evidence.PAIRED_SIDECAR_SCHEMA
    assert bound["scoring"] == scoring
    assert bound["inference_pair_sha256"] == case["originals"]["inference_pair_sha256"]
    assert bound["official_eligible"] is bound["official_score"] is False
    assert case["entry"]["score_state"] == "NOT_COMPUTED"


def test_another_grading_image_is_refused_not_failed(case):
    """A receiver inference-image override (direct_receiver's
    inference_image_manifest) changes the retained inference_image_id; grading
    compares that retained value, never config, with the pack's platform."""
    other = source._canonical(
        {
            **json.loads(case["originals"]["bundle_evidence_raw"]),
            "inference_image_id": _sha(b"another-judge-image"),
        }
    )
    with pytest.raises(
        source.PrivateEvaluationSourceRefused, match="leg_minimum_platform_mismatch"
    ):
        _produce(case, {**case["originals"], "bundle_evidence_raw": other})


def test_a_batched_repeat_is_not_a_repeat_of_the_per_case_grade(case):
    """Validator, 2026-10-19: the pair must repeat the identical graded
    procedure; a batched measured pair measures batch dependence instead."""
    timed = json.loads(case["originals"]["timed_query"]["receipt_raw"])
    pair_raw = _pair(timed, [case["predictions"], case["predictions"]])
    batched = {
        **case["originals"],
        "inference_pair_raw": pair_raw,
        "inference_pair_sha256": _sha(pair_raw),
    }
    with pytest.raises(
        source.PrivateEvaluationSourceRefused, match="dual_repeat_evidence_unavailable"
    ):
        _produce(case, batched)


def test_a_repeat_beyond_the_native_rule_fails_its_gate_not_the_run(case):
    drifted = deepcopy(case["predictions"])
    drifted[0] = [t + 1e-3 for t in drifted[0]]
    graded = json.loads(case["originals"]["inference_receipt_raw"])
    pair_raw = _pair(graded, [case["predictions"], drifted])
    originals = {
        **case["originals"],
        "inference_pair_raw": pair_raw,
        "inference_pair_sha256": _sha(pair_raw),
    }
    _, measured = _produce(case, originals)
    gates = json.loads(measured.raw)["benchmark"]["models"][0]["gates"]
    assert gates[case["native_gate"]] == "FAIL"


def test_unretained_bundle_originals_are_refused(case):
    timed = json.loads(case["originals"]["timed_query"]["receipt_raw"])
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
            _produce(case, {**case["originals"], key: body})
    # Without its timed query an unmeasured per-case receipt has no shapes.
    untimed = {k: v for k, v in case["originals"].items() if k != "timed_query"}
    with pytest.raises(source.PrivateEvaluationSourceRefused):
        _produce(case, untimed)
    reused = source._canonical(
        {
            **json.loads(case["originals"]["bundle_evidence_raw"]),
            "inference_operation": json.loads(case["originals"]["inference_pair_raw"])[
                "primary"
            ]["worker_operation"],
        }
    )
    with pytest.raises(
        source.PrivateEvaluationSourceRefused, match="dual_repeat_not_independent"
    ):
        _produce(case, {**case["originals"], "bundle_evidence_raw": reused})


def test_a_pinned_measurement_must_be_what_the_retained_originals_reduce_to(case):
    """A consistent, newly pinned receipt cannot carry a faster timing than the
    retained timed query: the binder recomputes a bundle's measured model."""
    prepared_source, measured = _produce(case)
    benchmark = json.loads(measured.raw)["benchmark"]
    faster = deepcopy(measured.measured_model)
    faster["cases"][0]["timing_s"]["inference"] = 1e-6
    forged = source.build_dual_measurement_receipt(
        selected_pack=case["snapshot"],
        public_root=case["root"],
        private_root=case["root"],
        entry=case["entry"],
        measured_model=faster,
        graph_originals=case["originals"],
        evaluation_source_receipt_raw=prepared_source.raw,
        benchmark=benchmark,
        producer_digest=case["adapter"].producer_digest(),
    )
    scoring = ScoreEngine.score_dual_benchmark_v4(benchmark, case["score_pack"])
    with pytest.raises(
        evidence.PrivateEvaluationEvidenceRefused,
        match="model_query_originals_unavailable",
    ):
        _bind(case, prepared_source, forged, scoring)


def _with_pack(case, root, **options):
    """The same retained model and originals under another built pack."""
    snapshot, documents = _write_pack(case["adapter"], root, case["public"], **options)
    registration = json.loads(documents["source_registration"])
    return {
        **case,
        "root": root,
        "snapshot": snapshot,
        "job": registration["trusted_job"],
        "registration": registration["benchmark_registration"],
        "version": registration["evaluation_version"],
        "references": json.loads(documents["reference_rows"]),
        "score_pack": json.loads(documents["score_pack"]),
        "definition": json.loads(documents["accuracy_definition"]),
    }


def _graded_binding(case):
    prepared_source, measured = _produce(case)
    benchmark = json.loads(measured.raw)["benchmark"]
    scoring = ScoreEngine.score_dual_benchmark_v4(benchmark, case["score_pack"])
    return scoring, _bind(case, prepared_source, measured, scoring)


def test_the_baseline_graded_on_the_judge_image_sets_the_minimums(case, tmp_path):
    """Validator, 2026-10-19: the minimums are the registered baseline's own
    legs graded on the judge image; that run sets them and never contends."""
    calibration = _with_pack(case, tmp_path / "calibration", calibration=True)
    assert all(
        leg["minimum"] is None for leg in calibration["score_pack"]["legs"].values()
    )
    assert calibration["definition"]["leg_minimum_mode"] == "calibration"
    assert "-calibration-" in calibration["version"]
    _, bound = _graded_binding(calibration)
    graded_under = {
        "baseline_binding_raw": physical.canonical(bound),
        "calibration_pack_root": calibration["root"],
    }
    # The per-image platform is the baseline run's, never a caller value: no
    # image needed, and a differing one (e.g. the analysis image) is refused.
    judge = _with_pack(
        case, tmp_path / "judge", inference_image_id=None, **graded_under
    )
    with pytest.raises(ValueError, match="differs from the baseline run"):
        _with_pack(
            case,
            tmp_path / "analysis",
            inference_image_id=_sha(b"fixture-analysis-image"),
            **graded_under,
        )
    legs = bound["scoring"]["models"][0]["legs"]
    assert {k: v["minimum"] for k, v in judge["score_pack"]["legs"].items()} == {
        "A": legs["A"],
        "D": legs["D"],
    }
    record = judge["definition"]["leg_minimum_source"]
    assert record["role"] == physical.BASELINE_ROLE
    assert record["entry_id"] == case["entry"]["entry_id"]
    assert record["inference_image_id"] == IMAGE
    assert record["binding_sha256"] == _sha(physical.canonical(bound))
    assert physical.minimum_source_entry_ids(judge["definition"]) == [
        case["entry"]["entry_id"]
    ]
    assert physical.minimum_source_entry_ids(calibration["definition"]) == []
    assert "-judge-" in judge["version"] and judge["version"] != case["version"]
    if case["adapter"] is cooling:
        # The comparison variant takes the same run's A and no D minimum.
        variant = _with_pack(
            case,
            tmp_path / "variant",
            rule="baseline_a_no_d_minimum",
            **graded_under,
        )
        assert variant["score_pack"]["legs"]["A"]["minimum"] == legs["A"]
        assert variant["score_pack"]["legs"]["D"]["minimum"] is None
    # The same baseline on the same image passes its own minimums at equality.
    scoring, other = _graded_binding(judge)
    assert scoring["models"][0]["status"] == "SCORED_DEVELOPMENT_CANDIDATE"
    # A binding from any other pack, or with changed legs, sets nothing.
    forged = deepcopy(bound)
    forged["scoring"]["models"][0]["legs"]["A"] = 0.0
    for name, binding, reason in (
        ("other", other, "not graded under this calibration pack"),
        ("forged", forged, "scored calibration run"),
    ):
        with pytest.raises(ValueError, match=reason):
            _with_pack(
                case,
                tmp_path / name,
                baseline_binding_raw=physical.canonical(binding),
                calibration_pack_root=calibration["root"],
            )
