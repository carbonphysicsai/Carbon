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

from carbon.challenge_registry import exam_registry, speed_gate
from carbon.challenge_validator import exam_cap, lean_recipe_retention

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
    except KeyError as refused:
        return type(refused).__name__


def grade(challenge, version):
    adapter = SimpleNamespace(challenge_id=challenge, challenge_version=version)
    return lean_recipe_retention._speed_ceiling(adapter)


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
        "f02 99.1": "SpeedGateUnregistered",
        "zz-synthetic 0.1": "SpeedGateUnregistered",
        "f02 2.5": 0.38,
    }
    assert out["grade"] == {"f02 99.1": None, "zz-synthetic 0.1": None, "f02 2.5": 0.38}


def test_an_unregistered_challenge_is_a_typed_refusal_that_old_readers_still_catch():
    with pytest.raises(speed_gate.SpeedGateUnregistered) as refused:
        speed_gate.ceiling_seconds("not-a-challenge", "1.0")
    assert isinstance(refused.value, KeyError)
    assert refused.value.code == "speed_gate_unregistered"
