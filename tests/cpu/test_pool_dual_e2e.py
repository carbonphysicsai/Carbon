"""A real-shaped POOL-graded Motor 1.5 exam, sealed pack to a COMPUTED score and a v4 binding.

valV3, 2026-10-27/28: the counted pool grade has failed one seam at a time on live runs
(`evaluation_pack_registered_material_mismatch`, the batched timed query over a bank larger than the
graph's declared batch, `single_call_row_not_in_the_delivered_query`). This test takes the REAL Motor 1.5
sealed pool bank (30 sealed cells, the private probes and 200 pool rows, built by `sealed_batch_source`),
the REAL sealed pack the custody builder writes, the REAL pool adapter with the owner's registered
constants, the retained-model custody, the repeat pair, the receiver's single-call side file (drawn by the
real seeded draw over the bank's pool rows) and runs them through the REAL producer, the REAL score engine
and the REAL binding, with no batched timed query anywhere (GPU_REBUILD_RULINGS section 13).

STAND-INS (labelled, none is production): the pool targets are synthetic Motor-shaped targets in Motor's own
derived outputs (mean torque, ripple), the model is an analytic curve family (cells answer their references,
probes the registered model), the retained model is a bundle-shaped custody fixture (the production graph
route's custody is covered by the graph tests), the repeat pair is a fixture envelope around the same
outputs, and the single-call seconds are fixed figures. No worker or solver runs here.
"""

from __future__ import annotations

import io
import json
import math
import random

import pytest
from test_motor_sealed_family import records_for
from test_physical_dual_pack_end_to_end import (
    GRADED_OPERATION,
    IMAGE,
    _bind,
    _pair,
    _retain_bundle,
)

from carbon.challenge_kit import motor_sealed_pack as pack
from carbon.challenge_kit import physical_pack, physical_public_train
from carbon.challenge_validator import motor_sealed_grid as grid
from carbon.challenge_validator.evaluation_pack import parse_pack, prepare_pack
from carbon.development_session import single_call_timing
from carbon.motor.domain import ANGLE_STEPS
from carbon.motor_grid_exam import population
from carbon.motor_grid_exam.domain import CONDITION_INPUTS, DESIGN_INPUTS
from carbon.scoring import (
    grade_feedback,
    motor_physics,
    pool_adapters,
    pool_grader,
    pool_version,
    sealed_batch_source,
)
from carbon.scoring import motor_sealed_dual_pack as sealed
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import private_evaluation_evidence as evidence
from carbon.scoring import private_evaluation_source as source
from carbon.scoring.engine import ScoreEngine
from carbon.scoring.pool_grader import Limit

np = pytest.importorskip("numpy")

MOTOR = sealed_batch_source.MOTOR
VERSION = "1.5"
KEY = bytes(range(32))
SUBMISSION = "rtsk_" + "a" * 64


def _sha(raw):
    import hashlib

    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _targets(chosen, box, names, train_inputs):
    column = {name: i for i, name in enumerate(names)}

    def curve_of(row):
        values = dict(zip(names, row))
        d = [values[n] for n in DESIGN_INPUTS]
        u = [(d[i] - box[i][0]) / (box[i][1] - box[i][0]) for i in range(6)]
        mean = 4.2 + 3.0 * u[0] - 1.5 * u[1] + 0.5 * u[2]
        ripple = 0.1 + 0.3 * u[3] + 0.05 * u[4]
        return [
            mean * (1.0 + ripple * math.sin(2 * math.pi * k / ANGLE_STEPS))
            for k in range(ANGLE_STEPS)
        ]

    def target(target_id, seed, shift):
        rng = random.Random(seed)
        fixed = {
            name: float(train_inputs[:, column[name]].mean() * (1 + shift))
            for name in chosen.condition_names
        }
        designs, truths = [], []
        for _ in range(100):
            d = [lo + rng.random() * (hi - lo) for lo, hi in box]
            row = chosen.model_row(fixed, d)
            designs.append(d)
            truths.append(dict(chosen.derive_row(row, curve_of(row))))
        return pool_grader.build_target(
            target_id=target_id,
            conditions={"target_id": target_id, "fixed": fixed},
            outputs=chosen.outputs,
            objective=chosen.objective,
            sense=chosen.sense,
            limits=tuple(Limit(o, k, b) for o, k, b in chosen.limits),
            u={"mean_torque_nm": 0.001, "ripple_fraction": 0.0005},
            box=box,
            designs=designs,
            truths=truths,
            agen=range(92, 100),
            start=(0.5,) * 6,
            seed=seed,
        )

    return curve_of, [target("A1", 1, 0.0), target("A2", 2, 0.02)]


@pytest.fixture(scope="module")
def case(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("pool-dual-e2e")
    names = physical_public_train.numeric_interface_document(MOTOR)["input_names"]
    chosen = pool_adapters.adapter("motor", VERSION)
    box = pool_adapters.train_box(
        "motor", VERSION, chosen.design_names, chosen.input_names
    )
    public = physical_pack.public_roles(MOTOR, VERSION)
    train_inputs = np.asarray(np.load(io.BytesIO(public["train"]))["inputs"], float)
    curve_of, targets = _targets(chosen, box, names, train_inputs)
    material = {
        "schema": pool_version.MATERIAL_SCHEMA,
        "kind": "motor",
        "version": VERSION,
        "input_names": list(names),
        "design_names": list(DESIGN_INPUTS),
        "input_dtype": "<f8",
        "set_digest": "sha256:" + "5" * 64,
        "sets": [[pool_grader.dump_pool(t) for t in targets]],
    }
    cases, _ = population.draw(random.Random(3), population.CELLS)
    document = {
        "schema": grid.DOCUMENT_SCHEMA,
        "challenge": {"id": MOTOR, "version": "1.1"},
        "role": "grid",
        "kind": "screening",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"g{i:02d}", "inputs": c} for i, c in enumerate(cases)],
        "pool": material,
    }
    records = [
        dict(r, wall_s=1.5)
        for r in records_for({k: v for k, v in document.items() if k != "pool"})
    ]
    bank = sealed_batch_source._build(MOTOR, pack, document, records, VERSION)
    adapter = sealed.adapter(VERSION)
    assert adapter.POOL_GRADED and sealed.is_pool_bank(bank)
    root = tmp / "pack"
    manifest_path = sealed.write_sealed_pack(
        root, bank, version=VERSION, inference_image_id=IMAGE
    )
    # the sealed batch the pack carries (private custody): the receiver resolves the bank from it
    (root / sealed_batch_source.SEALED_BATCH_FILE).write_bytes(
        sealed_batch_source.batch_bytes(document, records)
    )
    prepared = prepare_pack(
        root,
        manifest_path.name,
        public_root=root,
        private_root=root,
        challenge_id=MOTOR,
        challenge_version=VERSION,
    )
    snapshot = parse_pack(
        prepared.sealed_bytes,
        expected_digest=prepared.snapshot.manifest_digest,
        challenge_id=MOTOR,
        challenge_version=VERSION,
    )
    draft = json.loads(manifest_path.read_bytes())
    documents = {
        role: (root / draft[scope][role]["path"]).read_bytes()
        for scope, role in (
            ("public", "accuracy_definition"),
            ("private", "reference_rows"),
            ("private", "score_pack"),
            ("private", "source_registration"),
            ("private", "case_bank"),
        )
    }
    # (sealed packs list their roles under the draft; the interface is a public role)
    rows = physical.bank_rows(bank, names)
    model = motor_physics.registered_model(public["train"])
    outputs = []
    for i, row in enumerate(rows):
        if row["cohort"] == "pool_design":
            outputs.append(curve_of([row["inputs"][n] for n in names]))
        elif row["cohort"] == "probe_response":
            outputs.append([model([row["inputs"][n] for n in names])] * ANGLE_STEPS)
        else:
            outputs.append([float(v) for v in bank["references"][i]])
    predictions_raw = json.dumps(outputs, allow_nan=False, separators=(",", ":"))
    entry, custody_raw, artifacts, _timed = _retain_bundle(
        adapter,
        tmp,
        public=public,
        case_bank=documents["case_bank"],
        predictions_raw=predictions_raw.encode(),
        shapes=(list(bank["inputs"].shape), list(bank["references"].shape)),
    )
    registration_doc = json.loads(documents["source_registration"])
    graded = json.loads(artifacts["inference-receipt.json"])
    pair_raw = _pair(graded, [outputs, outputs])
    seed = single_call_timing.sample_seed(KEY, SUBMISSION)
    indices = single_call_timing.delivered_indices(bank, bank["inputs"], seed)
    side = single_call_timing.side_file(
        indices=indices,
        warmup_digest="sha256:" + "8" * 64,
        call_s=[0.02 + 0.0005 * n for n in range(single_call_timing.SAMPLE)],
        outputs_match=True,
        operation="operation-" + "9" * 64,
    )
    side_raw = (json.dumps(side, sort_keys=True) + "\n").encode()
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
        "inference_pair_raw": pair_raw,
        "inference_pair_sha256": _sha(pair_raw),
        "single_call_raw": side_raw,
    }
    return {
        "adapter": adapter,
        "bank": bank,
        "root": root,
        "snapshot": snapshot,
        "entry": entry,
        "custody_raw": custody_raw,
        "job": registration_doc["trusted_job"],
        "registration": registration_doc["benchmark_registration"],
        "version": registration_doc["evaluation_version"],
        "references": json.loads(documents["reference_rows"]),
        "score_pack": json.loads(documents["score_pack"]),
        "case_bank": documents["case_bank"],
        "originals": originals,
        "outputs": outputs,
        "rows": rows,
        "indices": indices,
        "artifacts": artifacts,
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
        timing_step=grade_feedback.step(None),
        single_call_raw=(originals or case["originals"]).get("single_call_raw"),
    )
    return prepared_source, measured


def test_the_pool_bank_is_the_real_sealed_shape(case):
    bank = case["bank"]
    cohorts = list(bank["cohorts"])
    assert cohorts.count("pool_design") == 200
    assert cohorts.count("decision_sealed_grid") == 30
    assert len(case["rows"]) == len(cohorts) == 306
    assert case["score_pack"]["hard_gates"][-1] == "speed"
    # the 20 timed rows are pool rows of THIS bank, drawn by the real seeded draw
    assert len(case["indices"]) == single_call_timing.SAMPLE
    assert all(cohorts[i] == "pool_design" for i in case["indices"])


def test_a_pool_graded_model_reaches_a_computed_score_with_no_batched_timed_query(case):
    assert "timed_query" not in case["originals"]
    prepared_source, measured = _produce(case)
    benchmark = json.loads(measured.raw)["benchmark"]
    model = benchmark["models"][0]
    assert sorted(model["gates"]) == sorted(case["score_pack"]["hard_gates"])
    assert set(model["gates"].values()) == {"PASS"}
    scoring = ScoreEngine.score_dual_benchmark_v4(benchmark, case["score_pack"])
    scored = scoring["models"][0]
    assert type(scored["score"]) is float and 0.9 < scored["score"] <= 1.0
    assert scored["legs"]["D"] == pytest.approx(1.0)
    # the measured model's speed is the single-call median of the side file, nothing batched
    cases = measured.measured_model["cases"]
    median = sorted(
        single_call_timing.read_side_file(case["originals"]["single_call_raw"])[0]
    )
    assert cases[0]["timing_s"]["inference"] == pytest.approx(
        (median[9] + median[10]) / 2
    )
    assert cases[0]["timing_s"]["export"] == 0.0
    # and the score binds as a v4 paired sidecar over the retained originals
    bound = _bind(case, prepared_source, measured, scoring)
    assert bound["schema"] == evidence.PAIRED_SIDECAR_SCHEMA
    assert bound["scoring"] == scoring
    assert bound["official_eligible"] is bound["official_score"] is False


def test_a_slow_single_call_median_fails_the_speed_gate_and_the_score_is_gated(case):
    side = single_call_timing.side_file(
        indices=case["indices"],
        warmup_digest="sha256:" + "8" * 64,
        call_s=[1e6] * single_call_timing.SAMPLE,
        outputs_match=True,
        operation="operation-" + "9" * 64,
    )
    slow = {
        **case["originals"],
        "single_call_raw": (json.dumps(side, sort_keys=True) + "\n").encode(),
    }
    _, measured = _produce(case, slow)
    model = json.loads(measured.raw)["benchmark"]["models"][0]
    assert model["gates"]["speed"] == "FAIL"
    assert model["gates"]["native_motor_valid"] == "PASS"


def test_a_timed_query_or_missing_side_file_leaves_a_pool_grade_unavailable(case):
    timed = {
        "receipt_raw": case["artifacts"]["timed-query-receipt.json"],
        "registered_sha256": _sha(case["artifacts"]["timed-query-receipt.json"]),
        "predictions_raw": case["artifacts"]["timed-query-predictions.json"],
    }
    with pytest.raises(source.PrivateEvaluationSourceRefused):
        _produce(case, {**case["originals"], "timed_query": timed})
    without = {k: v for k, v in case["originals"].items() if k != "single_call_raw"}
    with pytest.raises(source.PrivateEvaluationSourceRefused):
        _produce(case, without)
    with pytest.raises(source.PrivateEvaluationSourceRefused):
        _produce(case, {**case["originals"], "single_call_raw": b"{}"})


def test_the_declared_dtypes_the_pair_is_read_against_are_the_banks_and_the_interface(
    case,
):
    interface = json.loads(physical_pack.public_roles(MOTOR, VERSION)["interface"])
    from carbon.challenge_kit.interface_dtype import output_dtype

    measurement = physical._pool_query_measurement(
        case["snapshot"],
        case["root"],
        case["registration"],
        case["originals"],
        case["bank"],
        source.PrivateEvaluationSourceRefused,
    )
    assert measurement["input_dtype"] == str(np.asarray(case["bank"]["inputs"]).dtype)
    assert measurement["output_dtype"] == str(np.dtype(output_dtype(interface)))
    assert (
        measurement["input_shape"]
        == case["registration"]["timing_profile"]["input_shape"]
    )
    assert CONDITION_INPUTS  # the version's condition inputs are part of the real interface


def test_only_the_pool_exam_emits_the_pool_graded_outcome():
    """Validator ruling (2026-10-28): `POOL_GRADED` has no policy entry (no cap), so nothing but the
    pool exam may emit it; a non-pool adapter's measure never returns it."""
    import pathlib
    import re

    from carbon.scoring import pool_exam

    assert pool_exam.OUTCOME_POOL == "POOL_GRADED"
    root = pathlib.Path(pool_exam.__file__).parent
    uses, literals = set(), set()
    for path in root.glob("*.py"):
        code = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        ]
        text = chr(10).join(code)
        if "OUTCOME_POOL" in text:
            uses.add(path.name)
        # the outcome as a string value (a getattr(x, "POOL_GRADED") flag read is not one)
        flag_reads_removed = re.sub(r'getattr\(\w+, "POOL_GRADED"', "", text)
        if '"POOL_GRADED"' in flag_reads_removed:
            literals.add(path.name)
    assert uses == {"pool_exam.py"}
    assert literals == {"pool_exam.py", "dual_score.py"}


def _explained(case, monkeypatch, *, producer_differs=False):
    """Run the producer with the grade explainer installed; return (printed lines, failed checks)."""
    from scripts.dev.sealed_exam import grade_explain

    lines = []
    monkeypatch.setattr(physical, "_inputs", physical._inputs)
    monkeypatch.setattr(source, "_producer_require", source._producer_require)
    grade_explain.install(print_=lines.append)
    if producer_differs:
        monkeypatch.setattr(
            physical, "producer_digest", lambda _adapter: "sha256:" + "0" * 64
        )
    try:
        _produce(case)
    except source.PrivateEvaluationSourceRefused:
        pass  # a later step may fail for the same root cause: the explainer reports, it does not decide
    return lines, list(grade_explain.FAILED)


def test_the_grade_explainer_is_silent_about_failures_when_every_check_passes(
    case, monkeypatch
):
    lines, failed = _explained(case, monkeypatch)
    text = chr(10).join(lines)
    assert failed == []
    assert "binding  PRODUCER ok" in text and "binding  TRAIN ok" in text
    assert "binding  BANK ok" in text


def test_the_grade_explainer_names_which_binding_differs_and_lists_the_failed_check(
    case, monkeypatch
):
    """valV3 2026-10-28: 'dual_native_producer_or_train_binding' stands for the producer digest, the train and
    the bank at once; the explainer says which, with this host's per-file hashes for the producer.
    """
    lines, failed = _explained(case, monkeypatch, producer_differs=True)
    text = chr(10).join(lines)
    assert failed and failed[0] == "dual_native_producer_or_train_binding"
    assert "binding  PRODUCER DIFFERS" in text
    assert "binding  TRAIN ok" in text and "binding  BANK ok" in text
    assert (
        "physical_dual_pack.py  sha256:" in text
    )  # this host's files, to compare with the build host
