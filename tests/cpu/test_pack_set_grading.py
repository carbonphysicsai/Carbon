"""A retained bundle model is graded on every batch of its pack set
(OWNER-FULL-EXAM-BANK-01): one regrade per batch pack by the unchanged per-pack
path, then one set-level result. The grading core is stubbed here exactly as in
test_regrade_retained_entry; it is covered by test_normal_dual_pack_retention."""

import copy
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_regrade_retained_entry import _retained

from carbon.challenge_validator import exam_cap
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator import pack_set_grading as grading
from carbon.challenge_validator import pack_set_result as psr
from carbon.challenge_validator import sealed_exam_common as common
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.development_session.bundle_construction_worker import _tensors

HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
GATES = ("g1", "g2")


def _contents(batches):
    """Each batch's exam content for the pack-set key (inert: the batch digest
    stands in for both role digests)."""
    return [{"case_bank": d, "reference_rows": d} for d in batches]


def _digest(c):
    return "sha256:" + c * 64


BATCHES = [_digest("e"), _digest("f")]


def _row(a, d, ok=True):
    return {
        "status": psr.SCORED if ok else psr.GATE_FAILED,
        "score": 0.5 * a + 0.5 * d,
        "legs": {"A": a, "D": d},
        "gates": {g: ("PASS" if ok else "FAIL") for g in GATES},
    }


def _batch_adapters(fixture, tmp_path, scales):
    adapters = {}
    for digest, scale in zip(BATCHES, scales, strict=True):
        practice = fixture.material["practice_inputs"]
        bank_raw = _tensors(inputs=(practice * scale).astype(practice.dtype))
        snapshot = SimpleNamespace(
            manifest_digest=digest,
            read_role=lambda *_a, _raw=bank_raw, **_k: _raw,
            read_source_registration=lambda _root: {"evaluation_version": "ev-1"},
            read_json_role=lambda *_a, **_k: {"hard_gates": list(GATES)},
        )
        adapter = copy.copy(fixture.adapter)
        adapter.discovery = SimpleNamespace(
            _material=fixture.material,
            evaluation_pack_snapshot=snapshot,
            evaluation_pack_digest=digest,
            evaluation_pack_private_root=Path(tmp_path),
        )
        adapter._provider = lambda _owner: fixture.provider
        adapter.exam_cadence = {
            "capacity_cpu_hours_per_day": 270.0,
            "rebuild_cpu_hours_placeholder": {adapter.challenge_id: 1.0},
        }
        adapters[digest] = adapter
    return adapters


def _stub_core(monkeypatch, rows):
    monkeypatch.setattr(
        retention,
        "_retain_private_pack_binding",
        lambda adapter, _p, _sid, _t, result: {
            **result,
            "evaluation_pack_digest": adapter.discovery.evaluation_pack_digest,
        },
    )

    def grade(adapter, submission_id, result, artifacts, evidence=None, regrade=None):
        row = rows[adapter.discovery.evaluation_pack_digest]
        if row is None:
            return {**result, "private_evaluation_state": "UNAVAILABLE"}
        return {
            **result,
            "private_evaluation_state": "BOUND_DEVELOPMENT_ONLY",
            "graded_row": row,
        }

    monkeypatch.setattr(retention, "_retain_selected_pack_evaluation", grade)


def _world(tmp_path):
    directory = tmp_path / "set-ledger"
    directory.mkdir(mode=0o700)
    ledger = AttemptLedger(directory / "attempts.sqlite3")
    return exam_cap.ExamCap(ledger), psr.SetResultStore(ledger)


def _run(fixture, adapters, world, set_key, *, submission="rtsk_1", block=360):
    cap, store = world
    return grading.grade_entry_on_set(
        cap,
        store,
        adapters,
        set_key=set_key,
        batches=BATCHES,
        entry_id=fixture.first["entry_id"],
        artifact_directory=fixture.artifacts,
        entry_directory=fixture.entries,
        hotkey=HOTKEY,
        challenge_id="electric-motor-magnetics",
        challenge_version="1.0",
        submission_id=submission,
        block=block,
        runner=fixture.runner,
    )


def test_a_retained_model_is_graded_on_every_batch_and_the_set_is_aggregated(
    tmp_path, monkeypatch
):
    fixture = _retained(tmp_path, monkeypatch)
    try:
        adapters = _batch_adapters(fixture, tmp_path, (0.5, 0.25))
        _stub_core(
            monkeypatch, {BATCHES[0]: _row(0.8, 0.4), BATCHES[1]: _row(0.6, 0.2)}
        )
        world = _world(tmp_path)
        key = common.pack_set_key(
            common.pack_set_document(
                "electric-motor-magnetics", "1.0", _contents(BATCHES)
            )
        )
        result = _run(fixture, adapters, world, key)
        assert result["status"] == psr.SCORED and result["batches"] == 2
        assert result["graded"]["score"] == pytest.approx(0.5)
        # Each batch was a REGRADE (never counted); the set spent one slot.
        cap, store = world
        assert (
            cap.count(
                hotkey=HOTKEY, challenge_id="electric-motor-magnetics", exam_key=key
            )
            == 1
        )
        rows = store.batch_rows(key, "rtsk_1")
        assert sorted(rows) == sorted(BATCHES)
        assert store.result(key, "rtsk_1") == result
    finally:
        fixture.provider.close()


def test_an_ungraded_batch_gives_no_set_result(tmp_path, monkeypatch):
    fixture = _retained(tmp_path, monkeypatch)
    try:
        adapters = _batch_adapters(fixture, tmp_path, (0.5, 0.25))
        _stub_core(monkeypatch, {BATCHES[0]: _row(0.8, 0.4), BATCHES[1]: None})
        world = _world(tmp_path)
        key = common.pack_set_key(
            common.pack_set_document(
                "electric-motor-magnetics", "1.0", _contents(BATCHES)
            )
        )
        result = _run(fixture, adapters, world, key)
        assert result["state"] == psr.UNAVAILABLE
        assert world[1].result(key, "rtsk_1") is None
        cap = world[0]
        assert (
            cap.count(
                hotkey=HOTKEY, challenge_id="electric-motor-magnetics", exam_key=key
            )
            == 0
        )
    finally:
        fixture.provider.close()


def test_a_batch_without_an_adapter_gives_no_set_result(tmp_path, monkeypatch):
    fixture = _retained(tmp_path, monkeypatch)
    try:
        adapters = _batch_adapters(fixture, tmp_path, (0.5, 0.25))
        del adapters[BATCHES[1]]
        _stub_core(
            monkeypatch, {BATCHES[0]: _row(0.8, 0.4), BATCHES[1]: _row(0.6, 0.2)}
        )
        world = _world(tmp_path)
        key = common.pack_set_key(
            common.pack_set_document(
                "electric-motor-magnetics", "1.0", _contents(BATCHES)
            )
        )
        result = _run(fixture, adapters, world, key)
        assert result == {
            "state": psr.UNAVAILABLE,
            "reason": "set_batch_adapter_missing",
        }
    finally:
        fixture.provider.close()


def _ladder_spy(monkeypatch):
    calls = []

    def record(adapter, submission_id, *, exam_key, exam_version, gates, graded):
        calls.append((submission_id, exam_key, exam_version, gates, graded))
        return "RECORDED"

    monkeypatch.setattr(retention, "_record_ladder", record)
    return calls


def test_the_operator_step_takes_owner_and_origin_from_the_task_and_records_once(
    tmp_path, monkeypatch
):
    fixture = _retained(tmp_path, monkeypatch)
    try:
        adapters = _batch_adapters(fixture, tmp_path, (0.5, 0.25))
        _stub_core(
            monkeypatch, {BATCHES[0]: _row(0.8, 0.4), BATCHES[1]: _row(0.6, 0.2)}
        )
        monkeypatch.setattr(exam_cap, "submission_block", lambda *_a: 360)
        ladder = _ladder_spy(monkeypatch)
        key = common.pack_set_key(
            common.pack_set_document(
                fixture.adapter.challenge_id, "1.0", _contents(BATCHES)
            )
        )
        result = grading.grade_set_entry(
            adapters,
            batches=BATCHES,
            set_key=key,
            entry_id=fixture.first["entry_id"],
            artifact_directory=fixture.artifacts,
            entry_directory=fixture.entries,
            runner=fixture.runner,
        )
        assert result["status"] == psr.SCORED
        assert result["ladder_feedback_state"] == "RECORDED"
        # The Ladder is recorded once, under the set key and the set's exam version.
        ((origin, exam_key, version, gates, graded),) = ladder
        assert origin == fixture.task_id and exam_key == key
        assert version == "ev-1" and gates == list(GATES)
        assert graded == result["graded"]
        # One slot for the owner of the retained task, under the set key.
        primary = adapters[BATCHES[0]]
        cap = exam_cap.ExamCap(primary.ledger, cadence=primary.exam_cadence)
        assert (
            cap.count(hotkey="miner", challenge_id=primary.challenge_id, exam_key=key)
            == 1
        )
    finally:
        fixture.provider.close()


def test_no_set_result_means_no_ladder_record(tmp_path, monkeypatch):
    fixture = _retained(tmp_path, monkeypatch)
    try:
        adapters = _batch_adapters(fixture, tmp_path, (0.5, 0.25))
        _stub_core(monkeypatch, {BATCHES[0]: _row(0.8, 0.4), BATCHES[1]: None})
        monkeypatch.setattr(exam_cap, "submission_block", lambda *_a: 360)
        ladder = _ladder_spy(monkeypatch)
        key = common.pack_set_key(
            common.pack_set_document(
                fixture.adapter.challenge_id, "1.0", _contents(BATCHES)
            )
        )
        result = grading.grade_set_entry(
            adapters,
            batches=BATCHES,
            set_key=key,
            entry_id=fixture.first["entry_id"],
            artifact_directory=fixture.artifacts,
            entry_directory=fixture.entries,
            runner=fixture.runner,
        )
        assert result["state"] == psr.UNAVAILABLE and not ladder
    finally:
        fixture.provider.close()
