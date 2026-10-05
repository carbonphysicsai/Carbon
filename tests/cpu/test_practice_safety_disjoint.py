"""PRACTICE-SAFETY-01: the safety metrics' material is disjoint from Track B.

The ticket's disjointness test. After rounding to the generators' precision
(4 dp), no public practice input point coincides with any Track B or EV
point:
- the battery practice cases against the EV1, EV2, EV4, EV5 (and Graphite
  run 5) decision conditions, EV4's protected grids and EV5's optimizer grids,
  compared on (t_amb_c, soc0) alone, which is stricter than the full input;
- the B4 practice decision set at the ruled distance (BLOCKED until committed);
- the cooling practice cases against the cooling study's designs x conditions;
- the motor practice cases against the motor study's designs x conditions.

It also checks the import graph: the metric code loads no scoring-set,
pool-store, seed-service or seed-journal, protected-condition, study or
campaign module. This test reads EV condition coordinates and study designs
to prove the disjointness; the metric code reads neither.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from carbon.battery import practice_safety as battery_safety
from carbon.battery.practice import PracticeSet as BatteryPractice
from carbon.cold_plate.domain import INPUTS as COOLING_INPUTS
from carbon.cold_plate.practice import PracticeSet as CoolingPractice
from carbon.motor.domain import INPUTS as MOTOR_INPUTS
from carbon.motor.practice import PracticeSet as MotorPractice

REPO = Path(__file__).resolve().parents[2]
DIGITS = 4


def _r(value):
    return round(float(value), DIGITS)


def battery_protected_conditions():
    """Every EV decision condition and protected grid, as (t_amb_c, soc0)."""
    from carbon.battery.value import ev4_protected_conditions as ev4
    from carbon.battery.value import ev5_protected_conditions as ev5

    grids = (
        ev4.EV4_DEVELOPMENT,
        ev4.EV4_VERIFICATION,
        ev4.EV4_MODEL,
        ev4.EV4_OPTIMIZER_VERIFICATION,
        ev5.EV5_DEVELOPMENT,
        ev5.EV5_VERIFICATION,
        ev5.EV5_MODEL,
        ev5.EV5_OPTIMIZER_VERIFICATION,
    )
    points = {(float(t), float(s)) for grid in grids for t, s in grid}
    contracts = sorted((REPO / "carbon/battery/value/contracts").glob("*.json"))
    named = {p.name for p in contracts}
    for ev in ("ev1", "ev2", "ev4", "ev5"):
        assert f"{ev}-charge-protocol-selection.v1.json" in named
    for path in contracts:
        scenarios = json.loads(path.read_text())["scenarios"]
        for role in ("development", "verification"):
            for scenario in scenarios[role]:
                points |= {(float(t), float(s)) for t, s in scenario["conditions"]}
    return points


def test_battery_practice_cases_share_no_condition_with_any_ev_point():
    protected = {(_r(t), _r(s)) for t, s in battery_protected_conditions()}
    assert len(protected) > 300
    practice = BatteryPractice.load(REPO)
    seen = {
        (_r(r["inputs"]["t_amb_c"]), _r(r["inputs"]["soc0"])) for r in practice.records
    }
    assert len(practice.records) == 200
    assert not seen & protected


def test_b4_is_blocked_until_its_decision_set_is_committed():
    if battery_safety.DECISION_SET_PATH is not None:
        pytest.fail("B4's decision set is committed: replace this with its check")
    practice = BatteryPractice.load(REPO)
    document = battery_safety.safety({}, practice)
    assert document["metrics"]["B4"] == "BLOCKED: practice decision set not committed"


def test_the_b4_separation_is_both_coordinates_from_every_protected_condition():
    protected = [(14.0, 0.33)]
    assert battery_safety.decision_set_clear([(17.0, 0.40)], protected)
    assert battery_safety.decision_set_clear([(12.0, 0.30)], protected)
    # Far in one coordinate only is not far enough: the ruling says AND.
    assert not battery_safety.decision_set_clear([(20.0, 0.33)], protected)
    assert not battery_safety.decision_set_clear([(14.0, 0.45)], protected)
    assert not battery_safety.decision_set_clear([(15.9, 0.40)], protected)
    assert not battery_safety.decision_set_clear([(17.0, 0.35)], protected)


def _study_points(path, inputs):
    study = json.loads((REPO / path).read_text())
    points = set()
    for design in study["designs"]:
        for condition in study["conditions"]:
            values = {**design["values"], **condition["values"]}
            assert set(values) == set(inputs)
            points.add(tuple(_r(values[k]) for k in inputs))
    assert len(points) == len(study["designs"]) * len(study["conditions"])
    return points


def test_cooling_practice_cases_are_not_study_points():
    from carbon.cold_plate.practice_safety import STUDY_SOURCE

    study = _study_points(STUDY_SOURCE, COOLING_INPUTS)
    practice = CoolingPractice.load(REPO)
    seen = {tuple(_r(r["inputs"][k]) for k in COOLING_INPUTS) for r in practice.records}
    assert len(seen) == 100
    assert not seen & study


def test_motor_practice_cases_are_not_study_points():
    from carbon.motor.practice_safety import STUDY_SOURCE

    study = _study_points(STUDY_SOURCE, MOTOR_INPUTS)
    practice = MotorPractice.load(REPO)
    seen = {tuple(_r(r["inputs"][k]) for k in MOTOR_INPUTS) for r in practice.records}
    assert len(seen) == 30
    assert not seen & study


#: Modules the metric code must never load: the scoring set, pools, seed
#: service and journal, protected conditions, Track B, studies, campaigns and
#: the value modules that import the scoring set.
FORBIDDEN = (
    "carbon.battery.value.scoring",
    "carbon.battery.value.panel",
    "carbon.battery.value.margins",
    "carbon.battery.value.near",
    "carbon.battery.value.false_acceptance",
    "carbon.battery.value.admissibility",
    "carbon.battery.value.ev5",
    "carbon.battery.value.ev5_run",
    "carbon.battery.value.ev4_protected_conditions",
    "carbon.battery.value.ev5_protected_conditions",
    "carbon.battery.pool_store",
    "carbon.battery.seeds",
    "carbon.battery.track_a",
    "carbon.battery.deployment",
    "carbon.cold_plate.customer_decision",
    "carbon.cold_plate.decision_study",
    "carbon.cold_plate.track_b",
    "carbon.cold_plate.population",
    "carbon.motor.customer_decision",
    "carbon.motor.decision_study",
    "carbon.motor.track_b",
    "carbon.motor.population",
    "carbon.motor.q1_panel",
)
FORBIDDEN_PARTS = ("campaign", "journal", "admission_study", "pool_store", "truth")


def test_the_metric_code_imports_no_scoring_set_pool_seed_or_study_module():
    probe = (
        "import json, sys\n"
        "import carbon.practice_safety_feedback\n"
        "import carbon.battery.practice_safety\n"
        "import carbon.cold_plate.practice_safety\n"
        "import carbon.motor.practice_safety\n"
        "print(json.dumps(sorted(m for m in sys.modules if m.startswith('carbon'))))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(REPO)},
    )
    loaded = set(json.loads(out.stdout))
    assert "carbon.battery.practice_safety" in loaded
    assert not loaded & set(FORBIDDEN)
    assert not [m for m in loaded if any(part in m for part in FORBIDDEN_PARTS)]
