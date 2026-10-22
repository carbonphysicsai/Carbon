"""Motor's sealed grid exam (OWNER-MOTOR-EXAM-GRID-01; Validator ruling
VALIDATOR_RULING_MOTOR_GRID_SPLIT_20261022): a placed 5 designs x 6 conditions
batch beside the placed-30 family, selected by the deployment schema, whose pack
carries one grid cohort with design and condition ids, and whose post-solve
decision check refuses a grid that cannot measure design value."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_motor_hidden import Solver
from test_motor_sealed_family import records_for

from carbon.challenge_kit import motor_sealed_pack as pack
from carbon.challenge_validator import motor_sealed as placed
from carbon.challenge_validator import motor_sealed_grid as grid
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator.family_source import FamilySource
from carbon.challenge_validator.motor_sealed_source import (
    MotorSealedBatchSource,
    MotorSealedGridBatchSource,
    motor_sealed_grid_family,
    motor_source_for,
)
from carbon.motor_grid_exam import decision_check as dc
from carbon.motor_grid_exam import population

MOTOR = "electric-motor-magnetics"
SEED = 3


def write_deployment(path, schema, **fields):
    path.parent.mkdir(mode=0o700, exist_ok=True)
    path.write_text(json.dumps({"schema": schema, **fields}))
    path.chmod(0o600)
    return path


@pytest.fixture(scope="module")
def drawn_grid():
    cases, tries = population.draw(random.Random(SEED), population.CELLS)
    return cases, tries


def document(cases):
    return {
        "schema": grid.DOCUMENT_SCHEMA,
        "challenge": {"id": MOTOR, "version": "1.1"},
        "role": "grid",
        "kind": "screening",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"g{i:02d}", "inputs": c} for i, c in enumerate(cases)],
    }


def test_the_registration_is_the_grid_family_beside_the_placed_one():
    family = motor_sealed_grid_family()
    assert (family.challenge_id, family.challenge_version) == (MOTOR, "1.1")
    assert family.population_version == population.POPULATION_VERSION
    assert family.population_version == "carbon.motor.sealed-grid-5x6.v2"
    assert family.document_schema != placed.DOCUMENT_SCHEMA
    assert family.batch_cases == 30 and family.image == placed.SOLVER_IMAGE
    assert issubclass(MotorSealedGridBatchSource, FamilySource)
    assert grid.DEPLOYMENT_SCHEMA != placed.DEPLOYMENT_SCHEMA
    assert grid.STORE_SCHEMA != placed.STORE_SCHEMA


def test_the_rule_cites_the_unchanged_evaluation_version_and_the_grid():
    rule = grid.hidden_rule()
    assert rule["exam"]["evaluation_version"] == "motor-dual-sealed-batch-30-v1"
    assert rule["population"]["grid"] == {"designs": 5, "conditions": 6}
    assert rule["authority"] == "OWNER-MOTOR-EXAM-GRID-01"
    assert rule != placed.hidden_rule()
    text = json.dumps(rule)
    for scoring in ("weight", "reward", "min_torque"):
        assert scoring not in text


def test_a_draw_is_a_full_buildable_5_by_6_grid_meeting_the_placement(drawn_grid):
    cases, tries = drawn_grid
    designs, conditions = population.grid_of(cases)
    assert (len(designs), len(conditions), len(cases)) == (5, 6, 30)
    assert all(population.admitted(c) for c in cases)
    torque, ripple = population.predict(cases)
    ok_t, ok_r = torque >= 4.0, ripple <= 0.30
    assert 16 <= ok_t.sum() <= 19 and 16 <= ok_r.sum() <= 19
    feasible = (ok_t & ok_r).reshape(5, 6)  # design-major, as drawn
    assert feasible.all(axis=1).sum() >= 2 and not feasible.all(axis=0).any()
    # C17 fallback: 2 to 3 designs cleared at every condition at U-only clearance, and every condition has one
    clear = (torque >= 4.0 + 0.0052) & (ripple <= 0.30 - 0.026)
    sure = clear.reshape(5, 6)
    assert 2 <= sure.all(axis=1).sum() <= 3 and sure.any(axis=0).all()
    assert tries >= 1
    stored = population.placement_predictions(cases)
    assert len(stored) == 30 and set(stored[0]) == {"predicted_mean_torque_nm", "predicted_ripple_fraction"}


def test_a_seed_without_a_grid_raises_and_the_next_role_is_a_new_seed():
    with pytest.raises(RuntimeError, match="placed no grid"):
        population.draw(random.Random(1), population.CELLS, max_attempts=1)


def test_documents_must_be_a_full_grid(drawn_grid):
    cases, _ = drawn_grid
    good = document(cases)
    assert len(grid.check_document(good)) == 30
    other = dict(good, cases=list(good["cases"]))
    other["cases"][0] = {"case_id": "g00", "inputs": dict(cases[1])}  # a repeated cell
    for bad in (
        dict(good, schema=placed.DOCUMENT_SCHEMA),
        dict(good, cases=good["cases"][:29]),
        other,
    ):
        with pytest.raises(ValueError):
            grid.check_document(bad)


def test_the_selector_picks_the_grid_by_its_deployment_schema(tmp_path):
    path = write_deployment(
        tmp_path / "etc-grid" / "motor.json",
        grid.DEPLOYMENT_SCHEMA,
        store=str(tmp_path / "grid-store"),
        custody=str(tmp_path / "grid-custody"),
    )
    MotorSealedGridBatchSource.init(path)
    assert type(motor_source_for(path, repository=REPOSITORY)) is MotorSealedGridBatchSource
    other = write_deployment(
        tmp_path / "etc-placed" / "motor.json",
        placed.DEPLOYMENT_SCHEMA,
        store=str(tmp_path / "placed-store"),
        custody=str(tmp_path / "placed-custody"),
    )
    MotorSealedBatchSource.init(other)
    assert type(motor_source_for(other, repository=REPOSITORY)) is MotorSealedBatchSource


def test_a_grid_batch_is_drawn_solved_sealed_and_packed(tmp_path):
    path = write_deployment(
        tmp_path / "producer-etc" / "motor.json",
        grid.DEPLOYMENT_SCHEMA,
        store=str(tmp_path / "producer-store"),
        custody=str(tmp_path / "producer-custody"),
    )
    MotorSealedGridBatchSource.init(path)
    solver = Solver()
    source = MotorSealedGridBatchSource(path, repository=REPOSITORY, runner=solver)
    producer = pr.Producer(tmp_path / "producer", [source])
    drawn = None
    for suffix in ("S1", "S2", "S3", "S4", "S5", "S6"):
        try:
            drawn = producer.draw(MOTOR, f"motor-grid-exam-{suffix}", kind="screening")
            break
        except RuntimeError:  # no grid placed for this role: the operator moves to the next role (placement precedes every solve)
            continue
    assert drawn is not None
    jobs = source.jobs(drawn["fingerprint"])
    assert len(jobs) == 30
    producer.solve(MOTOR, drawn["fingerprint"])
    producer.seal(MOTOR, drawn["fingerprint"])
    exported = source.export(drawn["fingerprint"])
    assert exported["document"]["schema"] == grid.DOCUMENT_SCHEMA
    bank = pack.grid_bank(exported["document"], list(exported["references"].values()))
    assert bank["cohorts"] == ("decision_sealed_grid",) * 30


def test_the_pack_names_each_cell_with_design_and_condition_ids(drawn_grid):
    cases, _ = drawn_grid
    doc = document(cases)
    bank = pack.grid_bank(doc, records_for(doc))
    assert bank["cohorts"] == (pack.GRID_COHORT,) * 30 == ("decision_sealed_grid",) * 30
    designs = {r["design_id"] for r in bank["reference_records"]}
    conditions = {r["condition_id"] for r in bank["reference_records"]}
    assert designs == {f"design-{i}" for i in range(5)}
    assert conditions == {f"condition-{i}" for i in range(6)}
    cells = {(r["design_id"], r["condition_id"]) for r in bank["reference_records"]}
    assert len(cells) == 30
    assert set(pack.private_roles(bank)) == {"case_bank", "reference_rows", "solver_evidence"}
    # a placed (non-grid) document is not a grid batch
    with pytest.raises(pack.SealedPackRefused):
        pack.grid_bank(dict(doc, schema=placed.DOCUMENT_SCHEMA), records_for(doc))


def _cells(feasible, torque=5.0, ripple=0.1):
    """A 5 x 6 grid of reference quantities; `feasible(d, c)` -> bool."""
    cells = []
    for d in range(5):
        for c in range(6):
            ok = feasible(d, c)
            cells.append(
                {
                    "design_id": f"design-{d}",
                    "condition_id": f"condition-{c}",
                    "mean_torque_nm": torque if ok else 1.0,
                    "ripple_fraction": ripple + 0.001 * d if ok else 0.9,
                }
            )
    return cells


U = (0.0052, 0.026)


def test_the_decision_check_accepts_a_grid_that_can_measure_design_value():
    # design-0 feasible everywhere; design-1..4 fail at condition-0 only
    cells = _cells(lambda d, c: d == 0 or c != 0)
    assert dc.check(cells, *U) is None


def test_the_decision_check_refuses_a_grid_with_no_choice_or_no_winner():
    # every design feasible at every condition: no non-trivial condition
    assert dc.check(_cells(lambda d, c: True), *U) == "decision_no_nontrivial_condition"
    # no design feasible everywhere: each design fails at a different condition
    cells = _cells(lambda d, c: c != d)
    assert dc.check(cells, *U) == "decision_no_design_feasible_everywhere"
    assert dc.check(cells[:29], *U) == "decision_grid_incomplete"


def test_cells_within_u_of_a_limit_are_unresolved_not_feasible():
    near = _cells(lambda d, c: True, torque=4.0 + 0.001, ripple=0.30 - 0.001)
    assert {dc.label(c["mean_torque_nm"], c["ripple_fraction"], *U) for c in near} == {
        dc.UNRESOLVED
    }
    assert dc.label(4.0 + 0.01, 0.1, *U) == dc.FEASIBLE
    assert dc.label(3.9, 0.1, *U) == dc.INFEASIBLE
    with pytest.raises(ValueError):
        dc.label(float("nan"), 0.1, *U)


def test_the_clearance_rule_refuses_without_a_measured_value_and_the_full_one_places_nothing():
    with pytest.raises(RuntimeError, match="placement_clearance_unavailable"):
        population.draw_v2(random.Random(1), population.CELLS, None)
    with pytest.raises(RuntimeError, match="placement_clearance_unavailable"):
        population.draw_v2(random.Random(1), population.CELLS, {"mean_torque_nm": 0.4362})
    full = {  # the measured clearance (90 cells): torque 0.4362, ripple e 0.9138 with U 0.026
        "mean_torque_nm": 0.4362,
        "ripple_fraction_log_ratio": 0.9138,
        "ripple_fraction_u": 0.026,
    }
    with pytest.raises(RuntimeError, match="placed no grid"):
        population.draw_v2(random.Random(0), population.CELLS, full, max_attempts=3000)
