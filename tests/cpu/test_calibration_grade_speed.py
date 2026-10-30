"""A pool-graded version cannot be timed by the calibration tool: it grades with a labelled placeholder, never a
measured pass, and the aggregates do not report the speed gate as a result."""

from __future__ import annotations

from typing import ClassVar

from carbon.challenge_registry import speed_gate
from carbon.challenge_validator import calibration_grade as cg
from carbon.scoring import pool_exam
from tests.cpu.test_calibration_grade import _Adapter, _artifact, _grade


class _PoolAdapter(_Adapter):
    CHALLENGE = "f02"
    POOL_GRADED = True
    seen: ClassVar[list] = []

    @classmethod
    def measure(cls, **kw):
        cls.seen.append(kw.get("speed_call_seconds"))
        out = _Adapter.measure(**kw)
        return {**out, "gates": {**out["gates"], "speed": True}}


def test_a_pool_graded_grade_passes_the_ceiling_safe_placeholder_and_labels_it(
    tmp_path,
):
    _PoolAdapter.seen.clear()
    result = _grade_with(_PoolAdapter, _artifact(tmp_path))
    (timings,) = _PoolAdapter.seen[-1:]
    assert len(timings) == pool_exam.SPEED_SAMPLE
    assert set(timings) == {speed_gate.ceiling_seconds("f02")}
    assert result["speed_gate"] == cg.SPEED_NOT_MEASURED == "NOT_MEASURED_PLACEHOLDER"
    assert "speed" not in result["gates"]
    assert result["total"] is not None


def test_a_version_that_is_not_pool_graded_is_unchanged(tmp_path):
    result, _ = _grade(_artifact(tmp_path))
    assert "speed_gate" not in result and "speed" not in result["gates"]


def _grade_with(adapter, artifact_dir):
    from carbon.scoring import dual_score as dual
    from carbon.scoring.physical_dual_pack import METRICS
    from tests.cpu.test_calibration_grade import _bank
    from tests.cpu.test_dual_score import fixture as dual_fixture

    body, _ = dual_fixture()
    for leg in ("A", "D"):
        body["legs"][leg]["components"][0]["metric"] = METRICS[leg]
    body["hard_gates"] = [*body["hard_gates"], "speed"]
    body["challenge"] = adapter.CHALLENGE
    return cg.grade(
        adapter=adapter,
        bank=_bank(),
        pack=dual.register_pack(body),
        definition={},
        limits={},
        objective={},
        train_raw=b"",
        interface_names=("a", "b", "c"),
        infer=lambda inputs: [[1.0] * 32 for _ in range(len(inputs))],
        artifact=cg.load_artifact(artifact_dir),
        challenge="f02",
    )
