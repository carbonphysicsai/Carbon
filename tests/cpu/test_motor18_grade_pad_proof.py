"""PAD-PROOF: a synthetic Motor 1.8 GRADE on the real pack builder, run with two different pads (13 Nov, V2C condition 2).

The 1.8 sealed bank's references are 240 wide: the sealed torque truth in columns 0-59 and a structural pad in columns 60-239
(`motor_sealed_pack._ROW_PAD`; no sealed truth exists there). This test grades a 1.8 pool bank end to end on the REAL builders and
the REAL producer, twice, with the pad at 0 and at a finite sentinel (1e9), and asserts every graded outcome identical: the gate
verdicts, the A and D legs, the decision outcome, the engine's score, and the typed code of a refused grade. It therefore proves
that no reader of the grade scores columns 60-239.

STAND-INS (labelled; none is production): the exam's registered policies are the Motor 1.5 pool version's (no menu, no physics
headroom: those registrations pin sealed custody documents a synthetic exam cannot reproduce, and neither reads the bank's
reference columns), the pool targets are synthetic Motor-shaped targets built from 1.8's OWN derive (torque, pk-pk, the two EMF
waveforms), the model is an analytic 240-wide row family, the retained model is a bundle-shaped custody fixture, the repeat pair a
fixture envelope around the same outputs, and the single-call seconds are fixed figures. No worker or solver runs.
"""

from __future__ import annotations

import dataclasses
import io
import json
import math
import random
import sys
from pathlib import Path
from typing import ClassVar

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_motor_sealed_family import records_for
from test_physical_dual_pack_end_to_end import (
    GRADED_OPERATION,
    IMAGE,
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
from carbon.motor_grid_exam.domain import DESIGN_INPUTS
from carbon.scoring import (
    grade_feedback,
    motor_physics,
    pair_read_bound,
    pool_adapters,
    pool_grader,
    pool_version,
    sealed_batch_source,
)
from carbon.scoring import motor18_dual_pack as m18
from carbon.scoring import motor_sealed_dual_pack as sealed
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import private_evaluation_source as source
from carbon.scoring.engine import ScoreEngine
from scripts.dev.score_lab import public_unbound_custody as custody

np = pytest.importorskip("numpy")

MOTOR = sealed_batch_source.MOTOR
VERSION = "1.8"
KEY = bytes(range(32))
SUBMISSION = "rtsk_" + "a" * 64
WIDTH = 4 * ANGLE_STEPS
SENTINEL = 1e9
#: Two targets of 1229 designs: with the grid's 30 cells and 76 private probes, the bank is the canary's 2564 rows.
DESIGNS = 1229


def _sha(raw):
    import hashlib

    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _row_of(torque, scale):
    """A whole 1.8 row: the torque slice, then the three phase linkages (a smooth, valid waveform each)."""
    steps = range(ANGLE_STEPS)
    linkages = [
        [scale * math.sin(2 * math.pi * k / ANGLE_STEPS + phase) for k in steps]
        for phase in (0.0, 2.0 * math.pi / 3.0, 4.0 * math.pi / 3.0)
    ]
    return [*torque, *(v for phase in linkages for v in phase)]


def _targets(chosen, box, names, train_inputs):
    column = {name: i for i, name in enumerate(names)}

    def curve_of(row):
        values = dict(zip(names, row))
        d = [values[n] for n in DESIGN_INPUTS]
        u = [(d[i] - box[i][0]) / (box[i][1] - box[i][0]) for i in range(6)]
        mean = 4.2 + 3.0 * u[0] - 1.5 * u[1] + 0.5 * u[2]
        ripple = 0.1 + 0.3 * u[3] + 0.05 * u[4]
        torque = [
            mean * (1.0 + ripple * math.sin(2 * math.pi * k / ANGLE_STEPS))
            for k in range(ANGLE_STEPS)
        ]
        return _row_of(torque, 0.02 + 0.01 * u[5])

    def target(target_id, seed, shift):
        rng = random.Random(seed)
        fixed = {
            name: float(train_inputs[:, column[name]].mean() * (1 + shift))
            for name in chosen.condition_names
        }
        designs, truths = [], []
        for _ in range(DESIGNS):
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
            limits=(),
            u={
                "mean_torque_nm": 0.001,
                "ripple_pk_pk_nm": 0.0005,
                "back_emf_open_circuit": 0.001,
                "ke_ll_loaded": 0.001,
            },
            box=box,
            designs=designs,
            truths=truths,
            agen=range(DESIGNS - 8, DESIGNS),
            start=(0.5,) * 6,
            seed=seed,
        )

    return curve_of, [target("A1", 1, 0.0), target("A2", 2, 0.02)]


def build_case(tmp, monkeypatch, pad, mutate=None):
    """One complete 1.8 pool pack and its retained model, built with ``pad`` in the bank's non-truth columns."""
    monkeypatch.setattr(pack, "_ROW_PAD", pad)
    # the exam's registered policies: the Motor 1.5 pool version's (the stand-in named in the module docstring)
    real = pool_version.registered_policies

    def policies_of(challenge, version, **kw):
        base = real(challenge, "1.5", **kw)
        # the scales cover 1.8's four derived outputs (1.8's registered values for the three it registers)
        scales = {
            "mean_torque_nm": 0.0895,
            "ripple_pk_pk_nm": 0.0261,
            "back_emf_open_circuit": 0.00597,
            "ke_ll_loaded": 0.00597,
        }
        return dataclasses.replace(base, agen_scales=scales)

    monkeypatch.setattr(pool_version, "registered_policies", policies_of)
    real_multiplier = pool_version.registered_a_multiplier
    monkeypatch.setattr(
        pool_version,
        "registered_a_multiplier",
        lambda challenge, version, **kw: real_multiplier(challenge, "1.5", **kw),
    )
    names = physical_public_train.numeric_interface_document(MOTOR)["input_names"]
    chosen = m18.pool_adapter()
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
    assert bank["references"].shape[1] == WIDTH
    root = tmp / "pack"
    manifest_path = sealed.write_sealed_pack(
        root, bank, version=VERSION, inference_image_id=IMAGE
    )
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
    rows = physical.bank_rows(bank, names)
    model = motor_physics.registered_model(m18._torque_train())
    outputs = []
    for i, row in enumerate(rows):
        if row["cohort"] == "pool_design":
            outputs.append(curve_of([row["inputs"][n] for n in names]))
        elif row["cohort"] == "probe_response":
            response = model([row["inputs"][n] for n in names])
            outputs.append(_row_of([response] * ANGLE_STEPS, 0.02))
        else:
            truth = [float(v) for v in bank["references"][i][:ANGLE_STEPS]]
            outputs.append(_row_of(truth, 0.02))
    if mutate is not None:
        mutate(outputs, rows)
    predictions_raw = json.dumps(outputs, allow_nan=False, separators=(",", ":"))
    # the regrade's custody reads the retained set under the bank's own bound (`lean_recipe_retention._custody_json_ceiling`)
    with custody.raised_json_bytes(
        pair_read_bound.pair_bytes(*bank["references"].shape)
    ):
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
        "custody_raw": custody_raw,
        "copy_hotkey": None,
    }


def grade(case, originals=None):
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
        copy_hotkey=None,
    )
    return prepared_source, measured


def outcome(case):
    """Everything a grade decides, with the identities that legitimately differ between two banks left out."""
    try:
        _prepared, measured = grade(case)
    except source.PrivateEvaluationSourceRefused as refused:
        return {"refused": refused.code}
    benchmark = json.loads(measured.raw)["benchmark"]
    model = {k: v for k, v in benchmark["models"][0].items() if k != "artifact_digest"}
    scoring = ScoreEngine.score_dual_benchmark_v4(benchmark, case["score_pack"])
    scored = {k: v for k, v in scoring["models"][0].items() if k != "artifact_digest"}
    return {"model": model, "scoring": scored}


def _gate_failing(outputs, rows):
    """Every pool answer's torque goes negative: the physics gates fail (the candidate's, never a refusal)."""
    for row, out in zip(rows, outputs, strict=True):
        if row["cohort"] == "pool_design":
            out[:ANGLE_STEPS] = [-abs(v) - 1.0 for v in out[:ANGLE_STEPS]]


def _short_row(outputs, rows):
    """One answer is 60 wide, not a whole 1.8 row."""
    outputs[3] = outputs[3][:ANGLE_STEPS]


SCENARIOS = {
    "honest": None,
    "gate_failing": _gate_failing,
    "short_row": _short_row,
}


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_the_grade_is_identical_whatever_the_pad(scenario, tmp_path, monkeypatch):
    mutate = SCENARIOS[scenario]
    # each pack is graded under its own pad: the grade rebuilds the bank from the pack's sealed batch with the same kit, so
    # the pad is part of a pack's identity and stays fixed between its build and its grade (as it does in production)
    zero = build_case(tmp_path / "zero", monkeypatch, 0.0, mutate)
    first = outcome(zero)
    sentinel = build_case(tmp_path / "sentinel", monkeypatch, SENTINEL, mutate)
    second = outcome(sentinel)
    # the two packs really differ: the pad is in the bank, in the reference rows the producer binds, and in the definition's bank digest
    z_pad = zero["bank"]["references"][:, ANGLE_STEPS:]
    s_pad = sentinel["bank"]["references"][:, ANGLE_STEPS:]
    referenced = ~np.isnan(z_pad).all(axis=1)
    assert referenced.sum() == 30 and (z_pad[referenced] == 0.0).all()
    assert (s_pad[referenced] == SENTINEL).all()
    assert zero["references"] != sentinel["references"]
    assert zero["registration"]["reference"] != sentinel["registration"][
        "reference"
    ] or (zero["references"] != sentinel["references"])
    assert first == second
    if scenario == "honest":
        scoring = first["scoring"]
        assert scoring["status"] == "SCORED_DEVELOPMENT_CANDIDATE"
        assert type(scoring["score"]) is float and 0.0 < scoring["score"] <= 1.0
        assert set(first["model"]["gates"].values()) == {"PASS"}
    elif scenario == "gate_failing":
        assert "FAIL" in first["model"]["gates"].values()
    else:
        assert first["refused"].startswith("dual_native_")


def test_a_1_8_pool_pack_is_graded_end_to_end_at_the_canarys_shape(
    tmp_path, monkeypatch
):
    case = build_case(tmp_path, monkeypatch, 0.0)
    assert len(case["outputs"]) == 2564
    assert case["bank"]["references"].shape == (2564, WIDTH)
    assert (
        len(case["originals"]["predictions_raw"]) > 12_000_000
    )  # the canary's retained predictions were 12.3 MB
    assert outcome(case)["scoring"]["status"] == "SCORED_DEVELOPMENT_CANDIDATE"


class _Watched(list):
    """A reference row that records every way a reader touches it."""

    touched: ClassVar[list] = []

    def _note(self, how):
        frame = sys._getframe(2)
        _Watched.touched.append(
            f"{how} by {Path(frame.f_code.co_filename).name}:{frame.f_code.co_name}:{frame.f_lineno}"
        )

    def __getitem__(self, index):
        self._note("getitem")
        return super().__getitem__(index)

    def __iter__(self):
        self._note("iter")
        return super().__iter__()

    def __len__(self):
        self._note("len")
        return super().__len__()


def test_no_reader_of_the_grade_touches_a_reference_row_at_all(tmp_path, monkeypatch):
    """The instrumented control behind the identical grades: every present row's reference (all 240 columns) is replaced by a
    row that records any access, the honest grade runs, and nothing but the pack builder's own conversion touched one.
    """
    case = build_case(tmp_path, monkeypatch, 0.0)
    real = physical.bank_rows
    _Watched.touched = []

    def watched(bank, names):
        rows = real(bank, names)
        for row in rows:
            if row["reference"] is not None:
                watched_row = _Watched()
                list.extend(watched_row, row["reference"])
                row["reference"] = watched_row
        return rows

    monkeypatch.setattr(physical, "bank_rows", watched)
    _Watched.touched = []
    assert outcome(case)["scoring"]["status"] == "SCORED_DEVELOPMENT_CANDIDATE"
    assert (
        _Watched.touched == []
    ), f"a reader touched a reference row: {sorted(set(_Watched.touched))}"
