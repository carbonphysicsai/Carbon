"""Battery's sealed-exam family (VALIDATOR_BATTERY_SEALED_RULINGS_20261022): its
registration is the hidden rule's own values, its draw is the 420-grid hull law
disjoint from published cases, its records are checked with the pinned v2
reader, and its pack refuses anything but a whole, straddling batch."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

from carbon.battery import truth
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


def test_the_producer_finds_battery_sealed_as_a_registered_family():
    assert family_source_class("battery-sealed-exam") is BatterySealedSource
    assert issubclass(BatterySealedSource, FamilySource)
    # never the registry Challenge's own producer id
    assert family_source_class("battery-fastcharge-ageing-development-v1") is None


def test_the_registration_is_the_hidden_rules_own_values():
    family = battery_sealed_family()
    assert family.challenge_id == "battery-sealed-exam"
    assert family.kinds == hidden.KINDS == ("screening",)
    assert family.batch_cases == hidden.BATCH_CASES == 8
    assert family.every_blocks == hidden.ROTATION_EVERY_BLOCKS == 648_000
    assert family.active_batches == 1
    assert family.terminal == hidden.TERMINAL
    assert family.image_env == "CARBON_BATTERY_SEALED_IMAGE"
    assert (REPOSITORY / hidden.RUNNER).is_file()


def test_the_image_is_the_truth_images_and_the_version_is_the_validators():
    assert truth.TRUTH_IMAGE["base_image"].endswith(hidden.SOLVER_IMAGE.split(":")[1])
    rule = hidden.hidden_rule()
    assert rule["exam"]["evaluation_version"] == "battery-dual-sealed-batch-8-v1"
    text = json.dumps(rule)
    for scoring in ("weight", "threshold", "reward", "evaluation_rule"):
        assert scoring not in text


def test_the_hull_is_the_420_grids_own_extremes():
    from carbon.battery.value import contract as ev

    contract = json.loads(
        (ev.CONTRACTS / "ev4-charge-protocol-selection.v1.json").read_bytes()
    )
    t = [c[0] for s in ev.scenarios(contract, "development") for c in s["conditions"]]
    soc = [c[1] for s in ev.scenarios(contract, "development") for c in s["conditions"]]
    candidates = ev.candidates(contract)
    assert len(t) * len(candidates) == 12 * 35
    hull = population.HULL
    assert hull["t_amb_c"] == (min(t), max(t))
    assert hull["soc0"] == (min(soc), max(soc))
    assert hull["c1"] == (min(c["c1"] for c in candidates), max(c["c1"] for c in candidates))
    assert hull["c2"] == (min(c["c2"] for c in candidates), max(c["c2"] for c in candidates))


def test_a_draw_is_admitted_distinct_and_not_published():
    cases, _attempts = population.draw(random.Random(7), 8)
    assert len(cases) == 8
    keys = {tuple(c.values()) for c in cases}
    assert len(keys) == 8
    published, key = population._published()
    assert all(population.admitted(c) and key(c) not in published for c in cases)
    assert not population.admitted({"c1": 0.5, "c2": 0.2, "t_amb_c": 40.0, "soc0": 0.12})
    assert not population.admitted({"c1": 0.5, "c2": 0.2, "t_amb_c": 20.123456, "soc0": 0.2})


def test_the_420_grid_points_are_published_overlap_keys():
    published, key = population._published()
    grid_point = {"c1": 0.75, "c2": 0.6, "t_amb_c": 12.75, "soc0": 0.15}
    assert key(grid_point) in published  # a public D3 case


def _inputs(i):
    return {"c1": 1.0 + i / 100, "c2": 0.5, "t_amb_c": 20.0 + i / 10, "soc0": 0.2}


def _document():
    return {
        "schema": hidden.DOCUMENT_SCHEMA,
        "challenge": {"id": hidden.CHALLENGE_ID, "version": hidden.CHALLENGE_VERSION},
        "role": "battery-sealed-exam-1",
        "kind": "screening",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"c{i}", "inputs": _inputs(i)} for i in range(8)],
    }


def _record(i, m20, m160, **changes):
    record = {
        "case_id": f"c{i}",
        "inputs": _inputs(i),
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


def _batch():
    # margins: four clearly plated, four clearly not (no claim at 20 mV)
    return [_record(i, -0.01 if i < 4 else 0.02, -0.01 if i < 4 else 0.02) for i in range(8)]


def test_the_document_is_checked_for_shape_and_hull():
    assert set(hidden.check_document(_document())) == {f"c{i}" for i in range(8)}
    bad = _document()
    bad["cases"][0]["inputs"]["t_amb_c"] = 39.0  # outside the 420 grid's hull
    with pytest.raises(ValueError):
        hidden.check_document(bad)
    short = _document()
    short["cases"].pop()
    with pytest.raises(ValueError):
        hidden.check_document(short)


def test_a_reference_is_checked_and_the_label_is_the_pinned_readers():
    record = _record(0, -0.01, -0.01)
    hidden.check_reference(record, _inputs(0))
    assert record["plating"] == {"label": "INFEASIBLE", "rule": "m20-no-claim-gate-plating-v2"} or (
        record["plating"]["label"] == "INFEASIBLE"
    )
    near = _record(1, 0.002, 0.0012)  # inside the window: m160 decides
    assert near["plating"] == {"label": "FEASIBLE", "rule": "m160-d3-r1"}
    hidden.check_reference(near, _inputs(1))
    forged = _record(2, 0.002, 0.0012, plating={"label": "INFEASIBLE", "rule": "m160-d3-r1"})
    for bad in (
        forged,
        _record(0, -0.01, -0.01, image="sha256:" + "0" * 64),
        _record(0, -0.01, -0.01, overlay_lock_sha256="0" * 64),
        _record(0, -0.01, -0.01, inputs=_inputs(5)),
        _record(0, -0.01, float("nan")),
    ):
        with pytest.raises(ValueError):
            hidden.check_reference(bad, _inputs(0))
    hidden.check_reference({**record, "status": "REFERENCE_SOLVER_FAILED"}, _inputs(0))


def test_the_pack_is_the_whole_straddling_batch_or_nothing():
    document = _document()
    bank = pack.sealed_bank(document, _batch())
    assert bank["reference_present"] == (True,) * 8
    assert bank["references"].shape == (8, 247) and bank["inputs"].shape == (8, 4)
    assert set(pack.private_roles(bank)) == {"case_bank", "reference_rows", "solver_evidence"}
    with pytest.raises(pack.SealedPackRefused) as refused:
        pack.sealed_bank(document, _batch()[:7])
    assert refused.value.code == "battery_sealed_case_unresolved"
    failed = _batch()
    failed[3] = {**failed[3], "status": "REFERENCE_SOLVER_FAILED"}
    with pytest.raises(pack.SealedPackRefused) as refused:
        pack.sealed_bank(document, failed)
    assert refused.value.code == "battery_sealed_case_unresolved"
    one_side = [_record(i, -0.01, -0.01) for i in range(8)]
    with pytest.raises(pack.SealedPackRefused) as refused:
        pack.sealed_bank(document, one_side)
    assert refused.value.code == "battery_sealed_no_straddle"


def test_the_runner_builds_records_without_merging_failure_kinds():
    import battery_exam_runner as runner

    plan = {"batch": "b", "kind": "screening"}
    case = {"case_id": "c0", "inputs": _inputs(0)}
    image, lock = hidden.SOLVER_IMAGE, hidden.overlay_lock_sha256()
    std = {"status": "OK", "outputs": _record(0, -0.01, -0.01)["outputs"], "wall_s": 1.0, "maxrss_mb": 1000}
    plat = {"status": "OK", "plating_margin_v": -0.01, "wall_s": 2.0, "maxrss_mb": 6000}
    ok = runner.record_for(plan, case, ("done", std), ("done", plat), image, lock)
    assert ok["status"] == "OK"
    hidden.check_reference(ok, _inputs(0))
    kinds = {
        "FAILED_INFRA": runner.record_for(plan, case, ("done", std), ("infra", None), image, lock),
        "REFERENCE_TIMEOUT": runner.record_for(plan, case, ("timeout", None), ("done", plat), image, lock),
        "REFERENCE_SOLVER_FAILED": runner.record_for(
            plan, case, ("done", {"status": "REFERENCE_SOLVER_FAILED"}), ("done", {"status": "REFERENCE_SOLVER_FAILED"}), image, lock
        ),
    }
    for status, record in kinds.items():
        assert record["status"] == status
    assert "FAILED_INFRA" not in hidden.TERMINAL
    assert runner.TERMINAL == hidden.TERMINAL
    with pytest.raises(SystemExit):
        runner.check_plan({"batch": "b", "cases": [{"case_id": "x/y", "inputs": _inputs(0)}]})


def test_a_b15_probe_equal_at_four_places_is_an_overlap_key():
    plan = json.loads(
        (
            REPOSITORY
            / "docs/development/evidence/battery-b15-public-probes-20261020/plan.json"
        ).read_bytes()
    )
    published, key = population._published()
    from carbon.battery.domain import INPUTS

    probe = plan["pairs"][0]["base"]
    assert any(float(probe[n]) != round(float(probe[n]), 4) for n in INPUTS)
    rounded = {n: round(float(probe[n]), 4) for n in INPUTS}
    assert key(rounded) in published
