"""Battery's sealed-exam family (OWNER-BATTERY-EXAM-GRID-01; Validator rulings
VALIDATOR_BATTERY_SEALED_RULINGS_20261022 section 11): a placed 4 scenarios x
EV4's 35 candidates grid, checked with the pinned v2 reader, packed
whole-batch-or-nothing with scenario and candidate ids, and gated by the
post-solve straddle and decision checks."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

from carbon.battery import truth
from carbon.battery_sealed import decision_check as dc
from carbon.battery_sealed import population
from carbon.challenge_kit import battery_sealed_pack as pack
from carbon.challenge_validator import battery_sealed_hidden as hidden
from carbon.challenge_validator.battery_sealed_source import (
    BatterySealedSource,
    battery_sealed_family,
)
from carbon.challenge_validator.family_source import FamilySource, family_source_class

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "scripts/dev/battery"))
U = 0.00023


def test_the_producer_finds_battery_sealed_as_a_registered_family():
    assert family_source_class("battery-sealed-exam") is BatterySealedSource
    assert issubclass(BatterySealedSource, FamilySource)
    assert family_source_class("battery-fastcharge-ageing-development-v1") is None


def test_the_registration_is_the_grid_rules_values():
    family = battery_sealed_family()
    assert family.challenge_id == "battery-sealed-exam"
    assert family.kinds == hidden.KINDS == ("screening",)
    assert family.batch_cases == hidden.BATCH_CASES == 140
    assert family.every_blocks == hidden.ROTATION_EVERY_BLOCKS == 648_000
    assert family.population_version == "carbon.battery.sealed-grid-4x35.v1"
    assert family.image_env == "CARBON_BATTERY_SEALED_IMAGE"
    assert (REPOSITORY / hidden.RUNNER).is_file()


def test_the_image_is_the_truth_images_and_the_version_is_renamed():
    assert truth.TRUTH_IMAGE["base_image"].endswith(hidden.SOLVER_IMAGE.split(":")[1])
    rule = hidden.hidden_rule()
    assert rule["exam"]["evaluation_version"] == "battery-dual-sealed-grid-4x35-v1"
    text = json.dumps(rule)
    assert "battery-dual-sealed-batch-8-v1" not in text
    for scoring in ("weight", "threshold", "reward", "evaluation_rule"):
        assert scoring not in text


def test_the_scenario_hull_is_the_420_grids_own_extremes():
    from carbon.battery.value import contract as ev

    document, candidates = population.contract()
    conditions = [c for s in ev.scenarios(document, "development") for c in s["conditions"]]
    assert len(candidates) == 35 and len(conditions) == 12
    t = [c[0] for c in conditions]
    soc = [c[1] for c in conditions]
    assert population.HULL["t_amb_c"] == (min(t), max(t))
    assert population.HULL["soc0"] == (min(soc), max(soc))


@pytest.fixture(scope="module")
def grid():
    return population.draw(random.Random(11), population.CELLS)


def test_a_draw_is_a_placed_4_by_35_grid_disjoint_from_ev4(grid):
    cases, attempts = grid
    scenarios = population.scenarios_of(cases)
    assert len(cases) == 140 and len(scenarios) == 4 and attempts >= 4
    assert all(population.admitted(c) for c in cases)
    assert not set(scenarios) & population.ev4_scenario_conditions()
    published, key = population._published()
    assert not any(key(c) in published for c in cases)
    wanted = [(c["c1"], c["c2"]) for c in population.candidates()]  # EV4's order
    for t, s in scenarios:
        got = [(c["c1"], c["c2"]) for c in cases if (c["t_amb_c"], c["soc0"]) == (t, s)]
        assert got == wanted
        margins = [m for m in population.predicted_margins(t, s).values() if m is not None]
        assert any(m >= 4.5e-3 for m in margins) and any(m <= -1.97e-3 for m in margins)


def test_the_excluded_corner_and_ev4_scenarios_are_not_drawn():
    assert not population.scenario_admitted(5.0, 0.48)  # EV4's own failing corner
    assert not population.scenario_admitted(7.0, 0.45)  # inside the excluded box
    assert not population.scenario_admitted(14.0, 0.33)  # an EV4 development scenario
    assert not population.scenario_admitted(20.123456, 0.3)  # not 4 decimals
    assert not population.scenario_admitted(40.0, 0.3)  # outside the hull
    assert population.scenario_admitted(20.1234, 0.3)


def test_a_seed_that_places_no_scenarios_raises():
    with pytest.raises(RuntimeError, match="placed only"):
        population.draw(random.Random(1), population.CELLS, max_attempts=1)


def _document(cases):
    return {
        "schema": hidden.DOCUMENT_SCHEMA,
        "challenge": {"id": hidden.CHALLENGE_ID, "version": hidden.CHALLENGE_VERSION},
        "role": "battery-sealed-exam-1",
        "kind": "screening",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"c{i:03d}", "inputs": c} for i, c in enumerate(cases)],
    }


def test_the_document_must_be_a_full_grid_on_ev4_candidates(grid):
    cases, _ = grid
    assert len(hidden.check_document(_document(cases))) == 140
    short = _document(cases[:139])
    off_grid = _document([dict(cases[0], c1=0.51)] + cases[1:])
    repeated = _document([cases[0]] + cases[:139])
    for bad in (short, off_grid, repeated):
        with pytest.raises(ValueError):
            hidden.check_document(bad)


def _record(case_id, inputs, m20, m160, **changes):
    record = {
        "case_id": case_id,
        "inputs": inputs,
        "status": "OK",
        "image": hidden.SOLVER_IMAGE,
        "overlay_lock_sha256": hidden.overlay_lock_sha256(),
        "outputs": {
            "voltage_v": [3.5] * 121,
            "temperature_c": [25.0] * 121,
            "plating_margin_v": m20,
            "capacity_ah": [1.0, 0.99, 0.98, 0.97],
        },
        "plating_margin_m160_v": m160,
    }
    record["plating"] = hidden.plating_label(m20, m160)
    record.update(changes)
    return record


def _records(document, plated=lambda s, k: k % 2 == 0):
    """140 OK records, scenario-major over EV4's candidate order."""
    out = []
    for i, case in enumerate(document["cases"]):
        s, k = divmod(i, 35)
        margin = -0.01 if plated(s, k) else 0.02
        out.append(_record(case["case_id"], case["inputs"], margin, margin))
    return out


def test_a_reference_is_checked_and_the_label_is_the_pinned_readers(grid):
    cases, _ = grid
    inputs = cases[0]
    record = _record("c000", inputs, -0.01, -0.01)
    hidden.check_reference(record, inputs)
    near = _record("c000", inputs, 0.002, 0.0012)  # inside the window: m160 decides
    assert near["plating"] == {"label": "FEASIBLE", "rule": "m160-d3-r1"}
    hidden.check_reference(near, inputs)
    for bad in (
        _record("c000", inputs, 0.002, 0.0012, plating={"label": "INFEASIBLE", "rule": "m160-d3-r1"}),
        _record("c000", inputs, -0.01, -0.01, image="sha256:" + "0" * 64),
        _record("c000", inputs, -0.01, -0.01, overlay_lock_sha256="0" * 64),
        _record("c000", inputs, -0.01, float("nan")),
    ):
        with pytest.raises(ValueError):
            hidden.check_reference(bad, inputs)
    hidden.check_reference({**record, "status": "REFERENCE_SOLVER_FAILED"}, inputs)


def test_the_pack_is_the_whole_straddling_grid_with_cell_ids(grid):
    cases, _ = grid
    document = _document(cases)
    bank = pack.sealed_bank(document, _records(document))
    assert bank["reference_present"] == (True,) * 140
    assert bank["cohorts"] == ("decision_sealed_grid",) * 140
    assert bank["references"].shape == (140, 247) and bank["inputs"].shape == (140, 4)
    ids = {(r["scenario_id"], r["candidate_id"]) for r in bank["reference_records"]}
    assert len(ids) == 140
    assert {s for s, _ in ids} == {f"scenario-{i}" for i in range(4)}
    assert {k for _, k in ids} == {c["id"] for c in population.candidates()}
    assert set(pack.private_roles(bank)) == {"case_bank", "reference_rows", "solver_evidence"}
    with pytest.raises(pack.SealedPackRefused) as refused:
        pack.sealed_bank(document, _records(document)[:139])
    assert refused.value.code == "battery_sealed_case_unresolved"
    failed = _records(document)
    failed[7] = {**failed[7], "status": "REFERENCE_SOLVER_FAILED"}
    with pytest.raises(pack.SealedPackRefused) as refused:
        pack.sealed_bank(document, failed)
    assert refused.value.code == "battery_sealed_case_unresolved"
    with pytest.raises(pack.SealedPackRefused) as refused:
        pack.sealed_bank(document, _records(document, plated=lambda s, k: True))
    assert refused.value.code == "battery_sealed_no_straddle"


def _cases(plated, unresolved=lambda s, k: False):
    out = []
    for s in range(4):
        for k in range(35):
            is_plated = plated(s, k)
            out.append(
                {
                    "scenario_id": f"scenario-{s}",
                    "label": "UNRESOLVED" if unresolved(s, k) else ("INFEASIBLE" if is_plated else "FEASIBLE"),
                    "m160_v": -0.01 if is_plated else 0.02,
                }
            )
    return out


def test_the_straddle_counts_a_third_a_side_over_all_140():
    short = "straddle_short:plating_margin_m160_v"
    assert dc.straddle(_cases(lambda s, k: k % 2 == 0), U) is None
    assert dc.straddle(_cases(lambda s, k: True), U) == short
    assert dc.straddle(_cases(lambda s, k: (s * 35 + k) < 47), U) is None  # 47 >= 140 / 3
    assert dc.straddle(_cases(lambda s, k: (s * 35 + k) < 46), U) == short
    # unresolved cases count on neither side
    assert dc.straddle(_cases(lambda s, k: k % 2 == 0, unresolved=lambda s, k: k % 4 == 0), U) is not None
    assert dc.side("FEASIBLE", 0.0001, U) is None  # within U of 0


def test_every_scenario_needs_a_feasible_and_an_infeasible_candidate():
    assert dc.decision(_cases(lambda s, k: k % 2 == 0), U) is None
    assert dc.decision(_cases(lambda s, k: s == 2 or k % 2 == 0), U) == "decision_scenario_no_feasible"
    assert dc.decision(_cases(lambda s, k: s != 1 and k % 2 == 0), U) == "decision_scenario_no_infeasible"
    only_unresolved = _cases(lambda s, k: k % 2 == 0, unresolved=lambda s, k: s == 3 and k % 2 == 1)
    assert dc.decision(only_unresolved, U) == "decision_scenario_no_feasible"


def test_the_runner_builds_records_without_merging_failure_kinds():
    import battery_exam_runner as runner

    plan = {"batch": "b", "kind": "screening"}
    inputs = {"c1": 1.0, "c2": 0.4, "t_amb_c": 20.0, "soc0": 0.3}
    case = {"case_id": "c0", "inputs": inputs}
    image, lock = hidden.SOLVER_IMAGE, hidden.overlay_lock_sha256()
    std = {"status": "OK", "outputs": _record("c0", inputs, -0.01, -0.01)["outputs"], "wall_s": 1.0, "maxrss_mb": 1000}
    plat = {"status": "OK", "plating_margin_v": -0.01, "wall_s": 2.0, "maxrss_mb": 6000}
    ok = runner.record_for(plan, case, ("done", std), ("done", plat), image, lock)
    assert ok["status"] == "OK"
    hidden.check_reference(ok, inputs)
    failed = {"status": "REFERENCE_SOLVER_FAILED"}
    kinds = {
        "FAILED_INFRA": runner.record_for(plan, case, ("done", std), ("infra", None), image, lock),
        "REFERENCE_TIMEOUT": runner.record_for(plan, case, ("timeout", None), ("done", plat), image, lock),
        "REFERENCE_SOLVER_FAILED": runner.record_for(plan, case, ("done", failed), ("done", failed), image, lock),
    }
    for status, record in kinds.items():
        assert record["status"] == status
    assert "FAILED_INFRA" not in hidden.TERMINAL
    assert runner.TERMINAL == hidden.TERMINAL
    with pytest.raises(SystemExit):
        runner.check_plan({"batch": "b", "cases": [{"case_id": "x/y", "inputs": inputs}]})


def test_a_b15_probe_equal_at_four_places_is_an_overlap_key():
    plan = json.loads(
        (REPOSITORY / "docs/development/evidence/battery-b15-public-probes-20261020/plan.json").read_bytes()
    )
    published, key = population._published()
    from carbon.battery.domain import INPUTS

    probe = plan["pairs"][0]["base"]
    assert any(float(probe[n]) != round(float(probe[n]), 4) for n in INPUTS)
    rounded = {n: round(float(probe[n]), 4) for n in INPUTS}
    assert key(rounded) in published
