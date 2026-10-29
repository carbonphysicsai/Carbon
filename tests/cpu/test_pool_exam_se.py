"""The exam-total standard error of a pool-graded version (Validator ruling, 2026-10-29; exam-refresh audit gap 2):
a cluster bootstrap over TARGETS of the final pool total, 200 resamples seeded by the exam key, with the small-n
correction sqrt(n / (n - 1)), UNAVAILABLE when a gate failed or a set has fewer than four targets. Synthetic toy
Challenge values only (`test_pool_exam`); operator-only, nothing here reaches a miner surface."""

from __future__ import annotations

import math
import statistics
import sys
from pathlib import Path

import numpy as np
import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_pool_exam import (
    ARGUMENTS,
    CEILING,
    FAST,
    POLICIES,
    exam_rows,
    toy_binding,
)
from test_pool_plugin import fake_measure, good_serve, toy_target

from carbon.scoring import pool_exam as exam

KEY = "sha256:" + "ab" * 32
OTHER_KEY = "sha256:" + "cd" * 32


def four_target_sets():
    return (
        tuple(toy_target(f"a{i}", 20 + i) for i in range(4)),
        tuple(toy_target(f"b{i}", 40 + i) for i in range(4)),
    )


def measured(the_sets, serve=good_serve, speed=FAST):
    rows = exam_rows(the_sets)
    outputs = serve([r["inputs"] for r in rows])
    capture = {}
    result = exam.measure_pool(
        binding=toy_binding(),
        sets=the_sets,
        policies=POLICIES,
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        base_measure=fake_measure,
        base_arguments=ARGUMENTS,
        speed_call_seconds=speed,
        ceiling_seconds=CEILING,
        capture=capture,
    )
    return result, capture["se_basis"]


def test_the_captured_decomposition_recomposes_the_exams_own_total():
    result, basis = measured(four_target_sets())
    assert basis["gated"] is False
    assert [len(s) for s in basis["sets"]] == [4, 4]
    recomposed = exam.total_of_targets(basis, basis["sets"])
    assert recomposed == pytest.approx(0.5 * result["A"] + 0.5 * result["D"], abs=1e-12)
    assert basis["total"] == pytest.approx(recomposed, abs=1e-12)


def test_capture_never_changes_the_returned_grade_or_adds_a_surface():
    the_sets = four_target_sets()
    result, _basis = measured(the_sets)
    rows = exam_rows(the_sets)
    outputs = good_serve([r["inputs"] for r in rows])
    plain = exam.measure_pool(
        binding=toy_binding(),
        sets=the_sets,
        policies=POLICIES,
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        base_measure=fake_measure,
        base_arguments=ARGUMENTS,
        speed_call_seconds=FAST,
        ceiling_seconds=CEILING,
    )
    assert result == plain
    assert "se_basis" not in str(plain) and "se_basis" not in str(result)
    # The public view of a grade is unchanged: no per-target value, no SE.
    assert set(exam.public(plain)) <= {"status", "gates", "reasons", "total"} | set(
        exam.public(result)
    )


def test_the_se_is_deterministic_per_exam_key_and_follows_the_key():
    _result, basis = measured(four_target_sets())
    first, sizes = exam.target_bootstrap_se(basis, KEY)
    again, _ = exam.target_bootstrap_se(basis, KEY)
    other, _ = exam.target_bootstrap_se(basis, OTHER_KEY)
    assert first == again and sizes == [4, 4]
    assert first > 0 and other != first


def test_the_small_n_correction_is_applied():
    base = {
        "gated": False,
        "a_bank": 0.8,
        "c": 1.0,
        "a_rule": {"kind": "min"},
        "sets": [
            [{"d": d, "agen": None} for d in (0.1, 0.3, 0.5, 0.7)],
        ],
    }
    spread, sizes = exam.target_bootstrap_se(base, KEY, resamples=200)
    generator = np.random.Generator(
        np.random.PCG64(int.from_bytes(bytes.fromhex(KEY[7:])[:8], "big"))
    )
    totals = []
    for _ in range(200):
        order = generator.choice(4, size=4, replace=True)
        d = statistics.fmean(base["sets"][0][int(i)]["d"] for i in order)
        totals.append(0.5 * 0.8 + 0.5 * min(d, 1.0))
    raw = float(np.std(np.asarray(totals), ddof=1))
    assert sizes == [4]
    assert spread == pytest.approx(raw * math.sqrt(4 / 3), rel=1e-12)
    assert spread > raw


def test_identical_targets_give_a_zero_se():
    same = {"d": 0.4, "agen": 0.9}
    basis = {
        "gated": False,
        "a_bank": 0.7,
        "c": 1.0,
        "a_rule": {"kind": "mean"},
        "sets": [[dict(same) for _ in range(5)], [dict(same) for _ in range(5)]],
    }
    spread, _ = exam.target_bootstrap_se(basis, KEY)
    assert spread == pytest.approx(0.0, abs=1e-12)


def test_a_failed_gate_is_unavailable_gated():
    slow, basis = measured(four_target_sets(), speed=[CEILING * 3] * 20)
    assert slow["gates"][exam.SPEED_GATE] is False
    assert basis == {"gated": True}
    with pytest.raises(exam.ExamRefused) as refused:
        exam.target_bootstrap_se(basis, KEY)
    assert refused.value.code == "gated"


def test_fewer_than_four_targets_per_set_is_unavailable():
    _result, basis = measured(
        (
            tuple(toy_target(f"a{i}", 20 + i) for i in range(3)),
            tuple(toy_target(f"b{i}", 40 + i) for i in range(4)),
        )
    )
    with pytest.raises(exam.ExamRefused) as refused:
        exam.target_bootstrap_se(basis, KEY)
    assert refused.value.code == "too_few_targets"
    assert exam.SE_MIN_TARGETS == 4


def test_a_malformed_exam_key_is_refused():
    _result, basis = measured(four_target_sets())
    for key in ("", "ab" * 32, "sha256:zz"):
        with pytest.raises(exam.ExamRefused):
            exam.target_bootstrap_se(basis, key)


# --- the pool bootstrap beside the dual pack and the sidecar the pool grade writes -------------


class _FakeAdapter:
    """A pool-graded adapter whose `measure` fills `capture` from a real toy pool grade."""

    POOL_GRADED = True
    Refused = RuntimeError
    challenge_id = "toy"
    challenge_version = "1"

    def __init__(self, basis):
        self.basis = basis
        self.calls = []

    def measure(self, **kwargs):
        self.calls.append(kwargs)
        kwargs["capture"]["se_basis"] = self.basis
        return {}


def _ctx():
    from carbon.scoring import private_evaluation_source as source

    return {
        "refused": source.PrivateEvaluationSourceRefused,
        "roles": {"important_limit_definition": {}, "design_objective": {}},
        "n": 2,
        "width": 1,
        "values": [0.0, 1.0],
        "repeats": [[0.0, 1.0], [0.0, 1.0]],
        "definition": {},
        "train_raw": b"",
    }


def _patch_pool_inputs(monkeypatch):
    from carbon.development_session import single_call_timing
    from carbon.scoring import physical_dual_pack as pack
    from carbon.scoring import pool_exam_se

    monkeypatch.setattr(single_call_timing, "read_side_file", lambda raw: (FAST, True))
    monkeypatch.setattr(pack, "bank_rows", lambda bank, names: [{"cohort": "x"}] * 2)
    monkeypatch.setattr(pack, "_inputs", lambda adapter, **kwargs: _ctx())
    return pool_exam_se


def _call(module, adapter, report):
    return module.bootstrap_total_se(
        adapter,
        selected=None,
        public_root=None,
        private_root=None,
        entry={},
        job={},
        registration={},
        references=[],
        originals={"single_call_raw": b""},
        source_raw=b"",
        bank={},
        interface_names=["x"],
        exam_key=KEY,
        resamples=200,
        report=report,
    )


def test_the_pool_bootstrap_measures_once_with_capture_and_reports_targets(
    monkeypatch,
):
    module = _patch_pool_inputs(monkeypatch)
    _result, basis = measured(four_target_sets())
    adapter = _FakeAdapter(basis)
    report = {}
    spread = _call(module, adapter, report)
    assert spread == exam.target_bootstrap_se(basis, KEY)[0]
    assert report == {"n_targets": [4, 4]}
    (call,) = adapter.calls
    assert call["capture"] == {"se_basis": basis}
    assert call["speed_outputs_match"] is True


@pytest.mark.parametrize("basis", [{"gated": True}, None])
def test_the_pool_bootstrap_refuses_a_gated_grade_with_the_rulings_reason(
    monkeypatch, basis
):
    from carbon.scoring import private_evaluation_source as source

    module = _patch_pool_inputs(monkeypatch)
    with pytest.raises(source.PrivateEvaluationSourceRefused) as refused:
        _call(module, _FakeAdapter(basis), {})
    assert refused.value.code == "gated"


def test_the_physical_dual_pack_still_refuses_pool_versions_and_is_untouched():
    """The pool SE lives beside the dual pack, never inside it: that file is part of every producer digest."""
    from carbon.scoring import physical_dual_pack as pack

    source = Path(pack.__file__).read_text(encoding="utf-8")
    assert "bootstrap_pool_graded_unavailable" in source
    assert "pool_exam_se" not in source


def test_the_sidecar_records_measured_unavailable_and_never_fails_a_pool_grade(
    tmp_path, monkeypatch
):
    import json
    from types import SimpleNamespace

    from carbon.challenge_kit import physical_pack
    from carbon.challenge_validator import exam_rotation
    from carbon.challenge_validator import lean_recipe_retention as retention
    from carbon.scoring import physical_dual_pack as pack
    from carbon.scoring import pool_exam_se, sealed_batch_source
    from carbon.scoring import private_evaluation_source as source

    module = SimpleNamespace(POOL_GRADED=True)
    monkeypatch.setattr(source, "_physical_adapter", lambda cid, ver: module)
    monkeypatch.setattr(physical_pack, "development_bank", lambda cid, ver: {})
    monkeypatch.setattr(pack, "input_names", lambda m: ["x"])
    sealed_bank = {"pool": "material"}
    monkeypatch.setattr(
        sealed_batch_source,
        "resolve",
        lambda **kwargs: (sealed_bank, module),
    )
    adapter = SimpleNamespace(
        challenge_id="toy",
        challenge_version="1",
        discovery=SimpleNamespace(
            evaluation_pack_public_root=None, evaluation_pack_private_root=None
        ),
    )
    snapshot = SimpleNamespace(manifest_digest=KEY)
    registered = {
        "entry": {},
        "references": [],
        "evaluation_source_receipt_raw": b"",
    }
    source_doc = {"trusted_job": {}, "benchmark_registration": {}}
    scoring = {"models": [{"score": 0.5}]}

    def write(directory):
        retention._write_exam_se(
            adapter, snapshot, directory, registered, source_doc, {}, scoring
        )
        return json.loads((directory / exam_rotation.SE_SIDECAR).read_bytes())

    seen = {}

    def measured_se(_module, **kwargs):
        seen.update(kwargs)
        kwargs["report"]["n_targets"] = [4, 4]
        return 0.0123

    monkeypatch.setattr(pool_exam_se, "bootstrap_total_se", measured_se)
    (tmp_path / "a").mkdir()
    done = write(tmp_path / "a")
    assert done["status"] == "MEASURED", done
    assert done["standard_error"] == 0.0123
    assert done["n_targets"] == [4, 4] and done["exam_key"] == KEY
    assert (
        seen["bank"] is sealed_bank
    )  # graded on the sealed bank with the pool material
    sidecar = tmp_path / "a" / exam_rotation.SE_SIDECAR
    assert exam_rotation.read_se(sidecar)[0] == 0.0123

    def gated(_module, **kwargs):
        raise source.PrivateEvaluationSourceRefused("gated")

    monkeypatch.setattr(pool_exam_se, "bootstrap_total_se", gated)
    (tmp_path / "b").mkdir()
    done = write(tmp_path / "b")
    assert (done["status"], done["reason"]) == ("UNAVAILABLE", "gated")
    assert "standard_error" not in done

    def broken(_module, **kwargs):
        raise KeyError("nothing to see")

    monkeypatch.setattr(pool_exam_se, "bootstrap_total_se", broken)
    (tmp_path / "c").mkdir()
    done = write(tmp_path / "c")
    assert (done["status"], done["reason"]) == (
        "UNAVAILABLE",
        "bootstrap_failed:KeyError",
    )
    # A version that is not pool graded keeps the old behaviour: an unexpected error is raised.
    module.POOL_GRADED = False
    monkeypatch.setattr(pack, "bootstrap_total_se", broken)
    (tmp_path / "d").mkdir()
    with pytest.raises(KeyError):
        write(tmp_path / "d")
