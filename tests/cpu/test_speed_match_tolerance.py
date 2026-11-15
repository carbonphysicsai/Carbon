"""The speed gate's match for a vmap-64 version (owner, Sun 15 Nov 2026 ~11:1x CST via the Lead: "Just don't make some
barely fitting rule that causes things to fail and our system to be fragile."; CV-Motor-B ruling S2).

Claims: the committed values row carries CV-Motor-B's posted values (rtol 1e-9, atol 1e-9), and a null or malformed row
refuses the vmap-64 version, at
serve and at grade time (typed, version-wide, no automatic retry), never exact and never a guess; within the registered
wide tolerance the timed calls match; beyond it the stage raises Carbon's typed `speed_outputs_disagree`, which the
grader gives back as FAILED_INFRA (slot released, one automatic retry), and no side file (so no speed mismatch) ever
reaches the scorer; every other version still compares exactly, as before. The tolerance values below are SYNTHETIC
fixtures, not the registered ones.
"""

from __future__ import annotations

import inspect
import json

import pytest
from test_single_call_layer_b import _run, stage  # noqa: F401 - the stage fixture

from carbon.challenge_validator import auto_retry, direct_receiver, speed_match
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.development_session import single_call_timing

MOTOR_18 = ("electric-motor-magnetics", "1.8")
FIXTURE = {"rtol": 1e-9, "atol": 1e-12}


def _registry(tmp_path, row=FIXTURE, key="electric-motor-magnetics 1.8", **changes):
    document = {"schema": speed_match.SCHEMA, "rows": {key: row}, **changes}
    path = tmp_path / "speed_match_tolerance.json"
    path.write_text(json.dumps(document))
    return path


def test_the_committed_row_is_cv_motors_posted_values(tmp_path):
    """CV-Motor-B, team board Sun 15 Nov 2026: rtol 1e-9, atol 1e-9 on all 240 values."""
    document = json.loads(speed_match.REGISTRY.read_bytes())
    assert document["schema"] == speed_match.SCHEMA
    assert document["rows"] == {
        "electric-motor-magnetics 1.8": {"rtol": 1e-9, "atol": 1e-9}
    }
    assert speed_match.tolerance(*MOTOR_18) == (1e-9, 1e-9)
    speed_match.require_served(*MOTOR_18)
    # a null row (as before the values were posted) still refuses the version
    null = _registry(tmp_path, {"rtol": None, "atol": None})
    with pytest.raises(speed_match.SpeedMatchUnregistered) as refused:
        speed_match.tolerance(*MOTOR_18, path=null)
    assert refused.value.code == speed_match.UNREGISTERED
    # every other version: no tolerance, the exact comparison as before
    for key in (
        ("electric-motor-magnetics", "1.6"),
        ("chip-cold-plate", "1.8"),
        ("c", "1.5"),
    ):
        assert speed_match.tolerance(*key) is None
        speed_match.require_served(*key)


def test_a_registered_row_is_read_exactly(tmp_path):
    assert speed_match.tolerance(*MOTOR_18, path=_registry(tmp_path)) == (1e-9, 1e-12)
    assert speed_match.tolerance(
        *MOTOR_18, path=_registry(tmp_path, {"rtol": 0, "atol": 1e-10})
    ) == (0.0, 1e-10)


@pytest.mark.parametrize(
    "row",
    [
        {"rtol": None, "atol": None},
        {"rtol": 1e-9, "atol": None},
        {"rtol": 1e-9},
        {"rtol": 1e-9, "atol": 1e-12, "extra": 1},
        {"rtol": -1e-9, "atol": 1e-12},
        {"rtol": float("inf"), "atol": 1e-12},
        {"rtol": True, "atol": 1e-12},
        {"rtol": "1e-9", "atol": 1e-12},
        {"rtol": 0, "atol": 0.0},  # zero is exact equality: ruled out
        {
            "rtol": 1e-9,
            "atol": 0,
        },  # a zero atol: a value near zero needs exact equality
        {"rtol": 1e-9, "atol": -1e-12},
        "HUMAN_INPUT",
    ],
)
def test_a_null_or_malformed_row_fails_closed(tmp_path, row):
    with pytest.raises(speed_match.SpeedMatchUnregistered):
        speed_match.tolerance(*MOTOR_18, path=_registry(tmp_path, row))


def test_a_missing_or_foreign_registry_fails_closed(tmp_path):
    for path in (
        tmp_path / "absent.json",
        _registry(tmp_path, key="electric-motor-magnetics 1.6"),
        _registry(tmp_path, schema="other"),
    ):
        with pytest.raises(speed_match.SpeedMatchUnregistered):
            speed_match.tolerance(*MOTOR_18, path=path)
    (tmp_path / "bad.json").write_text("not json")
    with pytest.raises(speed_match.SpeedMatchUnregistered):
        speed_match.tolerance(*MOTOR_18, path=tmp_path / "bad.json")


def test_the_combined_tolerance_per_value():
    tolerance = (1e-9, 1e-12)
    graded = [[0.0, 5.0, -3.0] for _ in range(4)]
    indices = [1, 3]

    def timed(offset, column=1):
        rows = [list(graded[i]) for i in indices]
        rows[1][column] += offset
        return rows

    assert speed_match.outputs_agree(timed(0.0), graded, indices, tolerance)
    assert speed_match.outputs_agree(
        timed(4e-9), graded, indices, tolerance
    )  # 5e-9 + 1e-12 allowed at 5.0
    assert not speed_match.outputs_agree(timed(1e-8), graded, indices, tolerance)
    assert speed_match.outputs_agree(
        timed(5e-13, 0), graded, indices, tolerance
    )  # atol at 0.0
    assert not speed_match.outputs_agree(timed(1e-11, 0), graded, indices, tolerance)
    for bad in (float("nan"), float("inf"), -float("inf")):
        rows = timed(0.0)
        rows[0][2] = bad
        assert not speed_match.outputs_agree(rows, graded, indices, tolerance)
    assert not speed_match.outputs_agree(
        [row[:2] for row in timed(0.0)], graded, indices, tolerance
    )
    assert not speed_match.outputs_agree(timed(0.0)[:1], graded, indices, tolerance)
    assert not speed_match.outputs_agree([[1.0, [2.0]]] * 2, graded, indices, tolerance)
    nan_graded = [list(row) for row in graded]
    nan_graded[3][0] = float("nan")
    assert not speed_match.outputs_agree(
        [list(graded[1]), list(graded[3])], nan_graded, indices, tolerance
    )


def _as_motor_18(stage_fixture, monkeypatch, path):
    stage_fixture.adapter.discovery._material["construction_kit"].update(
        {"id": MOTOR_18[0], "version": MOTOR_18[1]}
    )
    monkeypatch.setattr(speed_match, "REGISTRY", path)


def _shift(stage_fixture, offset):
    stage_fixture.artifacts["predictions.json"] = json.dumps(
        [[v[0] + offset] for v in stage_fixture.graded]
    ).encode()


def test_within_the_tolerance_the_vmap64_stage_records_a_match(
    stage, monkeypatch, tmp_path  # noqa: F811
):
    _as_motor_18(stage, monkeypatch, _registry(tmp_path))
    _shift(stage, 1e-13)  # within atol at every value, not bit equal
    seconds, match = single_call_timing.read_side_file(_run(stage))
    assert seconds == [0.02] * single_call_timing.SAMPLE and match is True


def test_beyond_the_tolerance_the_stage_is_carbons_never_a_speed_fail(
    stage, monkeypatch, tmp_path  # noqa: F811
):
    _as_motor_18(stage, monkeypatch, _registry(tmp_path))
    _shift(stage, 1e-6)
    with pytest.raises(retention.RetentionUnavailable, match=speed_match.DISAGREE):
        _run(stage)
    # no side file: the scorer can never read a speed mismatch for a vmap-64 version
    assert not (stage.private_dir / "single-call.json").exists()
    assert len(stage.calls) == 1


def test_an_unset_tolerance_leaves_the_grade_unavailable_before_anything_runs(
    stage, monkeypatch, tmp_path  # noqa: F811
):
    stage.adapter.discovery._material["construction_kit"].update(
        {"id": MOTOR_18[0], "version": MOTOR_18[1]}
    )
    monkeypatch.setattr(
        speed_match, "REGISTRY", _registry(tmp_path, {"rtol": None, "atol": None})
    )  # an unset row
    with pytest.raises(retention.RetentionUnavailable, match=speed_match.UNREGISTERED):
        _run(stage)
    assert stage.calls == [] and not (stage.private_dir / "single-call.json").exists()


def test_every_other_version_still_compares_exactly(stage):  # noqa: F811
    stage.artifacts["predictions.json"] = json.dumps(
        [[v[0] + 1e-13] for v in stage.graded]
    ).encode()
    _, match = single_call_timing.read_side_file(_run(stage))
    assert match is False  # recorded for the gate, as before


def test_the_failure_codes_retry_as_ruled():
    """The real counted-grade path to the grader's FAILED marker is `test_vmap64_carbon_failures`."""
    assert (
        auto_retry.retryable(speed_match.DISAGREE) is True
    )  # transient: one retry for the task's life
    # an unset tolerance is version-wide: the slot is returned, no automatic retry into the same gap
    assert auto_retry.retryable(speed_match.UNREGISTERED) is False


def test_the_receiver_refuses_to_serve_a_vmap64_version_without_its_tolerance(
    monkeypatch, tmp_path
):
    unset = tmp_path / "unset"
    unset.mkdir()
    monkeypatch.setattr(
        speed_match, "REGISTRY", _registry(unset, {"rtol": None, "atol": None})
    )
    with pytest.raises(direct_receiver.ReceiverUnavailable) as refused:
        direct_receiver._require_speed_match(*MOTOR_18)
    assert refused.value.code == speed_match.UNREGISTERED
    direct_receiver._require_speed_match("electric-motor-magnetics", "1.6")
    monkeypatch.setattr(speed_match, "REGISTRY", _registry(tmp_path))
    direct_receiver._require_speed_match(*MOTOR_18)
    monkeypatch.undo()
    direct_receiver._require_speed_match(*MOTOR_18)  # the committed row serves
    source = inspect.getsource(direct_receiver.serve)
    assert source.index(
        "_require_speed_match(challenge.challenge_id, challenge.version)"
    ) < source.index("with owner_lock(root):")


@pytest.fixture(autouse=True)
def _vmap64_machinery_opted_in(monkeypatch):
    """Motor 1.8 is NOT a vmap-64 version since the owner's 116 rollback to A9 behaviour (Sun 15 Nov 2026; it grades
    with the per-case compiled program, tests/cpu/test_motor18_rollback_program.py). These tests exercise the dormant
    vmap-64 machinery with Motor 1.8 opted back in."""
    from carbon.development_session import direct_graph_construction_worker

    monkeypatch.setattr(
        direct_graph_construction_worker,
        "VMAP64_INFERENCE_VERSIONS",
        frozenset({("electric-motor-magnetics", "1.8")}),
    )
