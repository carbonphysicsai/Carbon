"""Report-only outputs of a pool-graded version (`PhysicsRule.report_only_outputs`; Motor 1.9 ADJ-C ask, 21 Nov 2026).

A registered report-only output is RECORDED for every class like any output, but never gated (no threshold needed, its
in-range verdict is None, it cannot fail the gate) and never scored (a scoring cell naming it refuses at attach). Absent,
every path is unchanged. Every name and value here is a SYNTHETIC fixture.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_pool_physics_score import CELLS, EDGE, IN, STEP, model, rule, stand_set

from carbon.scoring import pool_physics_score as pps

#: CELLS without its one scored cell on output g
CELLS_F = {
    **CELLS,
    "scored": [["fixture-F1", EDGE, "f"], ["fixture-F3", STEP, "f"]],
}


def _attach(specs, plan, *, threshold, cells, report_only=()):
    the_rule = replace(
        rule(threshold=threshold, cells=cells), report_only_outputs=report_only
    )
    return pps.attach_cells(the_rule, cells, plan, (tuple(specs),))


def test_absent_it_is_empty_and_nothing_changes():
    assert rule().report_only_outputs == ()
    pps.check_rule(rule())


@pytest.mark.parametrize("value", [["g"], ("g", "g"), ("",), (1,)])
def test_a_malformed_registration_refuses(value):
    with pytest.raises(pps.PhysicsRefused, match="report_only_outputs_malformed"):
        pps.check_rule(replace(rule(), report_only_outputs=value))


def test_a_report_only_output_needs_no_threshold_and_is_still_recorded():
    specs, plan = stand_set()
    with pytest.raises(
        pps.PhysicsRefused, match="accuracy_gate_threshold_missing_for_an_output"
    ):
        _attach(specs, plan, threshold={"f": 1.0}, cells=CELLS_F)
    attached = _attach(
        specs, plan, threshold={"f": 1.0}, cells=CELLS_F, report_only=("g",)
    )
    record = pps.accuracy_record(specs, model(specs), plan, attached)
    rows = {(r["class"], r["output"]): r for r in record["rows"]}
    in_g, in_f = rows[(IN, "g")], rows[(IN, "f")]
    assert (in_g["verdict"], in_g["scored"], in_g["n"]) == (None, False, 5)
    assert in_g["p90"] == pytest.approx(
        in_f["p90"]
    )  # the same statistics as any output
    assert in_f["verdict"] == "PASS"
    assert rows[(EDGE, "g")]["scored"] is False
    assert record["gate"]["passed"] is True


def test_a_report_only_output_can_never_fail_the_gate():
    specs, plan = stand_set()
    strict = {"f": 1.0, "g": 0.5}  # g's p90 (0.92) fails 0.5
    failing = _attach(specs, plan, threshold=strict, cells=CELLS_F)
    assert pps.accuracy_record(specs, model(specs), plan, failing)["gate"] == {
        "statistic": "p90",
        "passed": False,
    }
    reported = _attach(specs, plan, threshold=strict, cells=CELLS_F, report_only=("g",))
    assert (
        pps.accuracy_record(specs, model(specs), plan, reported)["gate"]["passed"]
        is True
    )


def test_a_scoring_cell_naming_a_report_only_output_refuses_at_attach():
    specs, plan = stand_set()
    with pytest.raises(pps.PhysicsRefused, match="scoring_cell_output_is_report_only"):
        _attach(specs, plan, threshold=1.0, cells=CELLS, report_only=("g",))


def test_it_registers_as_a_non_empty_list_with_no_placeholder(tmp_path):
    from carbon.scoring import pool_version

    document = json.loads(pool_version.CONSTANTS.read_bytes())
    base = json.loads(json.dumps(document["versions"]["chip-cold-plate 1.6"]))
    path = tmp_path / "pool_constants.json"

    def read(physics):
        entry = {**base, "physics": physics}
        path.write_text(json.dumps({**document, "versions": {"fixture 9.9": entry}}))
        return pool_version.registered_policies("fixture", "9.9", path=path)

    good = {
        "cells_sha256": pps.cell_map(CELLS_F).sha256,
        "gate_statistic": "p90",
        "gate_threshold": {"f": 1.0},
        "gate_cases": "pool",
        "enters": "a",
        "ad_split": 0.5,
        "total_rule": "half_a_half_d",
        "cell_scale": "agen_scales",
    }
    assert read(good).physics.report_only_outputs == ()
    assert read({**good, "report_only_outputs": ["g"]}).physics.report_only_outputs == (
        "g",
    )
    for bad in ([], "g", [pool_version.HUMAN_INPUT], ["g", "g"], [None]):
        with pytest.raises(pool_version.PoolConstantsNotRegistered):
            read({**good, "report_only_outputs": bad})


# --- report-only CELLS (owner MAGNET CELLS MOTOR, 21 Nov 2026): per (class, output), not the whole output ------------


def _attach_cells(specs, plan, *, threshold, cells, report_only_cells):
    the_rule = replace(
        rule(threshold=threshold, cells=cells), report_only_cells=report_only_cells
    )
    return pps.attach_cells(the_rule, cells, plan, (tuple(specs),))


def test_a_report_only_cell_is_ungated_in_its_class_only_and_still_recorded():
    specs, plan = stand_set()
    strict = {"f": 1.0, "g": 0.5}  # g's in-range p90 (0.92) fails 0.5
    attached = _attach_cells(
        specs, plan, threshold=strict, cells=CELLS, report_only_cells=((IN, "g"),)
    )
    record = pps.accuracy_record(specs, model(specs), plan, attached)
    rows = {(r["class"], r["output"]): r for r in record["rows"]}
    assert rows[(IN, "g")]["verdict"] is None and rows[(IN, "g")]["n"] == 5
    assert rows[(IN, "f")]["verdict"] == "PASS"
    assert rows[(EDGE, "g")]["scored"] is True  # g still scores in another class
    assert record["gate"]["passed"] is True


def test_a_scored_cell_that_is_report_only_refuses():
    specs, plan = stand_set()
    with pytest.raises(pps.PhysicsRefused, match="scoring_cell_output_is_report_only"):
        _attach_cells(
            specs, plan, threshold=1.0, cells=CELLS, report_only_cells=((EDGE, "g"),)
        )


def test_an_in_range_class_keeps_at_least_one_gated_output():
    specs, plan = stand_set()
    with pytest.raises(
        pps.PhysicsRefused, match="in_range_class_without_a_gated_output"
    ):
        _attach_cells(
            specs,
            plan,
            threshold=1.0,
            cells=CELLS,
            report_only_cells=((IN, "f"), (IN, "g")),
        )


@pytest.mark.parametrize(
    "value", [[(IN, "g")], ((IN,),), ((IN, ""),), ((IN, "g"), (IN, "g"))]
)
def test_malformed_report_only_cells_refuse(value):
    with pytest.raises(pps.PhysicsRefused, match="report_only_cells_malformed"):
        pps.check_rule(replace(rule(), report_only_cells=value))


def test_report_only_cells_register_as_a_list_of_pairs(tmp_path):
    from carbon.scoring import pool_version

    document = json.loads(pool_version.CONSTANTS.read_bytes())
    base = json.loads(json.dumps(document["versions"]["chip-cold-plate 1.6"]))
    path = tmp_path / "pool_constants.json"

    def read(physics):
        entry = {**base, "physics": physics}
        path.write_text(json.dumps({**document, "versions": {"fixture 9.9": entry}}))
        return pool_version.registered_policies("fixture", "9.9", path=path)

    good = {
        "cells_sha256": pps.cell_map(CELLS).sha256,
        "gate_statistic": "p90",
        "gate_threshold": {"f": 1.0},
        "gate_cases": "pool",
        "enters": "a",
        "ad_split": 0.5,
        "total_rule": "half_a_half_d",
        "cell_scale": "agen_scales",
    }
    assert read(good).physics.report_only_cells == ()
    assert read(
        {**good, "report_only_cells": [[IN, "g"]]}
    ).physics.report_only_cells == ((IN, "g"),)
    for bad in (
        [],
        [[IN]],
        [[IN, pool_version.HUMAN_INPUT]],
        "x",
        [[IN, "g"], [IN, "g"]],
    ):
        with pytest.raises(pool_version.PoolConstantsNotRegistered):
            read({**good, "report_only_cells": bad})


# --- a report-only name must name a real output (22 Nov 2026: a card label matched nothing and left the output gated) -


@pytest.mark.parametrize("name", ["g_shape", "G", "h"])
def test_a_report_only_output_no_target_carries_refuses_at_attach(name):
    specs, plan = stand_set()
    with pytest.raises(pps.PhysicsRefused, match="report_only_output_not_an_output"):
        _attach(specs, plan, threshold=1.0, cells=CELLS_F, report_only=("g", name))


@pytest.mark.parametrize("cell", [(IN, "g_shape"), ("fixture-no-such-class", "g")])
def test_a_report_only_cell_its_class_does_not_carry_refuses_at_attach(cell):
    specs, plan = stand_set()
    with pytest.raises(
        pps.PhysicsRefused, match="report_only_cell_not_an_output_of_its_class"
    ):
        _attach_cells(
            specs, plan, threshold=1.0, cells=CELLS, report_only_cells=(cell,)
        )
