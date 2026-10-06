"""PRACTICE-SAFETY-01: the safety metrics' material is disjoint from Track B.

The ticket's disjointness test. After rounding to the generators' precision
(4 dp), no public practice input point coincides with any Track B or EV
point:
- the battery practice cases against the EV1, EV2, EV4, EV5 (and Graphite
  run 5) decision conditions, EV4's protected grids and EV5's optimizer grids,
  compared on (t_amb_c, soc0) alone, which is stricter than the full input;
- the committed B4 practice decision set at the ruled distance from the
  ruled list, and by 4 dp coincidence from every point above;
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


def battery_ruled_conditions():
    """The B4 separation's ruled list (Test Lead, 2026-10-05): every EV1,
    EV2, EV4 and EV5 decision condition and every point of EV4's protected
    grids. EV5's protected grids are in `battery_protected_conditions` but
    not in the ruled list."""
    from carbon.battery.value import ev4_protected_conditions as ev4

    points = {tuple(map(float, p)) for p in ev4.PROTECTED}
    for ev in ("ev1", "ev2", "ev4", "ev5"):
        path = (
            REPO
            / f"carbon/battery/value/contracts/{ev}-charge-protocol-selection.v1.json"
        )
        scenarios = json.loads(path.read_text())["scenarios"]
        for role in ("development", "verification"):
            for scenario in scenarios[role]:
                points |= {(float(t), float(s)) for t, s in scenario["conditions"]}
    return points


def _committed_decision_conditions():
    return battery_safety.load_decision_set(REPO).conditions


def test_b4_s_committed_set_keeps_the_ruled_separation():
    ruled = battery_ruled_conditions()
    conditions = _committed_decision_conditions()
    assert len(conditions) == 6 and len(ruled) > 200
    assert battery_safety.decision_set_clear(conditions, sorted(ruled))
    # The set's own selection excluded exactly this list.
    from scripts.dev.battery import practice_decision_set as pds

    assert set(pds.excluded()) == ruled


def test_b4_s_committed_set_shares_no_point_with_any_ev_point():
    """The practice cases' own check (4 dp coincidence) over every protected
    point, EV5's protected grids included."""
    protected = {(_r(t), _r(s)) for t, s in battery_protected_conditions()}
    seen = {(_r(t), _r(s)) for t, s in _committed_decision_conditions()}
    assert len(seen) == 6 and not seen & protected


#: (condition, clear?) against the protected condition (14.0, 0.33), under
#: the Test Lead's ruling (2026-10-05): too close only inside BOTH bounds.
SEPARATION_CASES = (
    ((15.9, 0.35), False),  # inside both bounds
    ((12.1, 0.301), False),  # inside both bounds, the other side
    ((14.0, 0.33), False),  # the protected condition itself
    ((20.0, 0.33), True),  # outside in t_amb only
    ((14.0, 0.45), True),  # outside in soc0 only
    ((16.0, 0.34), True),  # exactly 2 degC away in t_amb
    ((17.0, 0.40), True),  # outside in both
)


def _separation_holds():
    protected = [(14.0, 0.33)]
    return all(
        battery_safety.decision_set_clear([condition], protected) is clear
        for condition, clear in SEPARATION_CASES
    )


def test_b4_refuses_a_point_inside_both_bounds_and_allows_one_outside_either():
    assert _separation_holds()
    protected = [(14.0, 0.33), (30.0, 0.10)]
    assert battery_safety.decision_set_clear([(20.0, 0.33), (30.0, 0.20)], protected)
    assert not battery_safety.decision_set_clear(
        [(20.0, 0.33), (29.0, 0.11)], protected
    )


def _and_of_separations(condition, protected):
    """The superseded reading: at least 2 degC in t_amb AND 0.03 in soc0."""
    return (
        abs(condition[0] - protected[0]) >= battery_safety.DECISION_SET_MIN_T_AMB_C
        and abs(condition[1] - protected[1]) >= battery_safety.DECISION_SET_MIN_SOC0
    )


def test_the_and_of_separations_mutant_is_killed(monkeypatch):
    monkeypatch.setattr(battery_safety, "_clear", _and_of_separations)
    assert not _separation_holds()
    assert _workable_grid_count() != 8422


def _workable_grid_count():
    """Grid points in the published box (0.1 degC x 0.001 soc0) that the
    separation check allows against every protected condition. Vectorized
    over t_amb; each soc0 column is decided by calling the check itself on
    the protected conditions near it, so a mutant check changes the count."""
    import numpy as np

    protected = sorted(battery_protected_conditions())
    t_grid = np.arange(50, 401) / 10
    clear = battery_safety._clear
    total = 0
    for s_index in range(50, 501):
        s = s_index / 1000
        allowed = np.ones(t_grid.shape, bool)
        for p in protected:
            # A condition differs from p only in t_amb along this column, so
            # the check's verdict at two t values decides the whole column:
            # one inside 2 degC of p, and one outside it.
            inside = clear((p[0], s), p)
            outside = clear((p[0] + 10.0, s), p)
            if inside and outside:
                continue
            near = np.abs(t_grid - p[0]) < battery_safety.DECISION_SET_MIN_T_AMB_C
            if not inside:
                allowed &= ~near
            if not outside:
                allowed &= near
        total += int(allowed.sum())
    return total


def test_the_ruled_separation_leaves_8422_workable_grid_points():
    assert _workable_grid_count() == 8422


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
