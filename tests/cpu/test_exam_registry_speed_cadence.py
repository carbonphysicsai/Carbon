"""The speed gate and the cadence read a new version's values from its exam registry row, and no live value moves.

The literals were read from main before the change (Motor 1.8, Cooling 1.8, the Motor 1.9 stack, RB 2.0, F08 1.7, F02
2.5). Every registry case runs in a fresh interpreter with synthetic rows.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_kit import version_registry
from carbon.challenge_registry import exam_registry, speed_gate
from carbon.challenge_validator import exam_cap, lean_recipe_retention
from carbon.scoring import practice_speed

REPOSITORY = Path(__file__).resolve().parents[2]
MOTOR = "electric-motor-magnetics"
CEILINGS = {
    "f02": 0.38,
    "f08-ribbed-bracket": 2.08,
    "chip-cold-plate": 2.84,
    MOTOR: 3.3,
}
LIVE = [
    (MOTOR, "1.8"),
    (MOTOR, "1.9"),
    ("chip-cold-plate", "1.8"),
    ("f08-ribbed-bracket", "1.7"),
    ("f08-ribbed-bracket", "2.0"),
    ("f02", "2.5"),
]
DIGEST = "sha256:" + "a" * 64

_PROGRAM = r"""
import json, sys
from types import SimpleNamespace
from carbon.challenge_kit import version_overlay
from carbon.challenge_registry import exam_registry, speed_gate
from carbon.challenge_validator import exam_cap, lean_recipe_retention
before = exam_cap.registered_cadence()
version_overlay.install(path=sys.argv[1])
exam_registry.install(sys.argv[2])


def ask(function, *args):
    try:
        return function(*args)
    except (KeyError, ValueError) as refused:
        return type(refused).__name__


def grade(challenge, version):
    adapter = SimpleNamespace(challenge_id=challenge, challenge_version=version)
    try:
        return lean_recipe_retention._speed_ceiling(adapter)
    except lean_recipe_retention.RetentionUnavailable as failure:
        return "unavailable: " + str(failure)


pairs = json.loads(sys.argv[3])
print(json.dumps({
    "before": before,
    "after": exam_cap.registered_cadence(),
    "file": exam_cap.registered_cadence(exam_cap.REGISTRY),
    "ceilings": {" ".join(p): ask(speed_gate.ceiling_seconds, *p) for p in pairs},
    "grade": {" ".join(p): grade(*p) for p in pairs},
    "family": ask(speed_gate.ceiling_seconds, "zz-synthetic"),
}))
"""


def _entry(challenge, version):
    return {
        "challenge_id": challenge,
        "version": version,
        "train": "zz-synthetic-train-v1",
        "allowlist": "v8",
        "step_caps": False,
        "pack_version": "zz-synthetic-normal-construction-development-1",
        "development_evaluation": None,
        "sealed_evaluation": "zz-synthetic-pool-sealed-v1",
        "campaign": "catalog",
    }


def _run(tmp_path, rows, pairs):
    versions = [("zz-synthetic", "0.1"), ("zz-synthetic", "0.2"), ("f02", "99.1")]
    overlay = tmp_path / "overlay.json"
    document = {
        "schema": "carbon.challenge-kit.version-overlay.v1",
        "versions": {f"{c} {v}": _entry(c, v) for c, v in versions},
    }
    overlay.write_text(json.dumps(document), encoding="utf-8")
    registry = tmp_path / "exam_registry.json"
    document = {"schema": exam_registry.SCHEMA, "source": "test", "exams": rows}
    registry.write_text(json.dumps(document), encoding="utf-8")
    argv = [str(overlay), str(registry), json.dumps(pairs)]
    done = subprocess.run(
        [sys.executable, "-c", _PROGRAM, *argv],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=600,
        check=True,
    )
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_every_live_ceiling_is_the_value_main_had():
    assert speed_gate.ceilings() == CEILINGS
    assert speed_gate.SOLVER_SECONDS_PER_DESIGN == {
        "f02": 190,
        "f08-ribbed-bracket": 1040,
        "chip-cold-plate": 1420,
        MOTOR: 1650,
    }
    for challenge, version in LIVE:
        # the committed registry values none of them: each keeps its Challenge's value
        assert (challenge, version) not in exam_registry.keys(
            "solver_seconds_per_design"
        )
        assert speed_gate.ceiling_seconds(challenge) == CEILINGS[challenge]
        assert speed_gate.ceiling_seconds(challenge, version) == CEILINGS[challenge]
        adapter = SimpleNamespace(challenge_id=challenge, challenge_version=version)
        assert lean_recipe_retention._speed_ceiling(adapter) == CEILINGS[challenge]


def test_the_cadence_in_force_is_the_files_for_every_challenge_it_values():
    in_force = exam_cap.registered_cadence()
    committed = exam_cap.registered_cadence(exam_cap.REGISTRY)
    hours = in_force.pop("rebuild_gpu_lane_hours")
    own = committed.pop("rebuild_gpu_lane_hours")
    assert in_force == committed
    assert {k: hours[k] for k in own} == own
    assert set(hours) - set(own) == {
        c for c, _ in exam_registry.keys("rebuild_gpu_lane_hours") if c not in own
    }


def test_a_new_family_takes_its_rows_values_and_moves_no_other(tmp_path):
    def row(hours, solver):
        return {
            "rebuild_gpu_lane_hours": {"value": hours, "measurement_digest": DIGEST},
            "solver_seconds_per_design": {"value": solver, "source": "synthetic"},
        }

    rows = {"zz-synthetic 0.2": row(0.03, 200), "zz-synthetic 0.1": row(0.02, 100)}
    pairs = [["zz-synthetic", "0.1"], ["zz-synthetic", "0.2"], [MOTOR, "1.8"]]
    out = _run(tmp_path, rows, pairs)
    assert out["ceilings"] == {
        "zz-synthetic 0.1": 0.2,
        "zz-synthetic 0.2": 0.4,
        f"{MOTOR} 1.8": 3.3,
    }
    assert out["grade"] == out["ceilings"]
    # a family with no value of its own has no ceiling without a version: refused typed, never another family's
    assert out["family"] == "SpeedGateUnregistered"
    # the newest row values the family; the file's Challenges and its every other field are unmoved
    before, after = out["before"], out["after"]
    assert after["rebuild_gpu_lane_hours"].pop("zz-synthetic") == 0.03
    assert after == before
    assert "zz-synthetic" not in out["file"]["rebuild_gpu_lane_hours"]
    # `sum_t` is the one reader that iterates every Challenge; the owner's set allowance does not read it
    assert before["daily_allowance"] == after["daily_allowance"]


def test_a_row_for_a_valued_challenge_moves_its_own_version_only(tmp_path):
    rows = {
        "f02 99.1": {
            "rebuild_gpu_lane_hours": {"value": 9, "measurement_digest": DIGEST},
            "solver_seconds_per_design": {"value": 50, "source": "synthetic"},
        }
    }
    out = _run(tmp_path, rows, [["f02", "99.1"], ["f02", "2.5"]])
    assert out["ceilings"] == {"f02 99.1": 0.1, "f02 2.5": 0.38}
    assert out["after"] == out["before"]


def test_a_malformed_row_refuses_its_version_and_never_takes_the_challenges_value(
    tmp_path,
):
    bad = {"solver_seconds_per_design": {"value": 0, "source": "synthetic"}}
    rows = {"f02 99.1": bad, "zz-synthetic 0.1": bad}
    pairs = [["f02", "99.1"], ["zz-synthetic", "0.1"], ["f02", "2.5"]]
    out = _run(tmp_path, rows, pairs)
    assert out["ceilings"] == {
        "f02 99.1": "SpeedGateRefused",
        "zz-synthetic 0.1": "SpeedGateRefused",
        "f02 2.5": 0.38,
    }
    # Carbon's failure, never a stage with no ceiling and never the candidate's
    refused = "unavailable: speed_gate_row_refused"
    assert out["grade"] == {
        "f02 99.1": refused,
        "zz-synthetic 0.1": refused,
        "f02 2.5": 0.38,
    }
    kept = lean_recipe_retention._KEPT_UNAVAILABLE
    assert speed_gate.SpeedGateRefused.code not in kept


@pytest.mark.parametrize(("bad", "valued"), [("0.2", False), ("0.1", True)])
def test_a_refused_newest_row_leaves_its_challenge_unvalued(tmp_path, bad, valued):
    def row(hours):
        return {
            "rebuild_gpu_lane_hours": {"value": hours, "measurement_digest": DIGEST}
        }

    rows = {f"zz-synthetic {v}": row(0.02) for v in ("0.1", "0.2")}
    rows[f"zz-synthetic {bad}"] = row(0)
    out = _run(tmp_path, rows, [[MOTOR, "1.8"]])
    hours = out["after"]["rebuild_gpu_lane_hours"]
    assert hours.get("zz-synthetic") == (0.02 if valued else None)
    assert {k: v for k, v in hours.items() if k != "zz-synthetic"} == (
        out["before"]["rebuild_gpu_lane_hours"]
    )


def test_no_committed_row_gives_a_valued_challenge_a_second_ceiling():
    """Until every reader asks by version (pool_gates is left, a design-time reader), a version of a Challenge valued in
    code may not carry its own seconds: two readers would name two ceilings. The head that moves the last reader deletes
    this test (review-b 6404)."""
    families = {c for c, _ in exam_registry.keys("solver_seconds_per_design")}
    assert not families & set(speed_gate.SOLVER_SECONDS_PER_DESIGN)


def test_every_version_the_code_serves_has_one_ceiling_asked_either_way():
    """The grade (`PoolVariant.measure`) and practice ask by version: no served version's number moves."""
    asked = [
        key
        for key in sorted(version_registry.keys())
        if key[0] in speed_gate.SOLVER_SECONDS_PER_DESIGN
    ]
    assert {c for c, _ in asked} == set(speed_gate.SOLVER_SECONDS_PER_DESIGN)
    assert (MOTOR, "1.8") in asked
    differ = [
        key
        for key in asked
        if speed_gate.ceiling_seconds(*key) != speed_gate.ceiling_seconds(key[0])
    ]
    assert differ == []


@pytest.mark.parametrize(
    ("challenge", "version"), [(MOTOR, "1.8"), ("zz-synthetic", "0.1")]
)
def test_the_grade_asks_the_ceiling_by_its_own_version(monkeypatch, challenge, version):
    """`PoolVariant.measure` itself, with `measure_pool` a stand-in (no score is computed)."""
    from carbon.scoring import pool_exam, pool_version

    asked, seen = [], {}
    monkeypatch.setattr(
        speed_gate, "ceiling_seconds", lambda *a: asked.append(a) or 0.5
    )
    monkeypatch.setattr(pool_exam, "measure_pool", lambda **a: seen.update(a) or {})
    for name, value in (
        ("registered_policies", SimpleNamespace()),
        ("menu_tasks", None),
        ("sealed_region", None),
        ("official_binding", None),
        ("check_material", {"input_dtype": "float64"}),
        ("registered_a_multiplier", 1.0),
    ):
        monkeypatch.setattr(pool_version, name, lambda *_a, _v=value, **_k: _v)
    adapter = object.__new__(pool_version.PoolVariant)
    adapter._module = SimpleNamespace(measure=None)
    adapter._kind, adapter._challenge_id, adapter.VERSION = "kind", challenge, version
    adapter.measure(
        bank_rows=[],
        outputs=[],
        repeats=[],
        definition={pool_version.POOL_KEY: {"sets": []}},
        limits={},
        objective={},
        train_raw=b"",
        names=(),
        speed_call_seconds=[0.1],
    )
    assert asked == [(challenge, version)]
    assert seen["ceiling_seconds"] == 0.5


def test_practice_reads_the_version_s_own_seconds(monkeypatch):
    plain = practice_speed.speed_block("motor", seconds=2.0, designs=1)
    for version in ("1.7", "1.8"):
        assert plain == practice_speed.speed_block(
            "motor", seconds=2.0, designs=1, version=version
        )
    asked = []

    def own(challenge, version, field):
        asked.append((challenge, version, field))
        return {"value": 500}

    monkeypatch.setattr(exam_registry, "require", own)
    block = practice_speed.speed_block("motor", seconds=2.0, designs=1, version="9.9")
    assert block["ceiling_seconds_per_design"] == 1.0
    assert block["solver_seconds_per_design"] == 500
    assert block["within_ceiling"] is False
    figures = practice_speed.per_call_figures("motor", [0.5], version="9.9")
    assert figures["per_call_within_ceiling"] is True
    assert set(asked) == {(MOTOR, "9.9", "solver_seconds_per_design")}


def test_an_unreadable_row_never_fails_a_practice(monkeypatch):
    def refuse(*_a):
        raise exam_registry.ExamRowRefused("row")

    monkeypatch.setattr(exam_registry, "require", refuse)
    block = practice_speed.speed_block("motor", seconds=2.0, designs=1, version="9.9")
    assert block is None


def test_an_unregistered_challenge_is_a_typed_refusal_that_old_readers_still_catch():
    with pytest.raises(speed_gate.SpeedGateUnregistered) as refused:
        speed_gate.ceiling_seconds("not-a-challenge", "1.0")
    assert isinstance(refused.value, KeyError)
    assert refused.value.code == "speed_gate_unregistered"
